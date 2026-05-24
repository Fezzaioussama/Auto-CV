"""
Main application entry point for Auto-CV Flask app.

This wires together the public-web-app foundation (config, database, accounts,
CSRF, rate limiting, security headers) and the feature endpoints (job parsing,
CV optimization, PDF rendering, interview prep, cover letters, file ingestion,
and the per-user workspace).
"""

import os
import sys
import base64
import traceback
from io import BytesIO
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    send_file,
    jsonify,
    redirect,
    url_for,
    session,
)
from flask_cors import CORS
from flask_login import login_required, current_user

# src/ is importable as bare modules (kept from the original layout).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from config import Config, ensure_instance_dir
from extensions import db, login_manager, csrf, limiter

import llm_client  # loads .env and centralizes provider/model selection
import latex_repair  # compile + LLM auto-repair of LaTeX
from parser import parse_job_description
from matcher import analyze_cv, optimize_cv_for_job
from latex_gen import render_cv, create_sample_cv  # noqa: F401 (render_cv used elsewhere)
import interview_agent


# ---------------------------------------------------------------------------
# App + extension wiring
# ---------------------------------------------------------------------------

ensure_instance_dir()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config.from_object(Config)

# CORS is only enabled when explicit origins are configured. For a same-origin
# app it should stay off; allowing arbitrary origins with cookies is unsafe.
_cors_origins = os.environ.get("CORS_ORIGINS", "").strip()
if _cors_origins:
    CORS(app, resources={r"/api/*": {"origins": _cors_origins.split(",")}},
         supports_credentials=True)

db.init_app(app)
login_manager.init_app(app)
csrf.init_app(app)
if app.config.get("RATELIMIT_ENABLED", True):
    limiter.init_app(app)

login_manager.login_view = "auth.login"
login_manager.session_protection = "strong"

# Import models so tables register on the metadata, then create them.
import models  # noqa: E402  (must follow db.init_app)
from auth import auth_bp  # noqa: E402
from workspace import workspace_bp  # noqa: E402
from features import features_bp  # noqa: E402

app.register_blueprint(auth_bp)
app.register_blueprint(workspace_bp)
app.register_blueprint(features_bp)

with app.app_context():
    db.create_all()


def llm_limit() -> str:
    """Per-request resolution of the tighter limit for expensive endpoints."""
    return app.config.get("RATELIMIT_LLM", "40 per hour")


# ---------------------------------------------------------------------------
# Security headers, auth boundary, and sanitized error handling
# ---------------------------------------------------------------------------


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


def _wants_json() -> bool:
    return request.path.startswith("/api/") or request.is_json


def _redirect_to_login():
    session["post_login_next"] = request.full_path if request.query_string else request.path
    return redirect(url_for("auth.login"))


@login_manager.unauthorized_handler
def _unauthorized():
    if _wants_json():
        return jsonify({"error": "Authentication required", "code": "auth_required"}), 401
    return _redirect_to_login()


def _server_error(exc: Exception):
    """Log the real error server-side; return a generic message to the client."""
    app.logger.error("Unhandled error on %s: %s", request.path, exc)
    app.logger.debug("%s", traceback.format_exc())
    return jsonify({"error": "Something went wrong. Please try again."}), 500


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
# Pages
# ---------------------------------------------------------------------------


@app.route("/")
@login_required
def index():
    """Render the authenticated optimizer workspace."""
    return render_template("index.html")


@app.route("/interview")
@login_required
def interview():
    """Render the interview preparation page."""
    return render_template("interview.html")


@app.route("/how-it-works")
@login_required
def how_it_works():
    """Render the guided product workflow page."""
    return render_template("how_it_works.html")


@app.route("/workspace")
@login_required
def workspace_page():
    """Render the saved-jobs / CV-history workspace."""
    return render_template("workspace.html")


# ---------------------------------------------------------------------------
# Interview API
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Job + CV optimization API
# ---------------------------------------------------------------------------


@app.route("/api/parse-job", methods=["POST"])
@limiter.limit(llm_limit)
def parse_job():
    """Parse a job description and extract information."""
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


# ---------------------------------------------------------------------------
# Diagnostics + samples
# ---------------------------------------------------------------------------


@app.route("/api/llm/health", methods=["GET"])
def llm_health():
    """Report the active LLM provider/model (never exposes the API key)."""
    return jsonify({
        "success": True,
        "source": llm_client.active_source(),
        "config": llm_client.describe_config(),
    })


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


if __name__ == "__main__":
    print(f"[startup] {llm_client.describe_config()}", flush=True)
    # Debug is sourced from config (FLASK_DEBUG), defaulting to OFF for safety.
    app.run(debug=app.config.get("DEBUG", False), host="0.0.0.0", port=5000)
