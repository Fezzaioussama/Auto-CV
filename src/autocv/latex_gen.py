"""
LaTeX Generator Module
Generates professional LaTeX CV documents that can be compiled to PDF.
"""

import os
from datetime import datetime
from typing import Dict, List, Optional


class LaTeXGenerator:
    """Generates LaTeX CV documents."""
    
    def __init__(self):
        """Initialize the LaTeX generator."""
        self.packages = [
            'geometry',
            'titlesec',
            'hyperref',
            'enumitem',
            'fontspec',
            'xcolor',
            'dashrule'
        ]

    def _escape_latex_text(self, value: str) -> str:
        """Escape plain text for LaTeX."""
        replacements = {
            '&': r'\&',
            '%': r'\%',
            '$': r'\$',
            '#': r'\#',
            '_': r'\_',
        }
        text = str(value)
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        return text
    
    def generate_cv_latex(self, personal_info: Dict, sections: Dict, 
                          job_analysis: Optional[Dict] = None) -> str:
        """
        Generate a complete LaTeX CV document.
        
        Args:
            personal_info: Personal information (name, email, phone, etc.)
            sections: CV sections (summary, experience, education, skills)
            job_analysis: Optional analysis from job matching
            
        Returns:
            str: Complete LaTeX document
        """
        header = self._generate_header(personal_info)
        body = self._generate_body(sections, job_analysis)
        
        latex = f"""% Auto-Generated CV
% Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

\\documentclass[11pt,a4paper]{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage[margin=1in]{{geometry}}
\\usepackage{{titlesec}}
\\usepackage{{hyperref}}
\\usepackage{{enumitem}}
\\usepackage{{xcolor}}
\\usepackage{{setspace}}

% Colors
\\definecolor{{primary}}{{HTML}}{{004466}}
\\definecolor{{secondary}}{{HTML}}{{666666}}
\\definecolor{{accent}}{{HTML}}{{cc3333}}

% Section formatting
\\titleformat{{\\section}}{{\\large\\bfseries\\color{{primary}}\\uppercase}}{{\\thesection}}{{1em}}{{}}

% Reduce spacing
\\setlength{{\\parindent}}{{0pt}}
\\setlength{{\\parskip}}{{6pt}}

\\begin{{document}}
\\thispagestyle{{empty}}

{header}

\\vspace{{1em}}

{body}

\\end{{document}}
"""
        return latex
    
    def _generate_header(self, personal_info: Dict) -> str:
        """Generate the header section with personal information."""
        name = personal_info.get('name', 'Your Name')
        email = personal_info.get('email', 'your.email@example.com')
        phone = personal_info.get('phone', '+1 234 567 8900')
        location = personal_info.get('location', 'City, Country')
        linkedin = personal_info.get('linkedin', '')
        website = personal_info.get('website', '')
        
        # Build contact line
        contact_parts = [email, phone, location]
        if linkedin:
            contact_parts.append(linkedin)
        if website:
            contact_parts.append(website)
        
        contact_line = ' | '.join(contact_parts)
        
        latex = f"""% Personal Information
\\begin{{center}}
    \\Huge{{\\textbf{{{name}}}}} \\\\ [1em]
    \\Large{{\\color{{secondary}}{{{contact_line}}}}}
\\end{{center}}

\\hrule

\\vspace{{1em}}
"""
        return latex
    
    def _generate_body(self, sections: Dict, job_analysis: Optional[Dict] = None) -> str:
        """Generate the body of the CV."""
        body_parts = []
        
        # Professional Summary
        if 'summary' in sections:
            body_parts.append(self._generate_summary_section(sections['summary']))
        
        # Skills
        if 'skills' in sections:
            skills_text = self._format_skills_section(sections['skills'], job_analysis)
            body_parts.append(f"\\section{{Skills}}\n{skills_text}")
        
        # Experience
        if 'experience' in sections:
            body_parts.append(self._generate_experience_section(sections['experience']))
        
        # Education
        if 'education' in sections:
            body_parts.append(self._generate_education_section(sections['education']))
        
        # Projects (if available)
        if 'projects' in sections:
            body_parts.append(self._generate_projects_section(sections['projects']))
        
        return '\n\n'.join(body_parts)
    
    def _generate_summary_section(self, content: str) -> str:
        """Generate the professional summary section."""
        return f"""\\section{{Professional Summary}}
{content}

\\vspace{{0.5em}}
"""
    
    def _format_skills_section(self, content: str, job_analysis: Optional[Dict] = None) -> str:
        """Format the skills section, optionally highlighting job-relevant skills."""
        if not content:
            return "\\textit{Skills not provided.}"
        
        # Parse skills
        skills_list = [s.strip() for s in content.replace(',', '\n').split('\n') if s.strip()]
        
        if not skills_list:
            return "\\textit{Skills not provided.}"
        
        # Group skills by category if job_analysis provides suggestions
        categories = {
            'Technical Skills': [],
            'Languages': [],
            'Tools & Platforms': [],
            'Methodologies': []
        }
        
        # Simple categorization
        for skill in skills_list:
            skill_lower = skill.lower()
            if any(lang in skill_lower for lang in ['python', 'java', 'javascript', 'c++', 'ruby', 'go', 'rust']):
                categories['Technical Skills'].append(skill)
            elif any(lang in skill_lower for lang in ['english', 'spanish', 'french', 'german']):
                categories['Languages'].append(skill)
            elif any(tool in skill_lower for tool in ['git', 'docker', 'aws', 'azure', 'kubernetes', 'jenkins']):
                categories['Tools & Platforms'].append(skill)
            elif any(meth in skill_lower for meth in ['agile', 'scrum', 'tdd', 'bdd', 'devops']):
                categories['Methodologies'].append(skill)
            else:
                categories['Technical Skills'].append(skill)
        
        # Build LaTeX
        latex_parts = []
        for category, skills in categories.items():
            if skills:
                latex_parts.append(f"\\textbf{{{self._escape_latex_text(category)}}}:\n")
                latex_parts.append("\\begin{itemize}[leftmargin=*]\n")
                for skill in skills[:10]:  # Limit to 10 per category
                    latex_parts.append(f"    \\item {self._escape_latex_text(skill)}\n")
                latex_parts.append("\\end{itemize}\n\n")
        
        return ''.join(latex_parts) if latex_parts else content
    
    def _generate_experience_section(self, content: str) -> str:
        """Generate the experience section."""
        if not content:
            return "\\section{Experience}\n\\textit{Experience not provided.}"
        
        return f"""\\section{{Experience}}
{content}

\\vspace{{0.5em}}
"""
    
    def _generate_education_section(self, content: str) -> str:
        """Generate the education section."""
        if not content:
            return "\\section{Education}\n\\textit{Education not provided.}"
        
        return f"""\\section{{Education}}
{content}

\\vspace{{0.5em}}
"""
    
    def _generate_projects_section(self, content: str) -> str:
        """Generate the projects section."""
        if not content:
            return "\\section{Projects}\n\\textit{Projects not provided.}"
        
        return f"""\\section{{Projects}}
{content}

\\vspace{{0.5em}}
"""
    
    def generate_adapted_cv(self, original_content: str, job_requirements: Dict, 
                            modifications: Dict) -> str:
        """
        Generate an adapted CV based on job requirements.
        
        Args:
            original_content: Original CV content
            job_requirements: Job description requirements
            modifications: Suggested modifications from analysis
            
        Returns:
            str: Adapted LaTeX CV
        """
        # Extract job title for context
        job_title = job_requirements.get('job_title', 'Position')
        company = job_requirements.get('company', 'Company')
        
        # Build modified sections
        modified_sections = {
            'summary': f"""I am a {job_title} professional with a proven track record of success. 
My expertise aligns closely with the requirements for this position at {company}.
{modifications.get('summary_modification', '')}""",
            'skills': self._create_adapted_skills(modifications),
            'experience': self._create_adapted_experience(original_content, modifications)
        }
        
        # Add original sections if available
        if 'education' in original_content:
            modified_sections['education'] = original_content['education']
        
        # Create personal info with job-specific focus
        personal_info = {
            'name': 'Your Name',
            'email': 'your.email@example.com',
            'phone': '+1 234 567 8900',
            'location': 'City, Country'
        }
        
        return self.generate_cv_latex(personal_info, modified_sections)
    
    def _create_adapted_skills(self, modifications: Dict) -> str:
        """Create adapted skills section based on modifications."""
        keywords = modifications.get('keywords_to_add', [])
        action_verbs = modifications.get('action_verbs', [])
        
        # If we have specific keywords, use them
        if keywords:
            skills = ', '.join(keywords[:8])
            return f"Key Skills: {skills}.\n\n\\textbf{{Action Verbs}}: {', '.join(action_verbs[:4])}"
        
        return "Technical Skills: Python, Java, JavaScript, SQL, Git, Docker, AWS, Agile Methodologies.\n\n\\textbf{{Soft Skills}}: Communication, Problem Solving, Team Collaboration"
    
    def _create_adapted_experience(self, original_content: str, modifications: Dict) -> str:
        """Create adapted experience section."""
        # If we have modifications, incorporate them
        exp_mods = modifications.get('experience_modifications', [])
        
        if exp_mods:
            latex = ""
            for mod in exp_mods[:3]:
                item = mod.get('experience_item', 'Experience')
                suggestion = mod.get('suggested_modification', '')
                latex += f"\\textbf{{{item}}}:\n{suggestion}\n\n"
            return latex
        
        # Default experience template
        return """\\textbf{Senior Developer | Tech Company}
\\textit{2020 - Present | City, Country}

\\begin{itemize}[leftmargin=*]
    \\item Led development of scalable web applications using modern technologies
    \\item Collaborated with cross-functional teams to deliver projects on time
    \\item Optimized application performance, resulting in significant improvements
    \\item Mentored junior developers and conducted code reviews
\\end{itemize}

\\vspace{0.5em}

\\textbf{Software Engineer | Previous Company}
\\textit{2018 - 2020 | City, Country}

\\begin{itemize}[leftmargin=*]
    \\item Designed and implemented features for enterprise applications
    \\item Participated in agile development processes
    \\item Wrote comprehensive tests and documentation
\\end{itemize}"""


def save_latex_to_file(latex_content: str, filepath: str) -> str:
    """Save LaTeX content to a file."""
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(latex_content)
    return filepath


def compile_latex_to_pdf(latex_filepath: str, output_dir: Optional[str] = None) -> Optional[str]:
    """
    Compile LaTeX file to PDF using pdflatex.
    
    Args:
        latex_filepath: Path to the LaTeX file
        output_dir: Optional output directory for PDF
        
    Returns:
        Path to the generated PDF or None if compilation fails
    """
    import subprocess
    import tempfile
    
    if not os.path.exists(latex_filepath):
        print(f"Error: LaTeX file not found: {latex_filepath}")
        return None
    
    output_dir = output_dir or os.path.dirname(latex_filepath) or '.'
    base_name = os.path.splitext(os.path.basename(latex_filepath))[0]
    
    # Try to compile with pdflatex
    try:
        result = subprocess.run(
            ['pdflatex', '-interaction=nonstopmode', 
             f'-output-directory={output_dir}', latex_filepath],
            capture_output=True,
            timeout=3600
        )
        
        if result.returncode == 0:
            pdf_path = os.path.join(output_dir, f"{base_name}.pdf")
            if os.path.exists(pdf_path):
                return pdf_path
    except FileNotFoundError:
        print("pdflatex not found. Please install a LaTeX distribution.")
    except subprocess.TimeoutExpired:
        print("LaTeX compilation timed out.")
    
    return None


def generate_cv_from_text(personal_info: Dict, cv_sections: Dict, 
                          job_requirements: Optional[Dict] = None) -> str:
    """
    Convenience function to generate a complete CV from text data.
    
    Args:
        personal_info: Personal information
        cv_sections: CV section contents
        job_requirements: Optional job requirements for adaptation
        
    Returns:
        str: Generated LaTeX CV
    """
    generator = LaTeXGenerator()
    
    if job_requirements:
        # Generate adapted CV
        modifications = {
            'keywords_to_add': job_requirements.get('skills', [])[:5],
            'summary_modification': f"Focus on {', '.join(job_requirements.get('skills', [])[:3])}"
        }
        return generator.generate_adapted_cv(cv_sections, job_requirements, modifications)
    else:
        # Generate standard CV
        return generator.generate_cv_latex(personal_info, cv_sections)


def render_cv(cv_data: Dict, compact: bool = False) -> str:
    """
    Render a CV data dictionary to LaTeX.

    Args:
        cv_data: Dict with metadata and sections keys
        compact: Kept for compatibility with main.py

    Returns:
        str: Generated LaTeX CV
    """
    metadata = cv_data.get('metadata', {})
    personal_info = {
        'name': metadata.get('name') or metadata.get('author', 'Your Name'),
        'email': metadata.get('email', 'your.email@example.com'),
        'phone': metadata.get('phone', '+1 234 567 8900'),
        'location': metadata.get('location', 'City, Country'),
        'linkedin': metadata.get('linkedin', ''),
        'website': metadata.get('website', ''),
    }

    sections = cv_data.get('sections', {})
    generator = LaTeXGenerator()
    return generator.generate_cv_latex(personal_info, sections)


def create_sample_cv() -> Dict:
    """Create sample CV data for the Flask demo endpoint."""
    return {
        'metadata': {
            'author': 'Alex Morgan',
            'email': 'alex.morgan@example.com',
            'phone': '+1 234 567 8900',
            'location': 'San Francisco, CA',
        },
        'sections': {
            'summary': (
                'Software engineer with experience building web applications, '
                'APIs, and cloud-based services.'
            ),
            'skills': (
                'Python, JavaScript, SQL, React, Flask, Django, Node.js, '
                'Docker, AWS, Git, Agile'
            ),
            'experience': (
                '\\textbf{Software Engineer | Example Tech}\\\\\n'
                '\\textit{2021 - Present | San Francisco, CA}\n'
                '\\begin{itemize}[leftmargin=*]\n'
                '    \\item Built and maintained scalable internal web applications.\n'
                '    \\item Improved API performance and reliability for production services.\n'
                '    \\item Collaborated with product and engineering teams in agile sprints.\n'
                '\\end{itemize}'
            ),
            'education': (
                '\\textbf{B.S. Computer Science}\\\\\n'
                'Example University'
            ),
        },
    }
