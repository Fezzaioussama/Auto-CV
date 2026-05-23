"""
Auto-CV Source Package
Contains all the core modules for job parsing, CV matching, and LaTeX generation.
"""

from .parser import parse_job_description, JobDescriptionParser
from .matcher import CVMatcher
from .latex_gen import LaTeXGenerator
from .smart_cv_generator import SmartCVGenerator, JobAnalysis, CVSection, generate_smart_cv

__version__ = "1.0.0"
__author__ = "Auto-CV Team"

__all__ = [
    'parse_job_description',
    'JobDescriptionParser',
    'CVMatcher',
    'LaTeXGenerator',
    'SmartCVGenerator',
    'JobAnalysis',
    'CVSection',
    'generate_smart_cv',
]
