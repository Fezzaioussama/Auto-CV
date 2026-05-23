"""
Main application entry point for Auto-CV Flask app.
"""

from flask import Flask, render_template, request, send_file, jsonify
from flask_cors import CORS
import os
import base64
from io import BytesIO
from datetime import datetime

# Import our modules
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import llm_client  # loads .env and centralizes provider/model selection
import latex_repair  # compile + LLM auto-repair of LaTeX
from parser import parse_job_description
from matcher import analyze_cv, optimize_cv_for_job
from latex_gen import render_cv, create_sample_cv
import interview_agent

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Sample CV for testing
SAMPLE_CV = create_sample_cv()


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
    """Render LaTeX to PDF, silently auto-repairing compilation errors via LLM.

    On success returns the PDF. If the LLM had to fix the document, the working
    source is returned (base64) in the ``X-Corrected-Latex`` header so the
    client can update its editor to the version that actually compiles.
    """
    try:
        data = request.get_json() or {}
        latex_content = data.get('latex', '')

        if not latex_content:
            return jsonify({'error': 'No LaTeX content provided'}), 400

        try:
            result = latex_repair.render_pdf(latex_content)
        except FileNotFoundError:
            return jsonify({
                'error': 'pdflatex not found. Please install a LaTeX distribution.'
            }), 500

        if not result.success:
            # Repair exhausted — surface a clean error (rare; the UI alerts).
            return jsonify({
                'error': 'LaTeX compilation failed',
                'details': result.error_details or 'The document could not be compiled.'
            }), 500

        response = send_file(
            BytesIO(result.pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'cv_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        )
        response.headers['X-Latex-Repaired'] = 'true' if result.repaired else 'false'
        if result.repaired:
            encoded = base64.b64encode(result.final_latex.encode('utf-8')).decode('ascii')
            # Keep the header within safe limits; the PDF is correct regardless.
            if len(encoded) < 60000:
                response.headers['X-Corrected-Latex'] = encoded
        return response

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/llm/health', methods=['GET'])
def llm_health():
    """Report the active LLM provider/model (never exposes the API key)."""
    return jsonify({
        'success': True,
        'source': llm_client.active_source(),
        'config': llm_client.describe_config(),
    })


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
    print(f'[startup] {llm_client.describe_config()}', flush=True)
    app.run(debug=True, host='0.0.0.0', port=5000)
