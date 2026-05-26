"""Pytest fixtures for Auto-CV.

The app is configured for tests *before* it is imported (config reads the
environment at import time): a throwaway SQLite DB, CSRF and rate limiting off,
and a fixed secret key. Tables are recreated for each test so cases are isolated.
"""

import os
import sys
import pathlib
import tempfile

# --- Configure the app via env BEFORE importing it -------------------------
_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

os.environ["FLASK_ENV"] = "testing"          # relaxes production-only behaviour
os.environ["WTF_CSRF_ENABLED"] = "false"     # test the API without CSRF tokens
os.environ["RATELIMIT_ENABLED"] = "false"    # don't trip limits during tests
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["SMTP_HOST"] = ""                 # dev log-only email (no network)
os.environ["REQUIRE_EMAIL_VERIFICATION"] = "false"
os.environ["LATEX_REPAIR_ATTEMPTS"] = "5"
os.environ["LATEX_REPAIR_MAX_TOKENS"] = "8000"
# Force LLM calls onto the fast no-op path (keyless OpenRouter returns None
# immediately) so tests exercise the rule-based fallbacks without any network.
os.environ["SOURCE_LLM"] = "openrouter"
os.environ["OPENROUTER_API_KEY"] = ""

_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_DB.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB.name}"

import pytest  # noqa: E402
from autocv import create_app  # noqa: E402

# Build the app once for the test session (mirrors a long-lived process). Config
# is read from the environment set above when the package is imported.
_application = create_app()


@pytest.fixture()
def app():
    application = _application
    # Reset the schema in a *temporary* context. Do NOT keep an app context open
    # during the test: Flask-Login caches current_user on ``g`` (bound to the app
    # context), so a long-lived context would bleed one client's identity into
    # another's requests. Each test_client request pushes its own fresh context.
    with application.app_context():
        from autocv.extensions import db
        db.drop_all()
        db.create_all()
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, email="user@example.com", password="password123", name="Test"):
    """Register (and, by default, log in) a user via the JSON API."""
    return client.post("/register", json={"email": email, "password": password, "name": name})


def login(client, email="user@example.com", password="password123"):
    return client.post("/login", json={"email": email, "password": password})
