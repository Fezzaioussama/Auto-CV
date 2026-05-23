"""
Main application entry point for Auto-CV Flask app.
"""

from flask import Flask, render_template, request, send_file, jsonify
from flask_cors import CORS
import os
import tempfile
import subprocess
import json
import re
import shutil
from io import BytesIO
from datetime import datetime

# Import our modules
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from parser import parse_job_description
from matcher import analyze_cv, optimize_cv_for_job
from latex_gen import render_cv, create_sample_cv
import interview_agent

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Sample CV for testing
SAMPLE_CV = create_sample_cv()


def latex_package_available(package_name):
    """Return whether a LaTeX package is installed for the local compiler."""
    if not shutil.which('kpsewhich'):
        return True

    result = subprocess.run(
        ['kpsewhich', f'{package_name}.sty'],
        capture_output=True
    )
    return result.returncode == 0


def strip_unavailable_latex_package(latex_content, package_name):
    """Remove usepackage lines for packages not installed locally."""
    pattern = rf'^[ \t]*\\usepackage(?:\[[^\]]*\])?\{{{re.escape(package_name)}\}}[ \t]*\n?'
    return re.sub(pattern, '', latex_content, flags=re.MULTILINE)


def replace_missing_graphics(latex_content):
    """Replace includegraphics calls whose local image file is unavailable."""
    image_extensions = {'.pdf', '.png', '.jpg', '.jpeg', '.eps'}

    def _replace(match):
        image_path = match.group('path').strip()
        _, ext = os.path.splitext(image_path)
        if ext.lower() not in image_extensions:
            return match.group(0)
        if os.path.isabs(image_path):
            exists = os.path.exists(image_path)
        else:
            exists = os.path.exists(os.path.join(os.getcwd(), image_path))
        if exists:
            return match.group(0)
        return r'\fbox{\rule{0pt}{1.6cm}\rule{1.6cm}{0pt}}'

    return re.sub(
        r'\\includegraphics(?:\[[^\]]*\])?\{(?P<path>[^{}]+)\}',
        _replace,
        latex_content,
    )


def ensure_latex_dependencies(latex_content):
    """Add packages required by optimizer-generated LaTeX when missing."""
    required_packages = []

    if not latex_package_available('fontawesome5'):
        latex_content = strip_unavailable_latex_package(latex_content, 'fontawesome5')
        latex_content = re.sub(r'\\raisebox\{[^{}]*\}\\faPhone\\?\s*', 'Phone: ', latex_content)
        latex_content = re.sub(r'\\raisebox\{[^{}]*\}\\faEnvelope\\?\s*', 'Email: ', latex_content)
        latex_content = re.sub(r'\\raisebox\{[^{}]*\}\\faLinkedin\\?\s*', 'LinkedIn: ', latex_content)
        latex_content = re.sub(r'\\raisebox\{[^{}]*\}\\faGithub\\?\s*', 'GitHub: ', latex_content)
        latex_content = re.sub(r'\\fa(?:Phone|Envelope|Linkedin|Github)\b\\?\s*', '', latex_content)

    if not latex_package_available('CormorantGaramond'):
        latex_content = strip_unavailable_latex_package(latex_content, 'CormorantGaramond')

    latex_content = replace_missing_graphics(latex_content)

    has_enumitem = re.search(r'\\usepackage(?:\[[^\]]*\])?\{enumitem\}', latex_content)
    if '[leftmargin=*]' in latex_content and not has_enumitem:
        required_packages.append('\\usepackage{enumitem}')

    if not required_packages:
        return latex_content

    package_block = '\n'.join(required_packages)
    document_start = '\\begin{document}'

    if document_start in latex_content:
        return latex_content.replace(document_start, package_block + '\n' + document_start, 1)

    return package_block + '\n' + latex_content


@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')


@app.route('/interview')
def interview():
    """Render the interview preparation page."""
    return render_template('interview.html')


@app.route('/api/interview/questions', methods=['POST'])
def interview_questions():
    """Generate interview questions grounded in the CV and the job offer."""
    try:
        data = request.get_json() or {}
        cv_latex = data.get('cv_latex', '')
        job_description = data.get('job_description') or data.get('job_text') or ''

        if not cv_latex and not job_description:
            return jsonify({'error': 'Provide a CV and/or a job description'}), 400

        result = interview_agent.generate_questions(
            cv_latex=cv_latex,
            job_description=job_description,
            level=data.get('level'),
            domains=data.get('domains'),
            count=data.get('count', 6),
            extra_instructions=data.get('extra_instructions'),
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/interview/review', methods=['POST'])
def interview_review():
    """Review a candidate's answer/code for a single interview question."""
    try:
        data = request.get_json() or {}
        question = data.get('question')
        answer = data.get('answer', '')

        if not question:
            return jsonify({'error': 'No question provided'}), 400

        result = interview_agent.review_answer(
            question=question,
            answer=answer,
            language=data.get('language', ''),
            job_description=data.get('job_description') or data.get('job_text') or '',
        )
        return jsonify({'success': True, 'review': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/parse-job', methods=['POST'])
def parse_job():
    """Parse a job description and extract information."""
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        if not text:
            return jsonify({'error': 'No job description provided'}), 400
        
        result = parse_job_description(text)
        return jsonify({
            'success': True,
            'text': text,
            'raw_text': result.get('raw_text', text),
            'skills': result.get('skills', []),
            'requirements': result.get('requirements', []),
            'qualifications': result.get('qualifications', []),
            'company_info': result.get('company_info', {}),
            'sections': result.get('sections', {})
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyze-cv', methods=['POST'])
def analyze_cv_endpoint():
    """Analyze a CV against a job description."""
    try:
        data = request.get_json()
        cv_latex = data.get('cv_latex', '')
        job_description = data.get('job_description', {})
        
        if not cv_latex:
            return jsonify({'error': 'No CV provided'}), 400
        
        if not job_description:
            return jsonify({'error': 'No job description provided'}), 400
        
        result = analyze_cv(cv_latex, job_description)
        return jsonify({
            'success': True,
            'analysis': result
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/optimize-cv', methods=['POST'])
def optimize_cv_endpoint():
    """Optimize a CV for a specific job."""
    try:
        data = request.get_json()
        cv_latex = data.get('cv_latex', '')
        job_description = data.get('job_description', {})
        
        if not cv_latex:
            return jsonify({'error': 'No CV provided'}), 400
        
        if not job_description:
            return jsonify({'error': 'No job description provided'}), 400

        # Log on arrival: this endpoint runs several sequential LLM calls and can
        # take a while, so make it visible in the terminal immediately instead of
        # only when Flask logs the completed request.
        print('[optimize-cv] request received — running analysis + section rewrites…', flush=True)
        _t0 = datetime.now()
        result = optimize_cv_for_job(cv_latex, job_description)
        print(f'[optimize-cv] done in {(datetime.now() - _t0).total_seconds():.1f}s', flush=True)

        return jsonify({
            'success': True,
            'analysis': result['analysis'],
            'optimized_latex': result['optimized_latex'],
            'rewritten_sections': result.get('rewritten_sections', []),
            'proposed_additions': result.get('proposed_additions', [])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/render-latex', methods=['POST'])
def render_latex():
    """Render LaTeX to PDF and return it."""
    try:
        data = request.get_json()
        latex_content = data.get('latex', '')
        
        if not latex_content:
            return jsonify({'error': 'No LaTeX content provided'}), 400
        
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            tex_file = os.path.join(tmpdir, 'cv.tex')
            pdf_file = os.path.join(tmpdir, 'cv.pdf')
            latex_content = ensure_latex_dependencies(latex_content)
            
            # Write the LaTeX file
            with open(tex_file, 'w', encoding='utf-8') as f:
                f.write(latex_content)
            
            # Compile to PDF using pdflatex
            try:
                result = subprocess.run(
                    ['pdflatex', '-interaction=nonstopmode', '-output-directory', tmpdir, tex_file],
                    capture_output=True,
                    timeout=3600
                )

                stdout_text = result.stdout.decode(errors='replace')
                stderr_text = result.stderr.decode(errors='replace')

                def _log_failure(reason):
                    print('\n' + '=' * 60, flush=True)
                    print(f'[render-latex] FAILED: {reason}', flush=True)
                    print(f'[render-latex] pdflatex returncode: {result.returncode}', flush=True)
                    print('--- pdflatex stdout (tail) ---', flush=True)
                    print('\n'.join(stdout_text.splitlines()[-80:]), flush=True)
                    if stderr_text.strip():
                        print('--- pdflatex stderr ---', flush=True)
                        print(stderr_text, flush=True)
                    log_path = os.path.join(tmpdir, 'cv.log')
                    if os.path.exists(log_path):
                        try:
                            with open(log_path, 'r', encoding='utf-8', errors='replace') as log_f:
                                log_contents = log_f.read()
                            print('--- cv.log (errors) ---', flush=True)
                            for line in log_contents.splitlines():
                                if line.startswith('!') or '! LaTeX Error' in line or line.startswith('l.'):
                                    print(line, flush=True)
                        except OSError:
                            pass
                    print('=' * 60 + '\n', flush=True)

                if result.returncode != 0 and os.path.exists(pdf_file):
                    print(
                        '[render-latex] pdflatex returned non-zero, but a PDF was created; returning PDF.',
                        flush=True
                    )
                elif result.returncode != 0:
                    _log_failure('pdflatex returned non-zero')
                    details = stderr_text or stdout_text
                    return jsonify({
                        'error': 'LaTeX compilation failed',
                        'details': details
                    }), 500

                # Check if PDF was created
                if not os.path.exists(pdf_file):
                    _log_failure('PDF file not created')
                    return jsonify({'error': 'PDF file was not created'}), 500
                
                # Read the PDF before the temporary directory is removed.
                with open(pdf_file, 'rb') as f:
                    pdf_content = f.read()
                
                # Return the PDF
                return send_file(
                    BytesIO(pdf_content),
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f'cv_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
                )
                
            except subprocess.TimeoutExpired:
                return jsonify({'error': 'LaTeX compilation timed out'}), 500
            except FileNotFoundError:
                return jsonify({'error': 'pdflatex not found. Please install a LaTeX distribution.'}), 500
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/sample-cv', methods=['GET'])
def get_sample_cv():
    """Get a sample CV for testing."""
    return jsonify({
        'success': True,
        'cv': SAMPLE_CV
    })


@app.route('/api/sample-job', methods=['GET'])
def get_sample_job():
    """Get a sample job description."""
    sample_job = {
        'text': '''Senior Software Engineer - Tech Company, Inc.
Location: San Francisco, CA

About Us:
We are a fast-growing technology company building next-generation software solutions.

Job Description:
We are looking for an experienced Senior Software Engineer to join our team. You will be responsible for designing and implementing scalable web applications using modern technologies.

Requirements:
- 5+ years of experience with Python, JavaScript, and SQL
- Experience with React, Node.js, and Django
- Knowledge of AWS, Docker, and Kubernetes
- Strong problem-solving skills and ability to work in a team

Preferred Qualifications:
- Master's degree in Computer Science or related field
- Experience with machine learning frameworks
- Prior startup experience
        ''',
        'skills': ['python', 'javascript', 'sql', 'react', 'node.js', 'django', 'aws', 'docker', 'kubernetes'],
        'requirements': [
            '5+ years of experience with Python, JavaScript, and SQL',
            'Experience with React, Node.js, and Django',
            'Knowledge of AWS, Docker, and Kubernetes',
            'Strong problem-solving skills and ability to work in a team'
        ],
        'qualifications': ["Master's degree in Computer Science or related field"]
    }
    return jsonify({
        'success': True,
        'job': sample_job
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
