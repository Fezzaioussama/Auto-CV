"""Auto-CV Flask application factory.

This wires together the public-web-app foundation (config, database, accounts,
CSRF, rate limiting, security headers) and the feature endpoints (job parsing,
CV optimization, PDF rendering, interview prep, cover letters, file ingestion,
and the per-user workspace).

The application is built by :func:`create_app`, so it can be created with test
or production configuration and discovered by ``flask --app autocv`` and
``python -m autocv``. ``templates/`` and ``static/`` live at the repository
root, alongside the package, and are wired in with absolute paths.
"""

from __future__ import annotations

import os
import base64
import logging
import traceback
from io import BytesIO
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    send_file,
    jsonify,
    redirect,
    url_for,
    session,
    current_app,
)
from flask_cors import CORS
from flask_login import login_required, current_user  # noqa: F401 (current_user kept for parity)
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config, ensure_instance_dir
from .extensions import db, login_manager, csrf, limiter, migrate

from . import llm_client  # loads .env and centralizes provider/model selection
from . import latex_repair  # compile + LLM auto-repair of LaTeX
from .parser import parse_job_description
from .matcher import analyze_cv, optimize_cv_for_job
from .latex_gen import render_cv, create_sample_cv  # noqa: F401 (render_cv used elsewhere)
from . import interview_agent


# ---------------------------------------------------------------------------
# Web assets: templates/ and static/ live at the repo root, alongside the
# package. This file is <repo>/src/autocv/app.py, so the repo root is two
# parents up (autocv -> src -> repo root).
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATE_DIR = _REPO_ROOT / "templates"
_STATIC_DIR = _REPO_ROOT / "static"


# Plain-text sample CV used by the public demo when a visitor doesn't paste
# their own. Broad enough to produce meaningful matched/missing lists.
_DEMO_SAMPLE_CV = """
Alex Morgan — Software Engineer
Summary: Backend-leaning full-stack engineer with 6 years building web apps and
APIs. Comfortable across the stack and shipping to production.
Skills: Python, Flask, JavaScript, SQL, PostgreSQL, REST APIs, Git, Linux,
unit testing, CI/CD, Agile.
Experience:
- Built and maintained Python/Flask services and REST APIs serving 100k users.
- Designed PostgreSQL schemas and optimized queries.
- Wrote automated tests and set up CI pipelines.
Education: BSc Computer Science.
"""


# ---------------------------------------------------------------------------
# Request helpers (shared by handlers + routes)
# ---------------------------------------------------------------------------


def _wants_json() -> bool:
    return request.path.startswith("/api/") or request.is_json


def _redirect_to_login():
    session["post_login_next"] = request.full_path if request.query_string else request.path
    return redirect(url_for("auth.login"))


def _server_error(exc: Exception):
    """Log the real error server-side; return a generic message to the client."""
    current_app.logger.error("Unhandled error on %s: %s", request.path, exc)
    current_app.logger.debug("%s", traceback.format_exc())
    return jsonify({"error": "Something went wrong. Please try again."}), 500


def llm_limit() -> str:
    """Per-request resolution of the tighter limit for expensive endpoints."""
    return current_app.config.get("RATELIMIT_LLM", "40 per hour")


def demo_limit() -> str:
    """Tight per-IP limit for the public, no-login demo endpoint."""
    return current_app.config.get("RATELIMIT_DEMO", "5 per day")


@login_manager.unauthorized_handler
def _unauthorized():
    if _wants_json():
        return jsonify({"error": "Authentication required", "code": "auth_required"}), 401
    return _redirect_to_login()


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app(config_object: type = Config) -> Flask:
    """Build and configure the Auto-CV Flask application."""
    ensure_instance_dir()

    app = Flask(
        __name__,
        static_folder=str(_STATIC_DIR),
        template_folder=str(_TEMPLATE_DIR),
    )
    app.config.from_object(config_object)

    # Behind a reverse proxy / load balancer (the normal public deployment),
    # trust the proxy's forwarded headers so the real client IP reaches the rate
    # limiter and request.is_secure reflects the external HTTPS scheme. The hop
    # count is configurable: set it to the number of proxies in front of the app.
    _proxy_hops = int(os.environ.get("PROXY_FIX_HOPS", "0"))
    if _proxy_hops > 0:
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=_proxy_hops, x_proto=_proxy_hops, x_host=_proxy_hops
        )

    # CORS is only enabled when explicit origins are configured. For a
    # same-origin app it should stay off; allowing arbitrary origins with
    # cookies is unsafe.
    _cors_origins = os.environ.get("CORS_ORIGINS", "").strip()
    if _cors_origins:
        CORS(app, resources={r"/api/*": {"origins": _cors_origins.split(",")}},
             supports_credentials=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    if migrate is not None:
        migrate.init_app(app, db)
    if app.config.get("RATELIMIT_ENABLED", True):
        limiter.init_app(app)
        # In-memory limit storage doesn't survive restarts and isn't shared across
        # worker processes/instances, so limits effectively don't hold in a real
        # multi-worker deployment. Warn loudly; production should set REDIS_URL.
        if app.config.get("IS_PRODUCTION") and str(
            app.config.get("RATELIMIT_STORAGE_URI", "")
        ).startswith("memory://"):
            app.logger.warning(
                "Rate-limit storage is in-memory in production; limits won't hold "
                "across workers/restarts. Set RATELIMIT_STORAGE_URI (e.g. a redis:// URL)."
            )

    login_manager.login_view = "auth.login"
    login_manager.session_protection = "strong"

    # Import models so tables register on the metadata, then create them.
    from . import models  # noqa: F401  (must follow db.init_app)
    from .auth import auth_bp
    from .workspace import workspace_bp
    from .features import features_bp
    from .account import account_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(workspace_bp)
    app.register_blueprint(features_bp)
    app.register_blueprint(account_bp)

    with app.app_context():
        try:
            db.create_all()
        except Exception:
            if _should_fail_on_db_init(app):
                raise
            app.logger.exception(
                "Database initialization failed during startup; continuing so "
                "public routes can still respond. Set DATABASE_URL to a valid "
                "database; set AUTO_CREATE_DB=1 if startup should fail on "
                "database initialization errors."
            )

    _configure_observability(app)
    _register_error_handlers(app)
    _register_routes(app)

    return app


def _should_fail_on_db_init(app: Flask) -> bool:
    """Keep local/test failures loud; let serverless deploys boot for diagnostics."""
    if app.config.get("TESTING"):
        return True
    if os.environ.get("AUTO_CREATE_DB", "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    return not (os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))


# ---------------------------------------------------------------------------
# Observability (optional, env-gated): error tracking + log level
# ---------------------------------------------------------------------------


def _configure_observability(app: Flask) -> None:
    if not app.debug:
        app.logger.setLevel(logging.INFO)

    _sentry_dsn = os.environ.get("SENTRY_DSN", "").strip()
    if _sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration

            sentry_sdk.init(
                dsn=_sentry_dsn,
                integrations=[FlaskIntegration()],
                traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
                send_default_pii=False,  # don't ship user PII to the error tracker
            )
            app.logger.info("Sentry error tracking enabled.")
        except Exception as exc:  # noqa: BLE001 - never let telemetry break boot
            app.logger.warning("SENTRY_DSN is set but Sentry init failed: %s", exc)


# ---------------------------------------------------------------------------
# Security headers, auth boundary, and sanitized error handling
# ---------------------------------------------------------------------------


def _register_error_handlers(app: Flask) -> None:
    @app.after_request
    def set_security_headers(response):
        """Baseline security headers safe for the CDN-based frontend."""
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        if app.config.get("IS_PRODUCTION"):
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    @app.errorhandler(400)
    def _bad_request(e):
        return jsonify({"error": "Bad request."}), 400

    @app.errorhandler(401)
    def _unauth(e):
        if _wants_json():
            return jsonify({"error": "Authentication required", "code": "auth_required"}), 401
        return _redirect_to_login()

    @app.errorhandler(403)
    def _forbidden(e):
        return jsonify({"error": "You do not have access to this resource."}), 403

    @app.errorhandler(413)
    def _too_large(e):
        mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return jsonify({"error": f"Upload too large. Maximum size is {mb} MB."}), 413

    @app.errorhandler(429)
    def _rate_limited(e):
        return jsonify({"error": "Too many requests. Please slow down and try again."}), 429

    @app.errorhandler(500)
    def _internal(e):
        return jsonify({"error": "Something went wrong. Please try again."}), 500


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def _register_routes(app: Flask) -> None:
    # --- Pages -------------------------------------------------------------

    @app.route("/")
    def index():
        """Render the optimizer/landing page.

        Public so visitors can see the product and value proposition before
        signing up (widening the funnel). Heavy actions still require auth and
        prompt login; anonymous visitors can also try the capped ``/demo``.
        """
        return render_template("index.html")

    @app.route("/interview")
    @login_required
    def interview():
        """Render the interview preparation page."""
        return render_template("interview.html")

    @app.route("/how-it-works")
    def how_it_works():
        """Render the guided product workflow page (public explainer)."""
        return render_template("how_it_works.html")

    @app.route("/demo")
    def demo_page():
        """Public, no-login taste of the optimizer."""
        return render_template("demo.html")

    @app.route("/workspace")
    @login_required
    def workspace_page():
        """Render the saved-jobs / CV-history workspace."""
        return render_template("workspace.html")

    # Legal pages are public (linked from auth pages and the footer) so visitors
    # can read them before creating an account.
    @app.route("/privacy")
    def privacy():
        return render_template("privacy.html", updated="2026-05-24")

    @app.route("/terms")
    def terms():
        return render_template("terms.html", updated="2026-05-24")

    # --- Interview API -----------------------------------------------------

    @app.route("/api/interview/questions", methods=["POST"])
    @login_required
    @limiter.limit(llm_limit)
    def interview_questions():
        """Generate interview questions grounded in the CV and the job offer."""
        try:
            data = request.get_json() or {}
            cv_latex = data.get("cv_latex", "")
            job_description = data.get("job_description") or data.get("job_text") or ""

            if not cv_latex and not job_description:
                return jsonify({"error": "Provide a CV and/or a job description"}), 400

            result = interview_agent.generate_questions(
                cv_latex=cv_latex,
                job_description=job_description,
                level=data.get("level"),
                domains=data.get("domains"),
                count=data.get("count", 6),
                extra_instructions=data.get("extra_instructions"),
                session_goal=data.get("session_goal"),
            )
            return jsonify({"success": True, **result})
        except Exception as e:  # noqa: BLE001
            return _server_error(e)

    @app.route("/api/interview/review", methods=["POST"])
    @login_required
    @limiter.limit(llm_limit)
    def interview_review():
        """Review a candidate's answer/code for a single interview question."""
        try:
            data = request.get_json() or {}
            question = data.get("question")
            answer = data.get("answer", "")

            if not question:
                return jsonify({"error": "No question provided"}), 400

            result = interview_agent.review_answer(
                question=question,
                answer=answer,
                language=data.get("language", ""),
                job_description=data.get("job_description") or data.get("job_text") or "",
            )
            return jsonify({"success": True, "review": result})
        except Exception as e:  # noqa: BLE001
            return _server_error(e)

    # --- Job + CV optimization API ----------------------------------------

    @app.route("/api/parse-job", methods=["POST"])
    @login_required
    @limiter.limit(llm_limit)
    def parse_job():
        """Parse a job description and extract information.

        Requires auth: parsing runs an LLM call, so leaving it open let anyone
        burn the app's LLM budget. Anonymous visitors use the capped
        ``/api/demo`` flow.
        """
        try:
            data = request.get_json()
            text = data.get("text", "")

            if not text:
                return jsonify({"error": "No job description provided"}), 400

            result = parse_job_description(text)
            return jsonify({
                "success": True,
                "text": text,
                "raw_text": result.get("raw_text", text),
                "skills": result.get("skills", []),
                "requirements": result.get("requirements", []),
                "qualifications": result.get("qualifications", []),
                "company_info": result.get("company_info", {}),
                "sections": result.get("sections", {}),
            })
        except Exception as e:  # noqa: BLE001
            return _server_error(e)

    @app.route("/api/analyze-cv", methods=["POST"])
    @login_required
    @limiter.limit(llm_limit)
    def analyze_cv_endpoint():
        """Analyze a CV against a job description."""
        try:
            data = request.get_json()
            cv_latex = data.get("cv_latex", "")
            job_description = data.get("job_description", {})

            if not cv_latex:
                return jsonify({"error": "No CV provided"}), 400
            if not job_description:
                return jsonify({"error": "No job description provided"}), 400

            result = analyze_cv(cv_latex, job_description)
            return jsonify({"success": True, "analysis": result})
        except Exception as e:  # noqa: BLE001
            return _server_error(e)

    @app.route("/api/optimize-cv", methods=["POST"])
    @login_required
    @limiter.limit(llm_limit)
    def optimize_cv_endpoint():
        """Optimize a CV for a specific job."""
        try:
            data = request.get_json()
            cv_latex = data.get("cv_latex", "")
            job_description = data.get("job_description", {})
            language = data.get("language") or "en"

            if not cv_latex:
                return jsonify({"error": "No CV provided"}), 400
            if not job_description:
                return jsonify({"error": "No job description provided"}), 400

            print("[optimize-cv] request received — running analysis + section rewrites…", flush=True)
            _t0 = datetime.now()
            result = optimize_cv_for_job(cv_latex, job_description, language=language)
            print(f"[optimize-cv] done in {(datetime.now() - _t0).total_seconds():.1f}s", flush=True)

            return jsonify({
                "success": True,
                "analysis": result["analysis"],
                "optimized_latex": result["optimized_latex"],
                "rewritten_sections": result.get("rewritten_sections", []),
                "proposed_additions": result.get("proposed_additions", []),
                "section_diffs": result.get("section_diffs", []),
            })
        except Exception as e:  # noqa: BLE001
            return _server_error(e)

    @app.route("/api/render-latex", methods=["POST"])
    @login_required
    @limiter.limit(llm_limit)
    def render_latex():
        """Render LaTeX to PDF, silently auto-repairing compilation errors via LLM."""
        try:
            data = request.get_json() or {}
            latex_content = data.get("latex", "")

            if not latex_content:
                return jsonify({"error": "No LaTeX content provided"}), 400

            try:
                result = latex_repair.render_pdf(latex_content)
            except FileNotFoundError:
                return jsonify({
                    "error": "pdflatex not found. Please install a LaTeX distribution."
                }), 500

            if not result.success:
                return jsonify({
                    "error": "LaTeX compilation failed",
                    "details": result.error_details or "The document could not be compiled.",
                }), 500

            response = send_file(
                BytesIO(result.pdf_bytes),
                mimetype="application/pdf",
                as_attachment=True,
                download_name=f'cv_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf',
            )
            response.headers["X-Latex-Repaired"] = "true" if result.repaired else "false"
            if result.repaired:
                encoded = base64.b64encode(result.final_latex.encode("utf-8")).decode("ascii")
                if len(encoded) < 60000:
                    response.headers["X-Corrected-Latex"] = encoded
            return response
        except Exception as e:  # noqa: BLE001
            return _server_error(e)

    # --- Diagnostics + samples --------------------------------------------

    @app.route("/api/llm/health", methods=["GET"])
    def llm_health():
        """Report the active LLM provider/model (never exposes the API key)."""
        return jsonify({
            "success": True,
            "source": llm_client.active_source(),
            "config": llm_client.describe_config(),
        })

    @app.route("/api/demo", methods=["POST"])
    @limiter.limit(demo_limit)
    def demo_optimize():
        """Public, capped taste of the optimizer (no login).

        Analyzes a pasted job offer against the user's CV text — or a built-in
        sample CV if none is given — and returns the match breakdown. Editing
        and export stay behind sign-up. Tightly rate limited per IP to bound LLM
        cost.
        """
        try:
            data = request.get_json() or {}
            job_text = (data.get("job_text") or data.get("text") or "").strip()[:8000]
            provided_cv = (data.get("cv_latex") or data.get("cv") or "").strip()[:20000]
            if not job_text:
                return jsonify({"error": "Paste a job description to try the demo."}), 400

            cv_text = provided_cv or _DEMO_SAMPLE_CV
            parsed = parse_job_description(job_text)
            analysis = analyze_cv(cv_text, parsed)
            # Drop internal/bulky fields before returning to an anonymous client.
            analysis.pop("_cv_text", None)
            return jsonify({
                "success": True,
                "analysis": analysis,
                "used_sample_cv": not bool(provided_cv),
            })
        except Exception as e:  # noqa: BLE001
            return _server_error(e)

    @app.route("/api/sample-cv", methods=["GET"])
    def get_sample_cv():
        """Get a sample CV for testing."""
        return jsonify({"success": True, "cv": create_sample_cv()})

    @app.route("/api/sample-job", methods=["GET"])
    def get_sample_job():
        """Get a sample job description."""
        sample_job = {
            "text": """Senior Software Engineer - Tech Company, Inc.
Location: San Francisco, CA

About Us:
We are a fast-growing technology company building next-generation software solutions.

Job Description:
We are looking for an experienced Senior Software Engineer to join our team. You will be responsible for designing and implementing scalable web applications using modern technologies.

Requirements:
- 5+ years of experience with Python, JavaScript, and SQL
- Experience with React, Node.js, and Django
- Knowledge of AWS, Docker, and Kubernetes
- Strong problem-solving skills and ability to work in a team

Preferred Qualifications:
- Master's degree in Computer Science or related field
- Experience with machine learning frameworks
- Prior startup experience
        """,
            "skills": ["python", "javascript", "sql", "react", "node.js", "django", "aws", "docker", "kubernetes"],
            "requirements": [
                "5+ years of experience with Python, JavaScript, and SQL",
                "Experience with React, Node.js, and Django",
                "Knowledge of AWS, Docker, and Kubernetes",
                "Strong problem-solving skills and ability to work in a team",
            ],
            "qualifications": ["Master's degree in Computer Science or related field"],
        }
        return jsonify({"success": True, "job": sample_job})
