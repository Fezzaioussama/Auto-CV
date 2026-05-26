# Quick Start Guide for Auto-CV

## Overview
Auto-CV is an AI-powered system that helps you create tailored CVs based on job descriptions. It uses vLLM to analyze job requirements and generate customized CV content.

## Prerequisites
- [uv](https://docs.astral.sh/uv/)
- Python 3.10+ (uv installs/pins it from `.python-version`)

## Installation

1. Install dependencies (creates `.venv`):
```bash
uv sync
```

2. Download NLTK data (if needed):
```bash
uv run python -c "import nltk; nltk.download('punkt_tab'); nltk.download('stopwords')"
```

## Quick Test (No Server Required)

Run the test script to verify everything works:

```bash
uv run python scripts/test_vllm_cv.py
```

This will:
1. Test vLLM API connection
2. Generate a sample CV using the API
3. Save the output to `output/vllm_test_cv.tex`

## Running the Web Application

1. Start the Flask server:
```bash
uv run python -m autocv
```

2. Open your browser to `http://localhost:5000`

3. Use the web interface to:
   - Upload your CV
   - Paste a job description
   - Get an AI-powered tailored CV

## API Usage (Programmatic)

You can also use the system programmatically:

```python
from src.smart_cv_generator import SmartCVGenerator, generate_smart_cv

# Method 1: Using the generator directly
generator = SmartCVGenerator()
job_description = """
Senior AI Developer - Tech Solutions

We are looking for an experienced AI Developer...
"""

cv_skills = ['Python', 'PyTorch', 'Deep Learning', 'AWS', 'Docker']
job_analysis = generator.analyze_job_description(job_description, cv_skills)
cv_content = generator.generate_customized_cv(job_analysis)
generator.save_cv(cv_content, "my_custom_cv.tex")

# Method 2: Using the convenience function
pdf_path = generate_smart_cv(
    job_description=job_description,
    cv_skills=cv_skills,
    output_dir="output"
)
```

## vLLM Configuration

The system uses vLLM at `http://127.0.0.1:8002/v1` with model `qwen/qwen3.6-plus`.

To change the API settings, set environment variables:

```bash
export VLLM_API_URL=http://your-vllm-server:8000/v1
export VLLM_MODEL=your/model-name
```

## Output

Generated CVs are saved as LaTeX files (`.tex`) in the `output/` directory.

To convert to PDF, you need `pdflatex` installed:
```bash
pdflatex output/your_cv.tex
```

## Project Structure

```
auto-cv-app/
├── main.py                     # Backwards-compatible entry point
├── pyproject.toml              # Packaging + tooling config
├── requirements.txt            # Python dependencies
├── src/
│   └── autocv/                 # Application package
│       ├── __init__.py         # Exposes create_app
│       ├── app.py              # Flask application factory + routes
│       ├── smart_cv_generator.py   # Core AI generation logic
│       ├── parser.py           # Job description parser
│       ├── matcher.py          # CV matching
│       ├── latex_gen.py        # LaTeX generation
│       └── utils.py            # Utility functions
├── templates/
│   ├── index.html             # Web interface
│   └── template_smart.tex     # CV template
├── static/
│   └── script.js              # Frontend JS
├── tests/                     # pytest suite (+ fixtures/)
├── scripts/                   # Standalone smoke/dev scripts
└── examples/
    └── sample_cv.tex          # Sample CV

```

## Troubleshooting

**NLTK errors**: Run `python -c "import nltk; nltk.download('punkt_tab')"` to download required data.

**PDF generation**: Install a LaTeX distribution (e.g., `sudo apt install texlive-full` on Ubuntu).

**API connection errors**: Check that the vLLM server is running and accessible at the configured URL.
