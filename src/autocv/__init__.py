"""Auto-CV package.

Public web app + core modules for job parsing, CV matching, LLM-assisted
rewriting, and LaTeX/PDF generation.

The Flask application is built by :func:`create_app`, which lets it be created
with test or production config and discovered by ``flask --app autocv`` and
``python -m autocv``.
"""

from .parser import parse_job_description, JobDescriptionParser
from .matcher import CVMatcher
from .latex_gen import LaTeXGenerator
from .smart_cv_generator import SmartCVGenerator, JobAnalysis, CVSection, generate_smart_cv
from .app import create_app

__version__ = "1.0.0"
__author__ = "Auto-CV Team"

__all__ = [
    'create_app',
    'parse_job_description',
    'JobDescriptionParser',
    'CVMatcher',
    'LaTeXGenerator',
    'SmartCVGenerator',
    'JobAnalysis',
    'CVSection',
    'generate_smart_cv',
]
