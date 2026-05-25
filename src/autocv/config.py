"""Application configuration for Auto-CV.

All deployment-sensitive behaviour is driven by environment variables (loaded
from the project-root ``.env``) so the same code runs safely as a local tool or
a public web app. Nothing here imports Flask app state, so it can be read from
anywhere without side effects.

The golden rules for a public deployment:

* ``FLASK_DEBUG`` defaults to **off** (the Werkzeug debugger is remote code
  execution if exposed).
* ``SECRET_KEY`` must be set in production; a dev-only fallback is generated and
  loudly warned about so sessions never silently use a shared key.
* Uploads and request bodies are size-capped (``MAX_CONTENT_LENGTH``).
* Session cookies are ``HttpOnly`` + ``SameSite`` and ``Secure`` in production.
"""

from __future__ import annotations

import os
import secrets
import sys

try:  # python-dotenv is a declared dependency; degrade gracefully if absent.
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - defensive only
    def load_dotenv(*_args, **_kwargs):  # type: ignore
        return False

# This file lives at <repo>/src/autocv/config.py, so the project root is three
# directories up (autocv -> src -> repo root).
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

# Where SQLite lives by default and where uploads are briefly written.
def _default_instance_dir() -> str:
    explicit = os.environ.get("INSTANCE_DIR", "").strip()
    if explicit:
        return explicit
    if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"):
        return os.path.join("/tmp", "autocv-instance")
    return os.path.join(_PROJECT_ROOT, "instance")


_INSTANCE_DIR = _default_instance_dir()


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip())
    except (TypeError, ValueError):
        return default


def _str(name: str, default: str) -> str:
    """Return the env var, treating unset OR empty as "use the default".

    This matters because a key left blank in .env (e.g. ``DATABASE_URL=``) sets
    the variable to an empty string, which must not override a real default.
    """
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else default


def _database_uri() -> str:
    default = f"sqlite:///{os.path.join(_INSTANCE_DIR, 'auto_cv.db')}"
    raw = os.environ.get("DATABASE_URL", "").strip()
    if not raw:
        return default
    if "..." in raw or "<" in raw or ">" in raw:
        print(
            "[config] WARNING: DATABASE_URL still contains a placeholder; "
            "falling back to local SQLite storage.",
            file=sys.stderr,
            flush=True,
        )
        return default
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+psycopg://", 1)
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw


def _is_production() -> bool:
    env = (os.environ.get("FLASK_ENV") or os.environ.get("APP_ENV") or "production").lower()
    # Default to production-safe behaviour; only "development"/"dev" relaxes it.
    return env not in {"development", "dev", "local", "test", "testing"}


def _resolve_secret_key() -> str:
    key = os.environ.get("SECRET_KEY", "").strip()
    if key:
        return key
    if _is_production():
        # In production a missing key is fatal: a generated key would invalidate
        # every session on restart and differ across workers.
        print(
            "[config] FATAL: SECRET_KEY is not set but the app is running in "
            "production mode. Set SECRET_KEY in your environment/.env.",
            file=sys.stderr,
            flush=True,
        )
        raise RuntimeError("SECRET_KEY must be set in production")
    print(
        "[config] WARNING: SECRET_KEY not set — generating an ephemeral dev key. "
        "Sessions will not survive a restart. Set SECRET_KEY for stable sessions.",
        flush=True,
    )
    return secrets.token_hex(32)


class Config:
    """Flask configuration resolved from the environment."""

    # --- Core / security ---------------------------------------------------
    DEBUG = _bool("FLASK_DEBUG", default=False)
    TESTING = False
    SECRET_KEY = _resolve_secret_key()

    # Cap request bodies (covers JSON payloads and file uploads).
    MAX_CONTENT_LENGTH = _int("MAX_CONTENT_LENGTH_MB", 8) * 1024 * 1024

    # Session cookie hardening.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = _str("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", default=_is_production())
    PERMANENT_SESSION_LIFETIME = _int("SESSION_LIFETIME_DAYS", 14) * 24 * 3600

    # CSRF: protect browser-originated state changes. The JSON API sends the
    # token via the X-CSRFToken header (see static/csrf.js).
    WTF_CSRF_ENABLED = _bool("WTF_CSRF_ENABLED", default=True)
    WTF_CSRF_TIME_LIMIT = None  # token valid for the session lifetime

    # --- Email confirmation + reset links ---------------------------------
    # When on, unverified accounts can register but not sign in until they
    # confirm their email. Off by default so dev/log-only email still works.
    REQUIRE_EMAIL_VERIFICATION = _bool("REQUIRE_EMAIL_VERIFICATION", default=False)
    RESET_TOKEN_MAX_AGE = _int("RESET_TOKEN_MAX_AGE_SECONDS", 3600)        # 1 hour
    VERIFY_TOKEN_MAX_AGE = _int("VERIFY_TOKEN_MAX_AGE_SECONDS", 86400)     # 24 hours
    # Absolute base URL for links in emails when there is no request context
    # (e.g. background jobs). Falls back to request.url_root in handlers.
    PUBLIC_BASE_URL = _str("PUBLIC_BASE_URL", "")

    # --- Database ----------------------------------------------------------
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- Rate limiting -----------------------------------------------------
    RATELIMIT_STORAGE_URI = _str("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_DEFAULT = _str("RATELIMIT_DEFAULT", "300 per hour")
    # Tighter budget for expensive endpoints (LLM calls / PDF compilation).
    RATELIMIT_LLM = _str("RATELIMIT_LLM", "40 per hour")
    RATELIMIT_AUTH = _str("RATELIMIT_AUTH", "20 per hour")
    # The public, no-login demo runs an LLM call per request, so keep it tight
    # (keyed by client IP). Encourages sign-up rather than free unlimited use.
    RATELIMIT_DEMO = _str("RATELIMIT_DEMO", "5 per day")
    RATELIMIT_ENABLED = _bool("RATELIMIT_ENABLED", default=True)

    # --- Uploads -----------------------------------------------------------
    INSTANCE_DIR = _INSTANCE_DIR
    # Text-layer formats are parsed directly; images (and scanned PDFs) are
    # read with OCR (see src/ocr.py).
    ALLOWED_UPLOAD_EXTENSIONS = {
        "pdf", "docx", "tex", "txt",
        "png", "jpg", "jpeg", "webp", "tif", "tiff", "bmp", "gif",
    }

    IS_PRODUCTION = _is_production()


def ensure_instance_dir() -> None:
    """Create the instance directory used by SQLite and temp uploads."""
    os.makedirs(_INSTANCE_DIR, exist_ok=True)
