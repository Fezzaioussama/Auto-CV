"""Shared, unbound Flask extension instances.

Defining these here (rather than in ``main.py``) lets models and blueprints
import ``db`` / ``login_manager`` without importing the application object,
which avoids circular imports. ``main.py`` calls ``init_app`` on each.
"""

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import CSRFProtect

try:  # Flask-Migrate is optional at runtime; the app still boots without it.
    from flask_migrate import Migrate
except ImportError:  # pragma: no cover - dependency declared in requirements
    Migrate = None  # type: ignore

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
# Alembic-backed schema migrations. Bound in main.py when the package is present.
migrate = Migrate() if Migrate is not None else None

# Rate-limit per authenticated user when logged in, else by client IP, so one
# user can't exhaust the whole IP budget on shared networks.
def _rate_key() -> str:
    try:
        from flask_login import current_user

        if current_user and current_user.is_authenticated:
            return f"user:{current_user.get_id()}"
    except Exception:  # pragma: no cover - never let limiter key crash a request
        pass
    return get_remote_address()


limiter = Limiter(key_func=_rate_key)
