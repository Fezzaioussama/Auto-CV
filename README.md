# Auto-CV: Automated LaTeX CV Generator for Job Applications

Auto-CV takes a job description and automatically adjusts your LaTeX CV to match the requirements, then renders it for you to download and use.

## Features

- Upload job description (text or file)
- Extract key requirements and skills
- Analyze your existing LaTeX CV
- Automatically adjust CV content to match job requirements
- Re-render CV in professional LaTeX format
- Download ready-to-use PDF

## Quick Start

### Prerequisites

- Python 3.8+
- LaTeX distribution (TeX Live, MiKTeX, or MacTeX)
- pip package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/auto-cv.git
cd auto-cv

# Install Python dependencies
pip install -r requirements.txt

# Install LaTeX dependencies (if not already installed)
pip install PyLaTeX
```

### Usage

```bash
python main.py
```

Then open your browser to the local web interface.

## Project Structure

```
auto-cv/
├── src/              # Source code
│   ├── parser.py     # Job description parser
│   ├── matcher.py    # CV matching engine
│   ├── latex_gen.py  # LaTeX renderer
│   └── utils.py      # Helper functions
├── templates/        # Web interface templates
├── static/          # CSS and JavaScript
├── docs/           # Documentation
├── examples/       # Example CV and job descriptions
├── requirements.txt
└── main.py         # Main application entry point
```

## How It Works

1. **Job Description Parsing**: Extracts skills, qualifications, and requirements
2. **CV Analysis**: Identifies current skills and experiences in your LaTeX CV
3. **Matching Engine**: Finds gaps between your CV and job requirements
4. **Content Adjustment**: Optimizes your CV content to highlight relevant experiences
5. **LaTeX Rendering**: Generates a professionally formatted LaTeX CV

## Example

See the `examples/` directory for sample job descriptions and corresponding adjusted CVs.

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting pull requests.

## License

This project is licensed under the MIT License.
