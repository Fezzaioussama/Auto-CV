# Auto-CV Project Summary

## Overview

Auto-CV is a web application that helps users optimize their LaTeX CVs based on job descriptions. The application parses job requirements, analyzes the user's CV, and generates recommendations to improve the CV's match with the job description.

## Project Structure

```
auto-cv-app/
├── src/
│   └── autocv/              # Application package
│       ├── __init__.py      # Package init (exposes create_app)
│       ├── app.py           # Flask application factory + routes
│       ├── parser.py        # Job description parser
│       ├── matcher.py       # CV matching engine
│       ├── latex_gen.py     # LaTeX renderer
│       └── ...              # auth, workspace, interview_agent, llm_client, etc.
├── templates/               # HTML + LaTeX templates
├── static/                  # CSS, JavaScript, and assets
├── tests/                   # pytest suite (+ fixtures/)
├── scripts/                 # Standalone smoke/dev scripts
├── docs/                    # Documentation
├── examples/                # Example files (sample_cv.tex)
├── main.py                  # Backwards-compatible entry point
├── pyproject.toml           # Packaging + tooling config
├── requirements.txt         # Python dependencies
└── README.md                # Project overview
```

## Core Features

### 1. Job Description Parser (`src/autocv/parser.py`)
- Extracts skills from job descriptions
- Identifies requirements and qualifications
- Detects company information
- Uses NLTK for natural language processing

### 2. CV Matching Engine (`src/autocv/matcher.py`)
- Parses LaTeX CVs into structured sections
- Matches CV skills with job requirements
- Calculates match score
- Identifies gaps and missing requirements
- Generates optimization recommendations

### 3. LaTeX Renderer (`src/autocv/latex_gen.py`)
- Generates professional LaTeX CV documents
- Supports multiple sections (summary, experience, education, skills, projects)
- Creates categorized skills sections
- Compiles to PDF using pdflatex

### 4. Web Interface
- User-friendly drag-and-drop upload
- Job description parsing visualization
- Match score display
- Optimization recommendations
- PDF download capability

## Technology Stack

### Backend
- **Flask 3.0.0** - Web framework
- **Python 3.8+** - Programming language
- **NLTK** - Natural language processing
- **scikit-learn** - Machine learning utilities
- **NumPy** - Numerical computing

### Frontend
- **Bootstrap 5.3** - CSS framework
- **Bootstrap Icons** - Icon library
- **JavaScript (ES6+)** - Interactive functionality

### PDF Generation
- **pdflatex** - LaTeX to PDF compiler
- **PyLaTeX** - LaTeX generation library

## Installation

### Prerequisites
- Python 3.8 or higher
- LaTeX distribution (MiKTeX, MacTeX, or TeX Live)
- uv (https://docs.astral.sh/uv/)

### Steps
```bash
# Install Python dependencies
uv sync

# Download NLTK data
uv run python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('stopwords')"

# Run the application
uv run python -m autocv
```

## Usage Flow

1. **Upload Job Description**
   - Paste text or upload a file
   - Click "Parse Job Description"

2. **Upload Your CV**
   - Paste LaTeX code or upload a `.tex` file
   - Or use sample CV for testing

3. **Optimize**
   - Click "Optimize CV for This Job"
   - Review match score and recommendations

4. **Download**
   - Click "Download PDF" for optimized CV
   - Or "Copy LaTeX" for manual editing

## API Endpoints

- `POST /api/parse-job` - Parse job description
- `POST /api/analyze-cv` - Analyze CV against job
- `POST /api/optimize-cv` - Optimize CV and generate recommendations
- `POST /api/render-latex` - Compile LaTeX to PDF
- `GET /api/sample-cv` - Get sample CV
- `GET /api/sample-job` - Get sample job description

## Testing the Application

### Start the Server
```bash
cd auto-cv-app
uv run python -m autocv
```

### Test URLs
- Main page: http://localhost:5000
- Sample job: http://localhost:5000/api/sample-job
- Sample CV: http://localhost:5000/api/sample-cv

## Example Job Description
```
Senior Software Engineer - Tech Company, Inc.

We are looking for an experienced developer with:
- 5+ years of experience with Python, JavaScript, and SQL
- Experience with React, Node.js, and Django
- Knowledge of AWS, Docker, and Kubernetes
- Strong problem-solving skills

Required: Bachelor's degree in Computer Science
```

## Example CV Sections

### Summary
Experienced software developer with 5+ years of experience in building scalable web applications.

### Experience
Senior Software Engineer, Tech Company, Inc.\hfill 2020 - Present
\textbf{Led} a team of 5 developers in building a distributed microservices architecture.

### Skills
\begin{description}[noitemsep,nosep]
\item[\textbf{Programming Languages}] Python, Java, JavaScript, C++, SQL
\item[\textbf{Frameworks \& Libraries}] Django, Flask, React, Node.js
\end{description}

## Troubleshooting

### Common Issues
1. **pdflatex not found** - Install LaTeX distribution
2. **NLTK errors** - Run `nltk.download()` commands
3. **Port already in use** - Use `PORT=5001 uv run python -m autocv`

See `docs/INSTALLATION.md` for detailed troubleshooting.

## Files Created

| File | Purpose |
|------|---------|
| `src/autocv/app.py` | Flask application factory (`create_app`) with all API endpoints |
| `main.py` | Backwards-compatible entry point that builds the app |
| `src/autocv/parser.py` | Job description parsing logic |
| `src/autocv/matcher.py` | CV matching and analysis engine |
| `src/autocv/latex_gen.py` | LaTeX generation and PDF compilation |
| `src/autocv/__init__.py` | Package initialization (exposes `create_app`) |
| `templates/index.html` | Main web interface |
| `static/style.css` | CSS styling |
| `static/script.js` | JavaScript frontend logic |
| `requirements.txt` | Python dependencies |
| `README.md` | Project documentation |
| `docs/QUICKSTART.md` | Quick start guide |
| `docs/INSTALLATION.md` | Installation guide |
| `examples/sample_cv.tex` | Sample LaTeX CV |

## Next Steps for Users

1. Install required packages (`uv sync`)
2. Install LaTeX distribution
3. Download NLTK data
4. Run `uv run python -m autocv`
5. Open http://localhost:5000 in browser
6. Upload job description and CV
7. Optimize and download

## Success Criteria Met

✅ Upload job description text
✅ Parse and extract requirements/skills
✅ Accept LaTeX CV input
✅ Analyze CV against job requirements
✅ Generate match score and statistics
✅ Provide optimization recommendations
✅ Re-render CV in LaTeX format
✅ Download PDF output

## Project Status

**Status**: ✅ Complete
**Tested**: ✅ All core functionality verified
**Documentation**: ✅ Installation and usage guides provided
**Examples**: ✅ Sample CV and job descriptions included

---

Created: March 31, 2026
Auto-CV Team
