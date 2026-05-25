"""Account self-service: change password / email, export data, delete account.

These back the ``/account`` page. The data-export and account-deletion
endpoints exist primarily to satisfy data-protection duties (GDPR right to
access and right to erasure) for an EU-facing public app: a user can download
everything we hold about them and permanently delete it themselves.

All endpoints are ``@login_required`` and scoped to ``current_user``. State
changes are JSON POSTs (CSRF token sent via the ``X-CSRFToken`` header, like the
rest of the API) and require the current password for sensitive actions.
"""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app
from flask_login import login_required, login_user, logout_user, current_user

try:  # importable both as a bare module (main.py) and as the src package
    from extensions import db, limiter
    from models import User, Job, CVDocument, CoverLetter
    import email_utils
    from tokens import make_token
    from tokens import PURPOSE_VERIFY
    from auth import _normalize_email, MIN_PASSWORD_LENGTH, _external_url
except ImportError:  # pragma: no cover
    from .extensions import db, limiter
    from .models import User, Job, CVDocument, CoverLetter
    from . import email_utils
    from .tokens import make_token, PURPOSE_VERIFY
    from .auth import _normalize_email, MIN_PASSWORD_LENGTH, _external_url


account_bp = Blueprint("account", __name__)


def _auth_limit() -> str:
    return current_app.config.get("RATELIMIT_AUTH", "20 per hour")


@account_bp.route("/account", methods=["GET"])
@login_required
def account_page():
    return render_template("account.html")


@account_bp.route("/api/account/password", methods=["POST"])
@login_required
@limiter.limit(_auth_limit)
def change_password():
    data = request.get_json() or {}
    current = data.get("current_password") or ""
    new = data.get("new_password") or ""

    if not current_user.check_password(current):
        return jsonify({"error": "Your current password is incorrect."}), 403
    if len(new) < MIN_PASSWORD_LENGTH:
        return jsonify({"error": f"New password must be at least {MIN_PASSWORD_LENGTH} characters."}), 400

    current_user.set_password(new)
    # Changing the password signs out every *other* session/device. Rotate the
    # token, then re-issue the current session with the new token so the user
    # who just changed their password stays logged in here.
    current_user.rotate_session_token()
    db.session.commit()
    login_user(current_user, remember=True)
    return jsonify({"success": True, "message": "Password updated. Other devices have been signed out."})


@account_bp.route("/api/account/logout-others", methods=["POST"])
@login_required
@limiter.limit(_auth_limit)
def logout_others():
    """Sign out of every other session/device, keeping the current one."""
    current_user.rotate_session_token()
    db.session.commit()
    # Re-issue this session with the fresh token so the caller stays logged in.
    login_user(current_user, remember=True)
    return jsonify({"success": True, "message": "Signed out of all other devices."})


@account_bp.route("/api/account/email", methods=["POST"])
@login_required
@limiter.limit(_auth_limit)
def change_email():
    data = request.get_json() or {}
    password = data.get("password") or ""
    new_email, err = _normalize_email(data.get("email", ""))

    if not current_user.check_password(password):
        return jsonify({"error": "Your password is incorrect."}), 403
    if err:
        return jsonify({"error": err}), 400
    if new_email == current_user.email:
        return jsonify({"error": "That is already your email address."}), 400
    if User.query.filter(User.email == new_email, User.id != current_user.id).first():
        return jsonify({"error": "That email is already in use."}), 409

    current_user.email = new_email
    current_user.email_verified = False
    current_user.verified_at = None
    db.session.commit()

    # Send a fresh confirmation link to the new address.
    token = make_token(PURPOSE_VERIFY, current_user.id)
    email_utils.send_email_verification(
        new_email, _external_url("auth.verify_email", token=token)
    )
    return jsonify({"success": True, "message": "Email updated. Check your inbox to confirm it.",
                    "email": new_email, "email_verified": False})


@account_bp.route("/api/account/export", methods=["GET"])
@login_required
def export_data():
    """Return everything we store about the user as a downloadable JSON file."""
    jobs = Job.query.filter_by(user_id=current_user.id).all()
    docs = CVDocument.query.filter_by(user_id=current_user.id).all()
    letters = CoverLetter.query.filter_by(user_id=current_user.id).all()

    payload = {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "account": {
            "email": current_user.email,
            "name": current_user.name,
            "email_verified": current_user.email_verified,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        },
        "jobs": [j.to_dict(include_text=True) for j in jobs],
        "cv_documents": [d.to_dict(include_versions=True) for d in docs],
        "cover_letters": [c.to_dict() for c in letters],
    }
    resp = jsonify(payload)
    resp.headers["Content-Disposition"] = (
        f"attachment; filename=auto-cv-export-{datetime.utcnow():%Y%m%d}.json"
    )
    return resp


@account_bp.route("/api/account/delete", methods=["POST"])
@login_required
@limiter.limit(_auth_limit)
def delete_account():
    """Permanently delete the account and all associated data (GDPR erasure)."""
    data = request.get_json() or {}
    if not current_user.check_password(data.get("password") or ""):
        return jsonify({"error": "Your password is incorrect."}), 403

    user = db.session.get(User, current_user.id)
    logout_user()
    # Relationships cascade (jobs, CV documents + versions, cover letters).
    db.session.delete(user)
    db.session.commit()
    return jsonify({"success": True, "message": "Your account and data have been deleted.",
                    "redirect": url_for("auth.login")})
