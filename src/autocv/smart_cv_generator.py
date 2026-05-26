"""
Smart CV Template Generator Module
Generates AI-adapted CV documents based on job requirements.
Uses vLLM for LLM-powered content generation and analysis.
"""

import os
import re
import json
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field

try:  # importable both as a bare module (tests) and as the src package
    from llm_client import complete, Task
except ImportError:  # pragma: no cover
    from .llm_client import complete, Task


@dataclass
class JobAnalysis:
    """Analysis of job requirements and matching."""
    job_title: str = ""
    company: str = ""
    location: str = ""
    required_skills: List[str] = field(default_factory=list)
    preferred_skills: List[str] = field(default_factory=list)
    key_requirements: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    experience_level: str = ""
    match_score: float = 0.0
    missing_skills: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    llm_analysis: Dict = field(default_factory=dict)


@dataclass
class CVSection:
    """Represents a CV section with content."""
    title: str
    content: str
    priority: int = 0  # Higher priority = more emphasis
    job_matched: bool = False
    llm_generated: bool = False  # Whether this section was AI-generated


class SmartCVGenerator:
    """
    Generates AI-adapted CV documents based on job requirements.
    Uses vLLM for LLM-powered content generation and analysis.
    """
    
    def __init__(self, template_path: str = None, 
                 api_url: str = None, 
                 model: str = None):
        """
        Initialize the Smart CV Generator.
        
        Args:
            template_path: Path to the smart template file
            api_url: vLLM API URL (default: http://195.154.75.46:8002/v1)
            model: Model name to use (default: qwen/qwen3.6-plus)
        """
        if template_path is None:
            # Try to find the template in the project. This file lives at
            # <repo>/src/autocv/smart_cv_generator.py, so the project root is
            # three directories up (autocv -> src -> repo root).
            project_root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            template_path = os.path.join(project_root, 'templates', 'template_smart.tex')
        
        self.template_path = template_path
        self.template_content = None
        
        # Load the template
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                self.template_content = f.read()
        
        # LLM configuration. When left as None, llm_client resolves the
        # provider, base URL, key and model from the environment (.env).
        self.api_url = api_url  # explicit base-URL override, or None
        self.model = model      # explicit model override, or None
        self.api_key = None     # explicit key override, or None (env-resolved)
    
    def _call_llm_api(self, prompt: str, max_tokens: int = 2000, temperature: float = 0.3) -> Optional[str]:
        """
        Call the configured LLM (local vLLM or OpenRouter) via llm_client.

        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            AI-generated response or None if call fails
        """
        return complete(
            prompt,
            system_prompt=(
                "You are a helpful assistant that provides job analysis and CV "
                "recommendations. Always respond with clear, structured "
                "information."
            ),
            task=Task.SMART_CV,
            model=self.model,      # None -> resolved by task/provider
            base_url=self.api_url,  # None -> configured base URL
            api_key=self.api_key,   # None -> env-resolved key
            temperature=temperature,
            max_tokens=max_tokens,
            log_prefix="smart-cv",
        )
    
    def analyze_job_with_llm(self, job_text: str, cv_skills: List[str] = None) -> JobAnalysis:
        """
        Use LLM to analyze job description and generate detailed analysis.
        
        Args:
            job_text: The job description text
            cv_skills: Optional list of skills from the CV for matching
            
        Returns:
            JobAnalysis object with LLM-powered insights
        """
        # First, get basic analysis from parser
        from .parser import JobDescriptionParser
        parser = JobDescriptionParser()
        parsed = parser.parse(job_text)
        
        # Extract basic info
        job_title = self._extract_job_title(job_text)
        company = self._extract_company(job_text)
        location = self._extract_location(job_text)
        job_skills = parsed.get('skills', [])
        requirements = parsed.get('requirements', [])
        
        # Build skills comparison
        cv_skills_lower = [s.lower() for s in cv_skills] if cv_skills else []
        missing_skills = [s for s in job_skills if s.lower() not in cv_skills_lower]
        
        # Build prompt for LLM analysis
        prompt = f"""Analyze the following job description and provide detailed insights for CV optimization.

Job Description:
{job_text}

CV Skills Available:
{', '.join(cv_skills) if cv_skills else 'Not provided'}

Please analyze and provide your response in the following JSON format:
{{
    "analysis": {{
        "role_focus": "main focus of the role",
        "key_requirements": ["list of top requirements"],
        "tech_stack": ["tech stack mentioned"],
        "company_culture": ["implied culture aspects"]
    }},
    "skill_matching": {{
        "matched_skills": ["skills that align"],
        "missing_skills": ["skills to highlight or learn"],
        "strong_matches": ["skills that are well-aligned"],
        "weak_matches": ["skills that need better demonstration"]
    }},
    "recommendations": {{
        "summary_focus": "what to emphasize in summary",
        "experience_highlights": ["specific achievements to highlight"],
        "keywords_to_include": ["important keywords to use"],
        "action_verbs": ["effective action verbs for this role"]
    }}
}}
"""
        
        # Call LLM
        llm_response = self._call_llm_api(prompt)
        llm_analysis = {}
        
        if llm_response:
            # Try to parse JSON response
            try:
                start_idx = llm_response.find('{')
                end_idx = llm_response.rfind('}') + 1
                if start_idx != -1 and end_idx > start_idx:
                    json_str = llm_response[start_idx:end_idx]
                    llm_analysis = json.loads(json_str)
            except (json.JSONDecodeError, Exception) as e:
                print(f"Could not parse LLM response as JSON: {e}")
                # Fallback to basic parsing
                llm_analysis = {
                    "analysis": {
                        "role_focus": job_title,
                        "key_requirements": requirements[:5] if requirements else [],
                        "tech_stack": job_skills[:5] if job_skills else [],
                        "company_culture": []
                    },
                    "skill_matching": {
                        "matched_skills": [s for s in job_skills if s.lower() in cv_skills_lower][:8],
                        "missing_skills": missing_skills[:5],
                        "strong_matches": [],
                        "weak_matches": []
                    },
                    "recommendations": {
                        "summary_focus": f"Emphasize experience with {', '.join(job_skills[:3])}",
                        "experience_highlights": ["Highlight relevant projects and achievements"],
                        "keywords_to_include": job_skills[:5],
                        "action_verbs": ["Led", "Developed", "Implemented", "Optimized"]
                    }
                }
        
        # Calculate match score
        matched_count = len(llm_analysis.get("skill_matching", {}).get("matched_skills", []))
        total_skills = len(job_skills) if job_skills else 1
        match_score = round((matched_count / total_skills) * 100, 1) if total_skills > 0 else 0.0
        
        # Extract recommendations
        recommendations = []
        if llm_analysis:
            recs = llm_analysis.get("recommendations", {})
            if recs.get("summary_focus"):
                recommendations.append(recs["summary_focus"])
            keywords = recs.get("keywords_to_include", [])
            if keywords:
                recommendations.append(f"Incorporate keywords: {', '.join(keywords[:5])}")
            verbs = recs.get("action_verbs", [])
            if verbs:
                recommendations.append(f"Use action verbs: {', '.join(verbs[:4])}")
        
        # Add general recommendations if needed
        if len(recommendations) < 3:
            if missing_skills:
                recommendations.append(f"Highlight or learn these skills: {', '.join(missing_skills[:5])}")
            recommendations.append("Use keywords from the job description throughout your CV")
        
        return JobAnalysis(
            job_title=job_title,
            company=company,
            location=location,
            required_skills=job_skills,
            preferred_skills=[],
            key_requirements=requirements,
            keywords=job_skills[:10],
            experience_level=self._determine_experience_level(job_text),
            match_score=match_score,
            missing_skills=missing_skills,
            recommendations=recommendations[:5],
            llm_analysis=llm_analysis
        )
    
    def analyze_job_description(self, job_text: str, cv_skills: List[str] = None) -> JobAnalysis:
        """
        Analyze a job description and extract key information.
        Uses LLM when available, falls back to rule-based analysis.
        
        Args:
            job_text: The job description text
            cv_skills: Optional list of skills from the CV for matching
            
        Returns:
            JobAnalysis object with extracted information
        """
        # Try LLM analysis first (more accurate)
        analysis = self.analyze_job_with_llm(job_text, cv_skills)
        
        # If LLM analysis fails, fall back to parser
        if not analysis.llm_analysis:
            from .parser import JobDescriptionParser
            parser = JobDescriptionParser()
            parsed = parser.parse(job_text)
            
            job_skills = parsed.get('skills', [])
            requirements = parsed.get('requirements', [])
            
            cv_skills_lower = [s.lower() for s in cv_skills] if cv_skills else []
            missing_skills = [s for s in job_skills if s.lower() not in cv_skills_lower]
            
            matched_count = len(job_skills) - len(missing_skills)
            total_skills = len(job_skills) if job_skills else 1
            match_score = round((matched_count / total_skills) * 100, 1) if total_skills > 0 else 50.0
            
            analysis = JobAnalysis(
                job_title=self._extract_job_title(job_text),
                company=self._extract_company(job_text),
                location=self._extract_location(job_text),
                required_skills=job_skills,
                preferred_skills=[],
                key_requirements=requirements,
                keywords=job_skills[:10],
                experience_level=self._determine_experience_level(job_text),
                match_score=match_score,
                missing_skills=missing_skills,
                recommendations=[
                    "Use keywords from the job description throughout your CV",
                    "Tailor your professional summary to match the position",
                    f"Highlight experience with {', '.join(job_skills[:3]) if job_skills else 'relevant skills'}"
                ],
                llm_analysis={}
            )
        
        return analysis
    
    def _extract_job_title(self, text: str) -> str:
        """Extract job title from job description."""
        lines = text.strip().split('\n')
        
        if lines:
            first_line = lines[0].strip()
            if len(first_line) < 80 and any(title in first_line.lower() for title in 
                                             ['developer', 'engineer', 'scientist', 'analyst', 
                                              'manager', 'consultant', 'specialist', 'lead']):
                clean_title = re.sub(r'[-–—]+.*$', '', first_line).strip()
                if clean_title and len(clean_title) > 2:
                    return clean_title
        
        patterns = [
            r'^(?:Senior\s+|Junior\s+|Mid-level\s+)?(\w+\s+(?:Engineer|Developer|Consultant|Analyst|Specialist|Manager|Director|Lead))',
            r'looking for\s+(.+?)(?:\n|$)',
            r'position:\s*(.+?)(?:\n|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return "Position"
    
    def _extract_company(self, text: str) -> str:
        """Extract company name from job description."""
        # First, try to extract from "About Us" or "About the company"
        about_match = re.search(r'about\s+(?:us|the\s+company)\s*[:\-]?\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if about_match:
            company = about_match.group(1).strip()
            # Clean up - remove "We are" or "is a" patterns
            company = re.sub(r'^(?:We are|is a|is an|is the)\s+', '', company, flags=re.IGNORECASE)
            company = re.sub(r'^(?:a|an|the)\s+', '', company, flags=re.IGNORECASE)
            if company and len(company) < 100:
                return company
        
        # Try to find company in "About Us" section
        about_match = re.search(r'about\s+us\s*[:\-]?\s*([A-Z][a-zA-Z\s]+?)(?:\n|$)', text, re.IGNORECASE)
        if about_match:
            company = about_match.group(1).strip()
            if company and len(company) < 100:
                return company
        
        # Try pattern "at [Company]" or "for [Company]"
        company_match = re.search(r'(?:at|for)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)(?:\s*[-–—].*|$)', text)
        if company_match:
            return company_match.group(1).strip()
        
        # Try "company\s+name" or "company\s+profile"
        company_match = re.search(r'(?:company\s+(?:name|profile))\s*[:\-]?\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)', text, re.IGNORECASE)
        if company_match:
            return company_match.group(1).strip()
        
        # Default fallback
        return "Company"
    
    def _extract_location(self, text: str) -> str:
        """Extract location from job description."""
        patterns = [
            r'location\s*[:\-]?\s*([A-Z][a-zA-Z\s,]+?(?:USA|US|UK|Europe|Asia|Canada)?(?:\n|$))',
            r'based\s+in\s+([A-Z][a-zA-Z\s,]+?(?:\n|$))',
            r'office\s+location\s*[:\-]?\s*([A-Z][a-zA-Z\s,]+?(?:\n|$))',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return "Location"
    
    def _determine_experience_level(self, text: str) -> str:
        """Determine experience level from job description."""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['senior', 'lead', 'principal', 'expert']):
            return "Senior"
        elif any(word in text_lower for word in ['junior', 'entry-level', 'graduate', 'intern']):
            return "Junior"
        elif any(word in text_lower for word in ['mid-level', 'intermediate']):
            return "Mid-Level"
        else:
            return "Intermediate"
    
    def generate_cv_section_with_llm(self, section_type: str, 
                                    job_analysis: JobAnalysis,
                                    original_content: str = None) -> CVSection:
        """
        Generate a CV section using LLM.
        
        Args:
            section_type: Type of section ('summary', 'skills', 'experience', etc.)
            job_analysis: Job analysis results
            original_content: Original CV content for this section
            
        Returns:
            CVSection with LLM-generated content
        """
        if section_type == 'summary':
            return self._generate_summary_with_llm(job_analysis)
        elif section_type == 'skills':
            return self._generate_skills_with_llm(job_analysis, original_content)
        elif section_type == 'experience':
            return self._generate_experience_with_llm(job_analysis, original_content)
        elif section_type == 'projects':
            return self._generate_projects_with_llm(job_analysis, original_content)
        else:
            return CVSection(title=section_type, content=original_content or "", llm_generated=False)
    
    def _generate_summary_with_llm(self, job_analysis: JobAnalysis) -> CVSection:
        """Generate optimized summary using LLM."""
        if not job_analysis.llm_analysis:
            # Fallback to template if no LLM analysis
            return self._generate_summary(job_analysis)
        
        recommendations = job_analysis.llm_analysis.get("recommendations", {})
        summary_focus = recommendations.get("summary_focus", "")
        keywords = recommendations.get("keywords_to_include", [])
        
        prompt = f"""Write a professional CV summary (2-3 sentences) for a {job_analysis.job_title} position at {job_analysis.company}.

Key requirements: {', '.join(job_analysis.required_skills[:5]) if job_analysis.required_skills else 'relevant skills'}
Focus areas: {summary_focus or 'relevant experience and skills'}
Keywords to include: {', '.join(keywords[:5]) if keywords else 'relevant keywords'}

Provide the summary in LaTeX format using \\textbf{{}} for emphasis.
"""
        
        llm_response = self._call_llm_api(prompt, max_tokens=500)
        
        if llm_response:
            return CVSection(
                title="Summary",
                content=llm_response.strip(),
                priority=10,
                job_matched=True,
                llm_generated=True
            )
        else:
            return self._generate_summary(job_analysis)
    
    def _generate_skills_with_llm(self, job_analysis: JobAnalysis, 
                                 original_content: str = None) -> CVSection:
        """Generate skills section using LLM."""
        if not job_analysis.llm_analysis:
            return self._generate_skills(job_analysis, original_content)
        
        recommendations = job_analysis.llm_analysis.get("recommendations", {})
        keywords = recommendations.get("keywords_to_include", [])
        
        prompt = f"""Create a skills section for a CV targeting {job_analysis.job_title} at {job_analysis.company}.

Required skills: {', '.join(job_analysis.required_skills[:8]) if job_analysis.required_skills else 'relevant skills'}
Keywords to emphasize: {', '.join(keywords[:5]) if keywords else 'relevant keywords'}

Format the skills in LaTeX with categories using \\textbf{{}}.
"""
        
        llm_response = self._call_llm_api(prompt, max_tokens=800)
        
        if llm_response:
            return CVSection(
                title="Skills",
                content=llm_response.strip(),
                priority=9,
                job_matched=True,
                llm_generated=True
            )
        else:
            return self._generate_skills(job_analysis, original_content)
    
    def _generate_experience_with_llm(self, job_analysis: JobAnalysis, 
                                     original_content: str = None) -> CVSection:
        """Generate experience section using LLM."""
        if not job_analysis.llm_analysis:
            return self._generate_experience(job_analysis, original_content)
        
        recommendations = job_analysis.llm_analysis.get("recommendations", {})
        highlights = recommendations.get("experience_highlights", [])
        verbs = recommendations.get("action_verbs", [])
        
        prompt = f"""Write experience bullet points for a {job_analysis.job_title} position.

Target role: {job_analysis.job_title}
Company: {job_analysis.company}
Required skills: {', '.join(job_analysis.required_skills[:5]) if job_analysis.required_skills else 'relevant skills'} 
Action verbs to use: {', '.join(verbs[:4]) if verbs else 'Achieved, Implemented, Led, Optimized'}
Key highlights to include: {', '.join(highlights[:3]) if highlights else 'relevant achievements'}

Format in LaTeX using \\textbf{{}} for emphasis and \\begin{{resume_list}} environment.
"""
        
        llm_response = self._call_llm_api(prompt, max_tokens=1000)
        
        if llm_response:
            return CVSection(
                title="Experience",
                content=llm_response.strip(),
                priority=8,
                job_matched=True,
                llm_generated=True
            )
        else:
            return self._generate_experience(job_analysis, original_content)
    
    def _generate_projects_with_llm(self, job_analysis: JobAnalysis, 
                                   original_content: str = None) -> CVSection:
        """Generate projects section using LLM."""
        if not job_analysis.llm_analysis:
            return self._generate_projects(job_analysis, original_content)
        
        recommendations = job_analysis.llm_analysis.get("recommendations", {})
        keywords = recommendations.get("keywords_to_include", [])
        
        prompt = f"""Write project descriptions that highlight skills for {job_analysis.job_title}.

Target role: {job_analysis.job_title}
Required skills: {', '.join(job_analysis.required_skills[:4]) if job_analysis.required_skills else 'relevant skills'} 
Keywords to emphasize: {', '.join(keywords[:4]) if keywords else 'relevant keywords'}

Format in LaTeX using \\textbf{{}} for project titles and technologies.
"""
        
        llm_response = self._call_llm_api(prompt, max_tokens=800)
        
        if llm_response:
            return CVSection(
                title="Projects",
                content=llm_response.strip(),
                priority=7,
                job_matched=True,
                llm_generated=True
            )
        else:
            return self._generate_projects(job_analysis, original_content)
    
    def generate_cv_section(self, section_type: str, 
                           job_analysis: JobAnalysis = None,
                           original_content: str = None) -> CVSection:
        """
        Generate a CV section based on job analysis.
        Uses LLM when available, falls back to template.
        
        Args:
            section_type: Type of section ('summary', 'skills', 'experience', etc.)
            job_analysis: Job analysis results
            original_content: Original CV content for this section
            
        Returns:
            CVSection with generated content
        """
        # Try LLM first
        llm_section = self.generate_cv_section_with_llm(section_type, job_analysis, original_content)
        
        if llm_section.llm_generated:
            return llm_section
        else:
            # Fallback to template-based generation
            if section_type == 'summary':
                return self._generate_summary(job_analysis)
            elif section_type == 'skills':
                return self._generate_skills(job_analysis, original_content)
            elif section_type == 'experience':
                return self._generate_experience(job_analysis, original_content)
            elif section_type == 'projects':
                return self._generate_projects(job_analysis, original_content)
            elif section_type == 'certifications':
                return self._generate_certifications(job_analysis, original_content)
            else:
                return CVSection(title=section_type, content=original_content or "", llm_generated=False)
    
    def _generate_summary(self, job_analysis: JobAnalysis) -> CVSection:
        """Generate an optimized summary section (template fallback)."""
        if not job_analysis:
            return CVSection(
                title="Summary",
                content="Highly motivated professional seeking opportunities to apply skills.",
                llm_generated=False
            )
        
        content = f"""Highly motivated AI professional seeking \\textbf{{{job_analysis.job_title}}} position at \\textbf{{{job_analysis.company}}}.

Bringing expertise in {', '.join(job_analysis.required_skills[:3]) if job_analysis.required_skills else 'relevant skills'} 
and a proven track record of {job_analysis.experience_level.lower()} level performance.

Key strengths aligned with the position requirements:
{chr(10).join(['  • ' + rec for rec in job_analysis.recommendations[:3]])}
"""
        
        return CVSection(
            title="Summary",
            content=content.strip(),
            priority=10,
            job_matched=True,
            llm_generated=False
        )
    
    def _generate_skills(self, job_analysis: JobAnalysis, 
                        original_content: str = None) -> CVSection:
        """Generate skills section highlighting job-relevant skills (template fallback)."""
        if not job_analysis:
            return CVSection(
                title="Skills",
                content=original_content or "Technical skills: Python, Java, JavaScript, SQL, Git, Docker, AWS",
                llm_generated=False
            )
        
        required = job_analysis.required_skills
        missing = job_analysis.missing_skills
        
        skills_lines = []
        
        if required:
            skills_lines.append(f"\\textbf{{Key Skills for {job_analysis.job_title} :}}")
            skills_lines.append("  " + ", ".join(required[:8]))
            skills_lines.append("")
        
        core_skills = [
            ("Programming Languages", ["Python", "C++", "MATLAB"]),
            ("AI/ML Frameworks", ["PyTorch", "Scikit-learn", "OpenCV", "Hugging Face"]),
            ("Cloud & DevOps", ["AWS", "Docker", "Kubernetes"]),
        ]
        
        for category, skills in core_skills:
            skills_lines.append(f"\\textbf{{{category}}} :")
            skills_lines.append("  " + ", ".join(skills))
        
        if missing:
            skills_lines.append("")
            skills_lines.append(f"\\textbf{{Skills in Development :}}")
            skills_lines.append("  " + ", ".join(missing[:5]))
        
        content = "\n".join(skills_lines)
        
        return CVSection(
            title="Skills",
            content=content.strip(),
            priority=9,
            job_matched=True,
            llm_generated=False
        )
    
    def _generate_experience(self, job_analysis: JobAnalysis, 
                            original_content: str = None) -> CVSection:
        """Generate experience section emphasizing job-relevant achievements (template fallback)."""
        if not job_analysis:
            return CVSection(
                title="Experience",
                content=original_content or "Professional experience not provided.",
                llm_generated=False
            )
        
        content = f"""\\textbf{{Key Experience for {job_analysis.job_title}}}:

\\begin{{resume_list}}
  \\item \\textbf{{Position Alignment:}} Direct experience with {', '.join(job_analysis.required_skills[:3]) if job_analysis.required_skills else 'relevant technologies'}
  
  \\item \\textbf{{Achievements:}} Proven success in {job_analysis.experience_level.lower()} level environments with measurable impact
  
  \\item \\textbf{{Relevant Projects:}} Worked on projects directly applicable to {job_analysis.company}'s needs
\\end{{resume_list}}

\\textbf{{Additional Experience:}} 

Highlights from professional background demonstrating capabilities required for this position.
"""
        
        return CVSection(
            title="Experience",
            content=content.strip(),
            priority=8,
            job_matched=True,
            llm_generated=False
        )
    
    def _generate_projects(self, job_analysis: JobAnalysis, 
                          original_content: str = None) -> CVSection:
        """Generate projects section highlighting relevant work (template fallback)."""
        if not job_analysis:
            return CVSection(
                title="Projects",
                content=original_content or "Projects: See resume for details.",
                llm_generated=False
            )
        
        content = f"""Selected projects demonstrating expertise in {', '.join(job_analysis.required_skills[:2]) if job_analysis.required_skills else 'relevant areas'}:

\\begin{{resume_list}}
  \\item \\textbf{{AI/ML Projects:}} Experience with {', '.join(['deep learning', 'computer vision', 'NLP'])} applications
  
  \\item \\textbf{{Technical Implementation:}} Demonstrated ability to deploy solutions using {', '.join(['Docker', 'AWS', 'CI/CD'])}
  
  \\item \\textbf{{Problem Solving:}} Track record of delivering solutions for complex technical challenges
\\end{{resume_list}}
"""
        
        return CVSection(
            title="Projects",
            content=content.strip(),
            priority=7,
            job_matched=True,
            llm_generated=False
        )
    
    def _generate_certifications(self, job_analysis: JobAnalysis, 
                                original_content: str = None) -> CVSection:
        """Generate certifications section (template fallback)."""
        content = """Professional certifications demonstrating commitment to continuous learning:

\\begin{{resume_list}}
  \\item \\textbf{{AI/ML Certifications:}} Hugging Face AI Agents, PyTorch, Machine Learning
  \\item \\textbf{{Technical Certifications:}} Python, Data Analysis, Power BI
  \\item \\textbf{{Cloud Certifications:}} AWS, Azure fundamentals
\\end{{resume_list}}
"""
        return CVSection(
            title="Certifications",
            content=content.strip(),
            priority=6,
            job_matched=False,
            llm_generated=False
        )
    
    def generate_customized_cv(self, job_analysis: JobAnalysis, 
                              cv_sections: Dict[str, str] = None) -> str:
        """
        Generate a customized CV based on job analysis.
        
        Args:
            job_analysis: Analysis of the job requirements
            cv_sections: Optional original CV sections
            
        Returns:
            Customized LaTeX CV content
        """
        if not self.template_content:
            raise ValueError("Template content not loaded. Check template path.")
        
        # Generate all sections with job-specific content
        sections = {}
        
        for section_type in ['summary', 'skills', 'experience', 'projects', 'certifications']:
            original = cv_sections.get(section_type) if cv_sections else None
            section = self.generate_cv_section(
                section_type, 
                job_analysis,
                original
            )
            sections[section_type] = section
        
        # Create substitutions for template variables
        substitutions = {
            '\\jobTitle': job_analysis.job_title,
            '\\jobCompany': job_analysis.company,
            '\\jobLocation': job_analysis.location,
            '\\targetSkill1': job_analysis.required_skills[0] if job_analysis.required_skills else "Skill 1",
            '\\targetSkill2': job_analysis.required_skills[1] if len(job_analysis.required_skills) > 1 else "Skill 2",
            '\\targetSkill3': job_analysis.required_skills[2] if len(job_analysis.required_skills) > 2 else "Skill 3",
            '\\targetKeyword1': job_analysis.keywords[0] if job_analysis.keywords else "Keyword 1",
            '\\targetKeyword2': job_analysis.keywords[1] if len(job_analysis.keywords) > 1 else "Keyword 2",
            '\\jobObjective': f"Highly motivated AI professional seeking \\textbf{{{job_analysis.job_title}}} position at \\textbf{{{job_analysis.company}}}. Bringing expertise in {', '.join(job_analysis.required_skills[:3]) if job_analysis.required_skills else 'relevant skills'}.",
        }
        
        # Apply substitutions
        customized = self.template_content
        for var, value in substitutions.items():
            customized = customized.replace(var, value)
        
        # Replace section placeholders with generated content
        customized = self._replace_section_content(customized, sections)
        
        return customized
    
    def _replace_section_content(self, template: str, 
                                sections: Dict[str, CVSection]) -> str:
        """Replace section content in the template."""
        section_markers = {
            'summary': '% PROFESSIONAL SUMMARY PLACEHOLDER',
            'skills': '% KEY SKILLS PLACEHOLDER',
            'experience': '% PROFESSIONAL EXPERIENCE PLACEHOLDER',
            'projects': '% PROJECTS PLACEHOLDER',
        }
        
        for section_name, section in sections.items():
            marker = section_markers.get(section_name, f'% {section_name.upper()} PLACEHOLDER')
            
            # Create content block
            content_block = f"% === {section.title} ===\n{section.content}"
            
            template = template.replace(marker, content_block)
        
        return template
    
    def save_cv(self, cv_content: str, filename: str, 
               output_dir: str = None) -> str:
        """
        Save CV content to a file.
        
        Args:
            cv_content: The LaTeX content
            filename: Output filename
            output_dir: Output directory
            
        Returns:
            Path to saved file
        """
        if output_dir is None:
            output_dir = os.path.dirname(self.template_path)
            if output_dir is None:
                output_dir = '.'
        
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(cv_content)
        
        return filepath
    
    def compile_to_pdf(self, latex_filepath: str, 
                      output_dir: str = None) -> str:
        """
        Compile LaTeX to PDF using pdflatex.
        
        Args:
            latex_filepath: Path to the LaTeX file
            output_dir: Output directory for PDF
            
        Returns:
            Path to generated PDF
        """
        import subprocess
        
        if not os.path.exists(latex_filepath):
            raise FileNotFoundError(f"LaTeX file not found: {latex_filepath}")
        
        output_dir = output_dir or os.path.dirname(latex_filepath)
        base_name = os.path.splitext(os.path.basename(latex_filepath))[0]
        
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
            else:
                raise RuntimeError(f"pdflatex failed: {result.stderr.decode()}")
                
        except FileNotFoundError:
            raise RuntimeError("pdflatex not found. Please install a LaTeX distribution.")
        except subprocess.TimeoutExpired:
            raise RuntimeError("LaTeX compilation timed out.")


def generate_smart_cv(job_description: str, cv_skills: List[str] = None,
                     output_dir: str = None, filename: str = None,
                     api_url: str = None, model: str = None) -> str:
    """
    Convenience function to generate a smart CV using vLLM.
    
    Args:
        job_description: The job description text
        cv_skills: Optional list of skills from the CV
        output_dir: Output directory
        filename: Output filename
        api_url: vLLM API URL (optional, uses environment variable if not provided)
        model: Model name (optional, uses environment variable if not provided)
        
    Returns:
        Path to generated PDF
    """
    generator = SmartCVGenerator(api_url=api_url, model=model)
    
    # Analyze job description
    job_analysis = generator.analyze_job_description(job_description, cv_skills)
    
    # Generate customized CV
    cv_content = generator.generate_customized_cv(job_analysis)
    
    # Save to file
    if filename is None:
        filename = f"CV_{job_analysis.job_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.tex"
    
    tex_path = generator.save_cv(cv_content, filename, output_dir)
    
    # Compile to PDF
    pdf_path = generator.compile_to_pdf(tex_path, output_dir)
    
    return pdf_path


if __name__ == "__main__":
    # Sample job description
    sample_job = """
    Senior AI Developer - Tech Solutions
    
    Location: Paris, France
    
    About Us:
    We are a leading technology company building next-generation AI solutions.
    
    Job Description:
    We are looking for an experienced AI Developer to join our team. 
    You will be responsible for designing and implementing AI solutions.
    
    Requirements:
    - 5+ years of experience with Python, PyTorch, and computer vision
    - Experience with deep learning models and optimization
    - Knowledge of AWS and cloud deployment
    - Strong problem-solving skills
    
    Preferred:
    - Experience with LLMs and NLP
    - Knowledge of MLOps practices
    """
    
    # Sample CV skills
    sample_skills = [
        'Python', 'C++', 'PyTorch', 'OpenCV', 'Deep Learning', 
        'AWS', 'Docker', 'Git', 'English', 'French'
    ]
    
    # Generate CV using vLLM
    try:
        pdf_path = generate_smart_cv(sample_job, sample_skills)
        print(f"CV generated at: {pdf_path}")
    except Exception as e:
        print(f"Error generating CV: {e}")
        print("Note: This may require pdflatex to be installed for PDF compilation")
