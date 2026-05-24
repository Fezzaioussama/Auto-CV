"""Per-user workspace API: saved jobs, CV documents, and version history.

Every endpoint is ``@login_required`` and scoped to ``current_user``; ownership
is enforced through :func:`_owned` so a user can never read or mutate another
account's data even by guessing IDs.
"""

from __future__ import annotations

from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user

try:  # importable both as a bare module (main.py) and as the src package
    from extensions import db
    from models import Job, CVDocument, CVVersion, CoverLetter
except ImportError:  # pragma: no cover
    from .extensions import db
    from .models import Job, CVDocument, CVVersion, CoverLetter


workspace_bp = Blueprint("workspace", __name__)


def _owned(model, obj_id):
    """Fetch a row by id and 404 unless it belongs to the current user."""
    obj = db.session.get(model, obj_id)
    if obj is None or getattr(obj, "user_id", None) != current_user.id:
        abort(404)
    return obj


def _owned_version(version_id):
    """Fetch a CVVersion and 404 unless its document belongs to the user."""
    version = db.session.get(CVVersion, version_id)
    if version is None or version.document is None or version.document.user_id != current_user.id:
        abort(404)
    return version


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


@workspace_bp.route("/api/jobs", methods=["GET"])
@login_required
def list_jobs():
    jobs = (
        Job.query.filter_by(user_id=current_user.id)
        .order_by(Job.created_at.desc())
        .all()
    )
    return jsonify({"success": True, "jobs": [j.to_dict() for j in jobs]})


@workspace_bp.route("/api/jobs", methods=["POST"])
@login_required
def create_job():
    data = request.get_json() or {}
    raw_text = (data.get("raw_text") or data.get("text") or "").strip()
    if not raw_text:
        return jsonify({"error": "Job text is required."}), 400

    job = Job(
        user_id=current_user.id,
        title=(data.get("title") or "").strip() or None,
        company=(data.get("company") or "").strip() or None,
        raw_text=raw_text,
        parsed=data.get("parsed"),
        language=(data.get("language") or "en")[:8],
    )
    db.session.add(job)
    db.session.commit()
    return jsonify({"success": True, "job": job.to_dict(include_text=True)}), 201


@workspace_bp.route("/api/jobs/<int:job_id>", methods=["GET"])
@login_required
def get_job(job_id):
    job = _owned(Job, job_id)
    return jsonify({"success": True, "job": job.to_dict(include_text=True)})


@workspace_bp.route("/api/jobs/<int:job_id>", methods=["DELETE"])
@login_required
def delete_job(job_id):
    job = _owned(Job, job_id)
    db.session.delete(job)
    db.session.commit()
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# CV documents + version history
# ---------------------------------------------------------------------------


@workspace_bp.route("/api/cv", methods=["GET"])
@login_required
def list_cvs():
    cvs = (
        CVDocument.query.filter_by(user_id=current_user.id)
        .order_by(CVDocument.updated_at.desc())
        .all()
    )
    return jsonify({"success": True, "documents": [c.to_dict() for c in cvs]})


@workspace_bp.route("/api/cv", methods=["POST"])
@login_required
def create_cv():
    data = request.get_json() or {}
    latex = (data.get("latex") or "").strip()
    if not latex:
        return jsonify({"error": "CV content (latex) is required."}), 400

    doc = CVDocument(
        user_id=current_user.id,
        name=(data.get("name") or "My CV").strip()[:255],
        source_format=(data.get("source_format") or "latex")[:16],
    )
    db.session.add(doc)
    db.session.flush()  # assign doc.id before creating the first version

    version = CVVersion(
        document_id=doc.id,
        job_id=data.get("job_id"),
        label=(data.get("label") or "Initial version")[:255],
        latex=latex,
        analysis=data.get("analysis"),
        template=data.get("template"),
        language=(data.get("language") or "en")[:8],
    )
    db.session.add(version)
    db.session.commit()
    return jsonify({"success": True, "document": doc.to_dict(include_versions=True)}), 201


@workspace_bp.route("/api/cv/<int:doc_id>", methods=["GET"])
@login_required
def get_cv(doc_id):
    doc = _owned(CVDocument, doc_id)
    return jsonify({"success": True, "document": doc.to_dict(include_versions=True)})


@workspace_bp.route("/api/cv/<int:doc_id>", methods=["DELETE"])
@login_required
def delete_cv(doc_id):
    doc = _owned(CVDocument, doc_id)
    db.session.delete(doc)
    db.session.commit()
    return jsonify({"success": True})


@workspace_bp.route("/api/cv/<int:doc_id>/versions", methods=["POST"])
@login_required
def add_version(doc_id):
    doc = _owned(CVDocument, doc_id)
    data = request.get_json() or {}
    latex = (data.get("latex") or "").strip()
    if not latex:
        return jsonify({"error": "Version content (latex) is required."}), 400

    version = CVVersion(
        document_id=doc.id,
        job_id=data.get("job_id"),
        label=(data.get("label") or "New version")[:255],
        latex=latex,
        analysis=data.get("analysis"),
        template=data.get("template"),
        language=(data.get("language") or "en")[:8],
    )
    db.session.add(version)
    # Touch the parent so "recently updated" ordering is meaningful.
    doc.name = doc.name
    db.session.commit()
    return jsonify({"success": True, "version": version.to_dict(include_latex=True)}), 201


@workspace_bp.route("/api/cv/versions/<int:version_id>", methods=["GET"])
@login_required
def get_version(version_id):
    version = _owned_version(version_id)
    return jsonify({"success": True, "version": version.to_dict(include_latex=True)})


@workspace_bp.route("/api/cv/versions/<int:version_id>", methods=["DELETE"])
@login_required
def delete_version(version_id):
    version = _owned_version(version_id)
    db.session.delete(version)
    db.session.commit()
    return jsonify({"success": True})


@workspace_bp.route("/api/cv/versions/<int:version_id>/restore", methods=["POST"])
@login_required
def restore_version(version_id):
    """Restore an old version by appending a new version with its content."""
    version = _owned_version(version_id)
    restored = CVVersion(
        document_id=version.document_id,
        job_id=version.job_id,
        label=f"Restored from version #{version.id}",
        latex=version.latex,
        analysis=version.analysis,
        template=version.template,
        language=version.language,
    )
    db.session.add(restored)
    db.session.commit()
    return jsonify({"success": True, "version": restored.to_dict(include_latex=True)}), 201


# ---------------------------------------------------------------------------
# Cover letters (created by features.py, listed here)
# ---------------------------------------------------------------------------


@workspace_bp.route("/api/cover-letters", methods=["GET"])
@login_required
def list_cover_letters():
    query = CoverLetter.query.filter_by(user_id=current_user.id)
    job_id = request.args.get("job_id", type=int)
    if job_id:
        query = query.filter_by(job_id=job_id)
    letters = query.order_by(CoverLetter.created_at.desc()).all()
    return jsonify({"success": True, "cover_letters": [c.to_dict() for c in letters]})
