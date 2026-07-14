"""Vercel Flask entry point.

Vercel's Flask integration auto-detects a top-level ``app.py`` exporting a
Flask ``app`` object. Keep the application construction in ``main.py`` so local
commands such as ``python main.py`` and ``gunicorn main:app`` continue to work.
"""

from __future__ import annotations

import os
import sys
import traceback


def _configure_vercel_runtime_dirs() -> None:
    """Point libraries that cache on import at Vercel's writable scratch space."""
    if not (os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV")):
        return

    runtime_root = "/tmp/autocv-runtime"
    paths = {
        "HOME": os.path.join(runtime_root, "home"),
        "XDG_CACHE_HOME": os.path.join(runtime_root, "cache"),
        "MPLCONFIGDIR": os.path.join(runtime_root, "matplotlib"),
        "NLTK_DATA": os.path.join(runtime_root, "nltk_data"),
        "JOBLIB_TEMP_FOLDER": os.path.join(runtime_root, "joblib"),
        "TMPDIR": os.path.join(runtime_root, "tmp"),
        "TEMP": os.path.join(runtime_root, "tmp"),
        "TMP": os.path.join(runtime_root, "tmp"),
    }
    for name, path in paths.items():
        os.environ[name] = path
        os.makedirs(path, exist_ok=True)


_configure_vercel_runtime_dirs()

from flask import Flask, Response

_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# Vercel's Python runtime detector requires a literal top-level WSGI app object.
# The real Auto-CV app replaces this after imports/configuration succeed.
app = Flask(__name__)

try:
    from autocv import create_app

    app = create_app()
except Exception as exc:  # noqa: BLE001 - keep Vercel function alive for diagnostics
    traceback.print_exc()
    _startup_error = f"{type(exc).__name__}: {exc}"

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def startup_error(path: str = ""):
        body = (
            "Auto-CV failed during server startup.\n\n"
            f"Error: {_startup_error}\n\n"
            "Open the latest Vercel deployment logs for the full Python traceback."
        )
        return Response(body, status=500, mimetype="text/plain")
