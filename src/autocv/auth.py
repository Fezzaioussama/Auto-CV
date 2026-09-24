"""Authentication blueprint: register, login, logout.

Server-rendered HTML forms (with a Flask-WTF CSRF hidden field) are used for the
auth pages themselves, which keeps the login flow simple and robust. The rest of
the app is a JSON API that sends the CSRF token via the ``X-CSRFToken`` header.

All account endpoints are rate limited to blunt credential-stuffing.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session,
    current_app,
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

try:  # importable both as a bare module (main.py) and as the src package
    from extensions import db, limiter
    from models import User
    import email_utils
    from tokens import make_token, read_token, PURPOSE_RESET, PURPOSE_VERIFY
except ImportError:  # pragma: no cover
    from .extensions import db, limiter
    from .models import User
    from . import email_utils
    from .tokens import make_token, read_token, PURPOSE_RESET, PURPOSE_VERIFY

try:
    from email_validator import validate_email, EmailNotValidError
except ImportError:  # pragma: no cover - dependency declared in requirements
    validate_email = None
    EmailNotValidError = Exception


auth_bp = Blueprint("auth", __name__)

MIN_PASSWORD_LENGTH = 8
# Hashed once at import so unknown-email logins cost the same as real ones.
_DUMMY_PASSWORD_HASH = generate_password_hash("autocv-timing-equalizer")


def _normalize_email(raw: str) -> tuple[str | None, str | None]:
    """Return (normalized_email, error). Uses email_validator when available."""
    email = (raw or "").strip().lower()
    if not email:
        return None, "Email is required."
    if validate_email is not None:
        try:
            # check_deliverability off: we don't want DNS lookups in the request path.
            result = validate_email(email, check_deliverability=False)
            return result.normalized.lower(), None
        except EmailNotValidError as exc:
            return None, str(exc)
    if "@" not in email or "." not in email.split("@")[-1]:
        return None, "Please enter a valid email address."
    return email, None


def _wants_json() -> bool:
    """True only for genuine API/JSON clients, not browser form posts.

    A browser sends ``Accept: text/html,...,*/*`` and Werkzeug's wildcard
    matching makes a naive ``"application/json" in accept_mimetypes`` test
    return True — which would wrongly return JSON to a form login and dump it
    on screen. So require either a JSON body or an Accept that prefers JSON
    over HTML (i.e. a fetch/XHR call), or an explicit XHR header.
    """
    if request.is_json:
        return True
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    accept = request.accept_mimetypes
    return accept.accept_json and not accept.accept_html


def _auth_response(ok: bool, *, message: str, redirect_to: str, status: int = 200):
    """Respond appropriately whether the caller is a browser form or JSON client."""
    if _wants_json():
        payload = {"success": ok}
        if ok:
            payload["user"] = current_user.to_dict() if current_user.is_authenticated else None
            payload["redirect"] = redirect_to
        else:
            payload["error"] = message
        return jsonify(payload), status if not ok else 200
    if not ok:
        flash(message, "error")
        return None  # caller re-renders the form
    return redirect(redirect_to)


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit(lambda: _auth_limit())
def register():
    if current_user.is_authenticated:
        return redirect(url_for("optimizer"))

    if request.method == "GET":
        return render_template("register.html")

    data = request.get_json(silent=True) if request.is_json else request.form
    email, err = _normalize_email((data or {}).get("email", ""))
    name = ((data or {}).get("name") or "").strip() or None
    password = (data or {}).get("password") or ""

    if err:
        resp = _auth_response(False, message=err, redirect_to="", status=400)
        return resp if resp is not None else render_template("register.html")
    if len(password) < MIN_PASSWORD_LENGTH:
        msg = f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        resp = _auth_response(False, message=msg, redirect_to="", status=400)
        return resp if resp is not None else render_template("register.html")
    if User.query.filter_by(email=email).first():
        msg = "An account with this email already exists."
        resp = _auth_response(False, message=msg, redirect_to="", status=409)
        return resp if resp is not None else render_template("register.html")

    user = User(email=email, name=name)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    _send_verification(user)

    # When verification is mandatory, don't sign the user in yet — make them
    # confirm first. Otherwise keep the frictionless "register and you're in"
    # flow, with a UI banner nudging them to confirm.
    if current_app.config.get("REQUIRE_EMAIL_VERIFICATION"):
        msg = "Account created. Check your email to confirm it before signing in."
        if _wants_json():
            return jsonify({"success": True, "verify_required": True, "message": msg,
                            "redirect": url_for("auth.login")})
        flash(msg, "info")
        return redirect(url_for("auth.login"))

    login_user(user, remember=True)
    target = url_for("optimizer")
    resp = _auth_response(True, message="", redirect_to=target)
    return resp


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit(lambda: _auth_limit())
def login():
    if current_user.is_authenticated:
        return redirect(url_for("optimizer"))

    next_target = request.args.get("next")
    if next_target:
        if _safe_return_path(next_target):
            session["post_login_next"] = next_target
        return redirect(url_for("auth.login"))

    if request.method == "GET":
        return render_template("login.html")

    data = request.get_json(silent=True) if request.is_json else request.form
    email, _ = _normalize_email((data or {}).get("email", ""))
    password = (data or {}).get("password") or ""

    user = User.query.filter_by(email=email).first() if email else None
    # Constant-ish behaviour: always check a hash to avoid trivial user enumeration.
    if user is None:
        check_password_hash(_DUMMY_PASSWORD_HASH, password)
    valid = bool(user and user.check_password(password))
    if not valid:
        msg = "Incorrect email or password."
        resp = _auth_response(False, message=msg, redirect_to="", status=401)
        return resp if resp is not None else render_template("login.html")

    if current_app.config.get("REQUIRE_EMAIL_VERIFICATION") and not user.email_verified:
        msg = "Please confirm your email before signing in. Check your inbox or request a new link."
        resp = _auth_response(False, message=msg, redirect_to="", status=403)
        return resp if resp is not None else render_template("login.html")

    login_user(user, remember=True)
    target = session.pop("post_login_next", None) or url_for("optimizer")
    # Only allow same-origin relative redirects from the stored return target.
    if not _safe_return_path(target):
        target = url_for("optimizer")
    resp = _auth_response(True, message="", redirect_to=target)
    return resp


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    if _wants_json():
        return jsonify({"success": True})
    return redirect(url_for("auth.login"))


@auth_bp.route("/api/me", methods=["GET"])
def me():
    """Lightweight identity check used by the frontend to render nav state."""
    if current_user.is_authenticated:
        return jsonify({"authenticated": True, "user": current_user.to_dict()})
    return jsonify({"authenticated": False, "user": None})


# ---------------------------------------------------------------------------
# Email verification + password reset (signed, expiring links — see tokens.py)
# ---------------------------------------------------------------------------


def _safe_return_path(target: str) -> bool:
    return (
        isinstance(target, str) and target.startswith("/")
        and not target.startswith("//") and "\\" not in target
        and not any(ord(char) < 32 or ord(char) == 127 for char in target)
        and not urlsplit(target).netloc
    )


def _external_url(endpoint: str, **values) -> str:
    """Absolute URL for an email link, honoring PUBLIC_BASE_URL when set."""
    base = (current_app.config.get("PUBLIC_BASE_URL") or "").rstrip("/")
    if base:
        return base + url_for(endpoint, **values)
    if current_app.config.get("IS_PRODUCTION", True):
        raise RuntimeError("PUBLIC_BASE_URL is required for production email links")
    return url_for(endpoint, _external=True, **values)


def _send_verification(user: User) -> None:
    """Mail a fresh email-confirmation link to ``user`` (best effort)."""
    token = make_token(PURPOSE_VERIFY, user.id)
    email_utils.send_email_verification(
        user.email, _external_url("auth.verify_email", token=token)
    )


def _reset_user_from_token(token: str):
    """Resolve a reset token to its user, binding it to the current password.

    The token payload carries a slice of the password hash, so it is **single
    use**: once the password changes (or was already changed), the slice no
    longer matches and the link stops working.
    """
    payload = read_token(
        PURPOSE_RESET, token, max_age=current_app.config["RESET_TOKEN_MAX_AGE"]
    )
    if not isinstance(payload, dict):
        return None
    user = db.session.get(User, payload.get("uid"))
    if user is None or payload.get("h") != user.password_hash[-20:]:
        return None
    return user


@auth_bp.route("/verify-email/<token>", methods=["GET"])
def verify_email(token):
    user_id = read_token(
        PURPOSE_VERIFY, token, max_age=current_app.config["VERIFY_TOKEN_MAX_AGE"]
    )
    user = db.session.get(User, user_id) if user_id else None
    if user is None:
        flash("That confirmation link is invalid or has expired.", "error")
        return redirect(url_for("auth.login"))
    if not user.email_verified:
        user.email_verified = True
        user.verified_at = datetime.utcnow()
        db.session.commit()
    flash("Email confirmed — you're all set.", "info")
    return redirect(url_for("optimizer") if current_user.is_authenticated else url_for("auth.login"))


@auth_bp.route("/resend-verification", methods=["POST"])
@login_required
@limiter.limit(lambda: _auth_limit())
def resend_verification():
    if current_user.email_verified:
        return jsonify({"success": True, "message": "Email already confirmed."})
    _send_verification(current_user)
    if _wants_json():
        return jsonify({"success": True, "message": "Confirmation email sent."})
    flash("Confirmation email sent.", "info")
    return redirect(url_for("optimizer"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit(lambda: _auth_limit())
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("optimizer"))
    if request.method == "GET":
        return render_template("forgot_password.html")

    data = request.get_json(silent=True) if request.is_json else request.form
    email, _ = _normalize_email((data or {}).get("email", ""))
    user = User.query.filter_by(email=email).first() if email else None
    if user is not None:
        token = make_token(PURPOSE_RESET, {"uid": user.id, "h": user.password_hash[-20:]})
        email_utils.send_password_reset(
            user.email, _external_url("auth.reset_password", token=token)
        )
    # Same response whether or not the email exists — no account enumeration.
    msg = "If that email has an account, a reset link is on its way."
    if _wants_json():
        return jsonify({"success": True, "message": msg})
    flash(msg, "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit(lambda: _auth_limit())
def reset_password(token):
    user = _reset_user_from_token(token)
    if user is None:
        flash("That reset link is invalid or has expired. Request a new one.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "GET":
        return render_template("reset_password.html", token=token)

    data = request.get_json(silent=True) if request.is_json else request.form
    password = (data or {}).get("password") or ""
    if len(password) < MIN_PASSWORD_LENGTH:
        msg = f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        if _wants_json():
            return jsonify({"success": False, "error": msg}), 400
        flash(msg, "error")
        return render_template("reset_password.html", token=token)

    user.set_password(password)
    # A reset must boot any sessions opened with the old password (e.g. an
    # attacker who knew it): rotate the per-user token so every existing
    # session/remember cookie for this account stops validating.
    user.rotate_session_token()
    db.session.commit()  # invalidates the (hash-bound) token — single use
    msg = "Password updated. You can sign in now."
    if _wants_json():
        return jsonify({"success": True, "message": msg, "redirect": url_for("auth.login")})
    flash(msg, "info")
    return redirect(url_for("auth.login"))


def _auth_limit() -> str:
    """Read the auth rate limit from app config at request time."""
    return current_app.config.get("RATELIMIT_AUTH", "20 per hour")
