"""Backwards-compatible entry point for the Auto-CV app.

The application now lives in the ``autocv`` package under ``src/`` and is built
by ``autocv.create_app()``. This thin shim keeps ``python main.py`` and
``gunicorn main:app`` working without an editable install by putting ``src/`` on
the import path, then exposing the built app as ``app``.

Preferred ways to run the app:

    pip install -e .          # then:
    flask --app autocv run    # dev server (auto-reload with --debug)
    python -m autocv          # dev server
    gunicorn "autocv:create_app()"   # production WSGI
"""

import os
import sys

# Make the ``autocv`` package importable without an editable install.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from autocv import create_app  # noqa: E402
from autocv import llm_client  # noqa: E402

app = create_app()

if __name__ == "__main__":
    print(f"[startup] {llm_client.describe_config()}", flush=True)
    # Debug is sourced from config (FLASK_DEBUG), defaulting to OFF for safety.
    app.run(debug=app.config.get("DEBUG", False), host="0.0.0.0", port=5000)
