"""Run the Auto-CV development server: ``python -m autocv``.

For production, serve the WSGI app behind gunicorn/uvicorn instead, e.g.::

    gunicorn "autocv:create_app()"
"""

from __future__ import annotations

import os

from . import create_app
from . import llm_client


def main() -> None:
    app = create_app()
    print(f"[startup] {llm_client.describe_config()}", flush=True)
    # Debug is sourced from config (FLASK_DEBUG), defaulting to OFF for safety.
    app.run(
        debug=app.config.get("DEBUG", False),
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
    )


if __name__ == "__main__":
    main()
