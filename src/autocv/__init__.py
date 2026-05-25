"""Auto-CV package.

Public web app + core modules for job parsing, CV matching, LLM-assisted
rewriting, and LaTeX/PDF generation.

The Flask application is built by :func:`create_app`, which lets it be created
with test or production config and discovered by ``flask --app autocv`` and
``python -m autocv``.
"""

from .app import create_app

__version__ = "1.0.0"
__author__ = "Auto-CV Team"

_LAZY_EXPORTS = {
    "parse_job_description": (".parser", "parse_job_description"),
    "JobDescriptionParser": (".parser", "JobDescriptionParser"),
    "CVMatcher": (".matcher", "CVMatcher"),
    "LaTeXGenerator": (".latex_gen", "LaTeXGenerator"),
    "SmartCVGenerator": (".smart_cv_generator", "SmartCVGenerator"),
    "JobAnalysis": (".smart_cv_generator", "JobAnalysis"),
    "CVSection": (".smart_cv_generator", "CVSection"),
    "generate_smart_cv": (".smart_cv_generator", "generate_smart_cv"),
}


def __getattr__(name):
    """Load optional/heavy public exports only when callers ask for them."""
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _LAZY_EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name, __name__), attr_name)
    globals()[name] = value
    return value


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
