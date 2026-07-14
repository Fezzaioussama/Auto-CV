# Installation Guide for Auto-CV

This is the basic installation guide. For developer onboarding and maintenance
details, start with [README.md](README.md) in this folder.

## Prerequisites

Before you begin, ensure you have the following installed:

1. **uv** (Python project + package manager)
   - [Install uv](https://docs.astral.sh/uv/getting-started/installation/)
   - uv installs and pins the right Python version for you (from `.python-version`)

2. **Python 3.10 or higher**
   - uv can install this automatically; no separate download is required

3. **LaTeX Distribution**
   - **Windows:** [MiKTeX](https://miktex.org/download) or [TeX Live](https://texlive.info/)
   - **macOS:** [MacTeX](https://tug.org/mactex/)
   - **Linux:** `sudo apt-get install texlive-full` (Debian/Ubuntu) or equivalent for your distribution

## Installation Steps

### Step 1: Clone or Download the Project

```bash
# Clone from git (if available)
git clone <repository-url>
cd auto-cv-app

# OR if downloading as zip, extract it first
```

### Step 2: Install Dependencies with uv

```bash
# Creates .venv, installs the project (editable) + all dependencies,
# and writes/uses uv.lock for a reproducible install.
uv sync
```

uv manages the virtual environment, so there is no manual `venv` creation or
`activate` step — prefix commands with `uv run` (for example `uv run pytest`).
The dependency set is declared in `pyproject.toml` and pinned in `uv.lock`.

### Step 3: Download NLTK Data

The application uses NLTK for text processing. Download the required data:

```bash
# Run this in your terminal or Python shell:
uv run python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('stopwords')"
```

Or run it as part of the first application startup - it will prompt you automatically.

### Step 4: Configure The LLM Provider

Copy the tracked environment template:

```bash
cp .env.example .env
```

For a local OpenAI-compatible server, set:

```text
SOURCE_LLM=local
LOCAL_LLM_URL=http://localhost:8000/v1
LOCAL_LLM_MODEL=your-model
```

For OpenRouter, set:

```text
SOURCE_LLM=openrouter
OPENROUTER_API_KEY=your-key
OPENROUTER_MODEL=qwen/qwen3.6-plus
OPENROUTER_MODEL_OCR=google/gemini-3.1-flash-lite
```

The app still has legacy local defaults, so it can start without `.env`, but
live AI behavior depends on the configured provider being reachable.

### Step 5: Verify LaTeX Installation

Make sure `pdflatex` is available in your system PATH:

```bash
# Check if pdflatex is installed
pdflatex --version

# On Ubuntu/Debian, install if needed:
sudo apt-get install texlive-latex-recommended texlive-fonts-recommended

# On macOS with MacTeX, it should already be installed
# On Windows with MiKTeX, ensure it's added to PATH
```

## Quick Start

### Running the Application

```bash
# uv runs inside the project .venv automatically
# Start the dev server:
uv run python -m autocv

# Or with a different port:
uv run flask --app autocv run --port 5001 --debug
```

The application will start on `http://localhost:5000`

### Using the Web Interface

1. Open your browser to `http://localhost:5000`
2. **Upload Job Description:**
   - Paste your job description text, OR
   - Drag and drop a text file containing the job description
   - Click "Parse Job Description" to extract requirements
3. **Upload Your CV:**
   - Paste your LaTeX CV code, OR
   - Drag and drop a `.tex` file
   - Or click "Load Sample CV" to test with a sample
4. **Optimize Your CV:**
   - Click "Optimize CV for This Job" to analyze and improve
   - Review the analysis and recommendations
5. **Download Your PDF:**
   - Click "Download PDF" to get your optimized CV as a PDF file
   - Or "Copy LaTeX" to copy the LaTeX code for manual editing

## Troubleshooting

### Common Issues

#### 1. "pdflatex not found" error

**Solution:** Install a LaTeX distribution:
- Windows: Install MiKTeX or TeX Live
- macOS: Install MacTeX
- Linux: `sudo apt-get install texlive-full`

Make sure `pdflatex` is in your system PATH.

#### 2. NLTK download errors

**Solution:** Manually download NLTK data:
```bash
uv run python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('stopwords')"
```

#### 3. Port already in use (5000)

**Solution:** Use a different port:
```bash
uv run flask --app autocv run --port 5001 --debug
```

#### 4. Dependency install problems

**Solution:** Re-create the environment with uv:
```bash
uv sync
```

#### 5. "Failed to generate PDF" error

**Solutions:**
- Check that your LaTeX CV is properly formatted
- Make sure all required LaTeX packages are installed
- Check for any syntax errors in your LaTeX code

## Configuration

### Environment Variables

Create `.env` from `.env.example`:

```bash
cp .env.example .env
```

All LLM-related variables are documented in `.env.example` and
[DEVELOPMENT.md](DEVELOPMENT.md). You can verify the active configuration once
the server is running:

```bash
curl http://localhost:5000/api/llm/health
```

## Next Steps

After installation, try the following:

1. **Load Sample Data:** Use the "Load Sample Job" and "Load Sample CV" buttons to see the app in action
2. **Test Your Own Data:** Upload your job description and CV to see the optimization
3. **Review Recommendations:** Check the suggestions for improving your CV
4. **Download PDF:** Get your optimized CV in PDF format

## Getting Help

If you encounter issues:

1. Check the browser console for errors (F12 -> Console)
2. Check the terminal where you ran `uv run python -m autocv` for backend errors
3. Review the example files in the `examples/` directory
4. Ensure all prerequisites are properly installed

## Support

For issues, questions, or contributions, use the project's repository issue
tracker or the communication channel used by the development team.
