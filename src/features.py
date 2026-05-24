"""Feature endpoints: file ingestion, templates, and cover-letter generation.

Grouped into one blueprint so ``main.py`` registers a single object. Everything
here that costs money or runs heavy work is ``@login_required`` and rate
limited; results can optionally be persisted to the user's workspace.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

from flask import Blueprint, request, jsonify, current_app, send_file
from flask_login import login_required, current_user

try:  # importable both as a bare module (main.py) and as the src package
    from extensions import db, limiter
    from models import CoverLetter
    import file_extract
    import cv_templates
    import cv_export
    import web_fetch
    import cover_letter as cover_letter_mod
except ImportError:  # pragma: no cover
    from .extensions import db, limiter
    from .models import CoverLetter
    from . import file_extract
    from . import cv_templates
    from . import cv_export
    from . import web_fetch
    from . import cover_letter as cover_letter_mod


features_bp = Blueprint("features", __name__)


def _llm_limit() -> str:
    return current_app.config.get("RATELIMIT_LLM", "40 per hour")


def _allowed(filename: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config.get("ALLOWED_UPLOAD_EXTENSIONS", set())


@features_bp.route("/api/templates", methods=["GET"])
def templates():
    """List available CV templates (public — used to populate the picker)."""
    return jsonify({"success": True, "templates": cv_templates.list_templates()})


@features_bp.route("/api/extract-cv", methods=["POST"])
@login_required
@limiter.limit(_llm_limit)
def extract_cv():
    """Accept a PDF/DOCX/TXT/TEX upload and return text + a LaTeX document."""
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify({"error": "No file uploaded."}), 400
    if not _allowed(file.filename):
        allowed = ", ".join(sorted(current_app.config["ALLOWED_UPLOAD_EXTENSIONS"]))
        return jsonify({"error": f"Unsupported file type. Allowed: {allowed}."}), 400

    template = request.form.get("template") or cv_templates.DEFAULT_TEMPLATE
    language = (request.form.get("language") or "en")[:8]

    try:
        text, source_format = file_extract.extract_cv_text(file.filename, file.read())
    except file_extract.ExtractionError as exc:
        return jsonify({"error": str(exc)}), 422

    # .tex uploads are already LaTeX; everything else is converted.
    if source_format == "tex":
        latex = text
    else:
        latex = cv_templates.plain_text_to_latex(text, template, language)

    return jsonify({
        "success": True,
        "text": text,
        "latex": latex,
        "source_format": source_format,
    })


@features_bp.route("/api/apply-template", methods=["POST"])
@login_required
def apply_template():
    """Re-skin an existing CV with a different template's preamble."""
    data = request.get_json() or {}
    latex = (data.get("latex") or "").strip()
    template = data.get("template") or cv_templates.DEFAULT_TEMPLATE
    if not latex:
        return jsonify({"error": "No LaTeX provided."}), 400
    return jsonify({"success": True, "latex": cv_templates.apply_template(latex, template)})


@features_bp.route("/api/fetch-job-url", methods=["POST"])
@login_required
@limiter.limit(_llm_limit)
def fetch_job_url():
    """Fetch a job posting from a URL and return its text (SSRF-protected)."""
    data = request.get_json() or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "Provide a job posting URL."}), 400
    try:
        text = web_fetch.fetch_url_text(url)
    except web_fetch.FetchError as exc:
        return jsonify({"error": str(exc)}), 422
    return jsonify({"success": True, "text": text, "url": url})


@features_bp.route("/api/export", methods=["POST"])
@login_required
def export_cv():
    """Export the current CV (LaTeX) as a Word (.docx) or plain-text file.

    Recruiters and job portals usually want Word or text rather than LaTeX/PDF,
    so this converts the tailored CV without needing a LaTeX toolchain.
    """
    data = request.get_json() or {}
    latex = (data.get("latex") or data.get("cv_latex") or "").strip()
    fmt = (data.get("format") or "docx").lower()
    if not latex:
        return jsonify({"error": "No CV content to export."}), 400

    try:
        content, mimetype, ext = cv_export.export_cv(latex, fmt)
    except cv_export.ExportError as exc:
        return jsonify({"error": str(exc)}), 422

    filename = f"cv_{datetime.now():%Y%m%d_%H%M%S}.{ext}"
    return send_file(
        BytesIO(content), mimetype=mimetype, as_attachment=True, download_name=filename
    )


@features_bp.route("/api/cover-letter", methods=["POST"])
@login_required
@limiter.limit(_llm_limit)
def cover_letter():
    """Generate cover letter / recruiter / LinkedIn / email outreach text."""
    data = request.get_json() or {}
    cv = data.get("cv_latex") or data.get("cv") or ""
    job_description = data.get("job_description") or data.get("job_text") or ""
    kinds = data.get("kinds") or ["cover_letter"]
    language = (data.get("language") or "en")[:8]
    applicant_name = (data.get("applicant_name") or current_user.name or "").strip()

    if not cv and not job_description:
        return jsonify({"error": "Provide a CV and a job description."}), 400

    results = cover_letter_mod.generate_outreach(
        cv,
        job_description,
        kinds=kinds,
        language=language,
        applicant_name=applicant_name,
    )

    # Optionally persist to the workspace (tied to a saved job when given).
    if data.get("save"):
        job_id = data.get("job_id")
        for kind, content in results.items():
            db.session.add(CoverLetter(
                user_id=current_user.id,
                job_id=job_id,
                cv_version_id=data.get("cv_version_id"),
                kind=kind,
                content=content,
                language=language,
            ))
        db.session.commit()

    return jsonify({"success": True, "results": results})
