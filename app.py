"""Vercel Flask entry point.

Vercel's Flask integration auto-detects a top-level ``app.py`` exporting a
Flask ``app`` object. Keep the application construction in ``main.py`` so local
commands such as ``python main.py`` and ``gunicorn main:app`` continue to work.
"""

from __future__ import annotations

import os
import sys
import traceback

_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

try:
    from autocv import create_app

    app = create_app()
except Exception as exc:  # noqa: BLE001 - keep Vercel function alive for diagnostics
    traceback.print_exc()
    _startup_error = f"{type(exc).__name__}: {exc}"

    from flask import Flask, Response

    app = Flask(__name__)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def startup_error(path: str = ""):
        body = (
            "Auto-CV failed during server startup.\n\n"
            f"Error: {_startup_error}\n\n"
            "Open the latest Vercel deployment logs for the full Python traceback."
        )
        return Response(body, status=500, mimetype="text/plain")
