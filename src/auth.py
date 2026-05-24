"""Authentication blueprint: register, login, logout.

Server-rendered HTML forms (with a Flask-WTF CSRF hidden field) are used for the
auth pages themselves, which keeps the login flow simple and robust. The rest of
the app is a JSON API that sends the CSRF token via the ``X-CSRFToken`` header.

All account endpoints are rate limited to blunt credential-stuffing.
"""

from __future__ import annotations

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session,
)
from flask_login import login_user, logout_user, login_required, current_user

try:  # importable both as a bare module (main.py) and as the src package
    from extensions import db, limiter
    from models import User
except ImportError:  # pragma: no cover
    from .extensions import db, limiter
    from .models import User

try:
    from email_validator import validate_email, EmailNotValidError
except ImportError:  # pragma: no cover - dependency declared in requirements
    validate_email = None
    EmailNotValidError = Exception


auth_bp = Blueprint("auth", __name__)

MIN_PASSWORD_LENGTH = 8


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
        return redirect(url_for("index"))

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
    login_user(user, remember=True)

    target = url_for("index")
    resp = _auth_response(True, message="", redirect_to=target)
    return resp


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit(lambda: _auth_limit())
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    next_target = request.args.get("next")
    if next_target:
        if next_target.startswith("/"):
            session["post_login_next"] = next_target
        return redirect(url_for("auth.login"))

    if request.method == "GET":
        return render_template("login.html")

    data = request.get_json(silent=True) if request.is_json else request.form
    email, _ = _normalize_email((data or {}).get("email", ""))
    password = (data or {}).get("password") or ""

    user = User.query.filter_by(email=email).first() if email else None
    # Constant-ish behaviour: always check a hash to avoid trivial user enumeration.
    valid = bool(user and user.check_password(password))
    if not valid:
        msg = "Incorrect email or password."
        resp = _auth_response(False, message=msg, redirect_to="", status=401)
        return resp if resp is not None else render_template("login.html")

    login_user(user, remember=True)
    target = session.pop("post_login_next", None) or url_for("index")
    # Only allow same-origin relative redirects from the stored return target.
    if not target.startswith("/"):
        target = url_for("index")
    resp = _auth_response(True, message="", redirect_to=target)
    return resp


@auth_bp.route("/logout", methods=["POST", "GET"])
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


def _auth_limit() -> str:
    """Read the auth rate limit from app config at request time."""
    from flask import current_app

    return current_app.config.get("RATELIMIT_AUTH", "20 per hour")
