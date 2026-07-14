"""Shared helper that serves the React SPA's built index.html.

The SPA owns every public page (landing, auth, optimizer, workspace, account).
Flask blueprints still own /api/* and the auth POST handlers; for *GET* requests
on those routes they call into here so the SPA can take over client-side
routing. Kept in its own module to avoid the circular import that would happen
if auth.py imported app.py."""

from __future__ import annotations

from pathlib import Path

from flask import render_template, request

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SPA_INDEX = _REPO_ROOT / "static" / "spa" / "index.html"


def serve_spa() -> str:
    """Return the SPA shell, or fall back to a Jinja template before build."""
    if _SPA_INDEX.exists():
        return _SPA_INDEX.read_text(encoding="utf-8")
    template = "index.html"
    if request.path.startswith("/login"):
        template = "login.html"
    elif request.path.startswith("/register"):
        template = "register.html"
    elif request.path.startswith("/forgot-password"):
        template = "forgot_password.html"
    return render_template(template)
