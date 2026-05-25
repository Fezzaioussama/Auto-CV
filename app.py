"""Vercel Flask entry point.

Vercel's Flask integration auto-detects a top-level ``app.py`` exporting a
Flask ``app`` object. Keep the application construction in ``main.py`` so local
commands such as ``python main.py`` and ``gunicorn main:app`` continue to work.
"""

from main import app
