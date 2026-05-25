"""Explicit Vercel Python function entry point.

This keeps deployment working even when Vercel's Flask auto-detection does not
mount the top-level ``app.py`` at the site root.
"""

from __future__ import annotations

import os
import sys
import traceback

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from main import app  # noqa: E402
except Exception as exc:  # noqa: BLE001 - keep Vercel function alive for diagnostics
    traceback.print_exc()
    _startup_error = f"{type(exc).__name__}: {exc}"

    from flask import Flask, Response  # noqa: E402

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
