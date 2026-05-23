# Installation Guide for Auto-CV

## Prerequisites

Before you begin, ensure you have the following installed:

1. **Python 3.8 or higher**
   - [Download Python](https://www.python.org/downloads/)

2. **LaTeX Distribution**
   - **Windows:** [MiKTeX](https://miktex.org/download) or [TeX Live](https://texlive.info/)
   - **macOS:** [MacTeX](https://tug.org/mactex/)
   - **Linux:** `sudo apt-get install texlive-full` (Debian/Ubuntu) or equivalent for your distribution

3. **pip** (Python package manager)
   - Usually comes with Python installation

## Installation Steps

### Step 1: Clone or Download the Project

```bash
# Clone from git (if available)
git clone https://github.com/yourusername/auto-cv.git
cd auto-cv

# OR if downloading as zip, extract it first
```

### Step 2: Create a Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### Step 3: Install Python Dependencies

```bash
# Install required Python packages
pip install -r requirements.txt

# The following packages will be installed:
# - Flask==3.0.0 (Web framework)
# - PyLaTeX==1.4.2 (LaTeX generation)
# - python-dotenv==1.0.0 (Environment variables)
# - requests==2.31.0 (HTTP requests)
# - nltk==3.8.1 (Natural language processing)
# - scikit-learn==1.3.2 (Machine learning)
# - numpy==1.24.3 (Numerical computing)
# - matplotlib==3.8.2 (Plotting)
# - seaborn==0.13.2 (Statistical data visualization)
```

### Step 4: Download NLTK Data

The application uses NLTK for text processing. Download the required data:

```bash
# Run this in your terminal or Python shell:
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('stopwords')"
```

Or run it as part of the first application startup - it will prompt you automatically.

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
# Make sure your virtual environment is activated
# Then run:
python main.py

# Or with explicit port:
python main.py --port 5000
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
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('stopwords')"
```

#### 3. Port already in use (5000)

**Solution:** Use a different port:
```bash
python main.py --port 5001
```

#### 4. Permission errors during pip install

**Solution:** Use a virtual environment or add `--user` flag:
```bash
pip install --user -r requirements.txt
```

#### 5. "Failed to generate PDF" error

**Solutions:**
- Check that your LaTeX CV is properly formatted
- Make sure all required LaTeX packages are installed
- Check for any syntax errors in your LaTeX code

## Configuration

### Environment Variables (Optional)

Create a `.env` file in the project root:

```
FLASK_ENV=production
FLASK_DEBUG=0
```

## Next Steps

After installation, try the following:

1. **Load Sample Data:** Use the "Load Sample Job" and "Load Sample CV" buttons to see the app in action
2. **Test Your Own Data:** Upload your job description and CV to see the optimization
3. **Review Recommendations:** Check the suggestions for improving your CV
4. **Download PDF:** Get your optimized CV in PDF format

## Getting Help

If you encounter issues:

1. Check the browser console for errors (F12 → Console)
2. Check the terminal where you ran `python main.py` for backend errors
3. Review the example files in the `examples/` directory
4. Ensure all prerequisites are properly installed

## Support

For issues, questions, or contributions:
- Create an issue on GitHub
- Email: support@auto-cv.com (placeholder)

Happy CV optimizing! 🚀
