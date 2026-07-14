"""Verify the configured database connection (Supabase Postgres or SQLite).

Run after setting DATABASE_URL (in .env locally, or in Vercel env vars):

    uv run --python 3.12 python scripts/check_db.py

It reports which backend is active, opens a real connection, ensures the
application tables exist, and prints PASS/FAIL. The password in the connection
string is masked in all output, so this is safe to share.
"""

from __future__ import annotations

import re
import sys

# Make ``src/`` importable when run from the repo root.
sys.path.insert(0, "src")

from autocv.config import Config  # noqa: E402


def _mask(uri: str) -> str:
    """Hide the password in a SQLAlchemy URI before printing it."""
    return re.sub(r"(://[^:/@]+:)[^@]+(@)", r"\1********\2", uri)


def main() -> int:
    uri = Config.SQLALCHEMY_DATABASE_URI
    is_postgres = uri.startswith("postgresql")
    backend = "Postgres (Supabase)" if "supabase.com" in uri else (
        "Postgres" if is_postgres else "SQLite (local fallback)"
    )

    print(f"Backend : {backend}")
    print(f"URI     : {_mask(uri)}")
    print(f"Engine  : {Config.SQLALCHEMY_ENGINE_OPTIONS}")

    if not is_postgres:
        print(
            "\nFAIL: DATABASE_URL is not pointing at Postgres, so the app would "
            "use local SQLite. Set DATABASE_URL to your Supabase connection "
            "string and re-run."
        )
        return 1

    # Import lazily so a missing driver gives a clear message rather than a
    # traceback at import time.
    from sqlalchemy import create_engine, inspect, text

    engine = create_engine(uri, **Config.SQLALCHEMY_ENGINE_OPTIONS)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("\nConnection: OK")
    except Exception as exc:  # noqa: BLE001 - surface the real reason to the user
        print(f"\nFAIL: could not connect: {exc}")
        return 1

    # Create the application tables (idempotent) and report what exists.
    from flask import Flask

    from autocv.extensions import db

    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    with app.app_context():
        from autocv import models  # noqa: F401  (registers the tables)

        db.create_all()
        tables = sorted(inspect(db.engine).get_table_names())

    print(f"Tables  : {', '.join(tables) if tables else '(none)'}")
    print("\nPASS: Supabase database is reachable and schema is in place.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
