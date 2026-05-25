"""Explicit Vercel Python function entry point.

This keeps deployment working even when Vercel's Flask auto-detection does not
mount the top-level ``app.py`` at the site root.
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from main import app  # noqa: E402
