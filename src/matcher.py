"""
CV Matcher Module
Matches CV content with job requirements using LLM analysis.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, List, Optional, Union


# All LLM access is centralized in llm_client, which picks the provider
# (local vLLM or OpenRouter) and per-task model from the environment (.env).
try:  # importable both as a bare module (main.py) and as the src package
    from llm_client import complete, Task
except ImportError:  # pragma: no cover
    from .llm_client import complete, Task


# Surface forms that should be treated as the same skill when comparing the
# offer's requirements against the CV text. Keys and values are lowercase.
SKILL_ALIASES = {
    "js": "javascript",
    "node": "node.js",
    "nodejs": "node.js",
    "node js": "node.js",
    "reactjs": "react",
    "react.js": "react",
    "react js": "react",
    "angularjs": "angular",
    "ts": "typescript",
    "py": "python",
    "postgres": "postgresql",
    "k8s": "kubernetes",
    "ml": "machine learning",
    "dl": "deep learning",
    "ai": "artificial intelligence",
    "cicd": "ci/cd",
    "ci cd": "ci/cd",
    "golang": "go",
    "csharp": "c#",
    "c sharp": "c#",
    "dotnet": ".net",
    "tf": "tensorflow",
    "gcp": "google cloud",
    "nlp": "natural language processing",
}


def _canonical_skill(skill: str) -> str:
    """Lowercase, collapse whitespace, and map a skill to its canonical form."""
    normalized = re.sub(r"\s+", " ", str(skill).strip().lower())
    return SKILL_ALIASES.get(normalized, normalized)


def _skill_surface_forms(skill: str) -> set:
    """All known surface forms for a skill (the skill plus its aliases)."""
    canonical = _canonical_skill(skill)
    forms = {str(skill).strip().lower(), canonical}
    for surface, canon in SKILL_ALIASES.items():
        if canon == canonical:
            forms.add(surface)
    return {form for form in forms if form}


def _text_contains_skill(text_lower: str, skill: str) -> bool:
    """Whether any surface form of ``skill`` appears in ``text_lower``.

    Uses alphanumeric/symbol boundaries rather than ``\\b`` so tokens such as
    ``c++``, ``.net`` and ``node.js`` still match cleanly, while ``react`` does
    not match inside ``reactor``.
    """
    for form in _skill_surface_forms(skill):
        pattern = r"(?<![a-z0-9+#.])" + re.escape(form) + r"(?![a-z0-9+#])"
        if re.search(pattern, text_lower):
            return True
    return False


def match_skills(cv_text: str, job_skills: List[str]) -> tuple[List[str], List[str]]:
    """Split offer skills into those present in the CV and those missing.

    Comparison is case-insensitive, alias-aware, and deduplicated by canonical
    form so the displayed coverage matches what a recruiter would scan for.
    """
    text_lower = (cv_text or "").lower()
    matched: List[str] = []
    missing: List[str] = []
    seen = set()
    for skill in job_skills:
        canonical = _canonical_skill(skill)
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        if _text_contains_skill(text_lower, skill):
            matched.append(skill)
        else:
            missing.append(skill)
    return matched, missing


@dataclass
class OptimizedSection:
    """Small section wrapper used by the Flask endpoint."""
    title: str
    content: str


class CVMatcher:
    """Matches CV content with job requirements using LLM analysis."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = None):
        """
        Initialize the CV matcher.

        Args:
            api_key: API key for the LLM service (if needed)
            model: Model name to use (defaults to the shared vLLM model)
        """
        # Kept for backward compatibility / explicit overrides. When left as
        # None, llm_client resolves provider, base URL, key and model from env.
        self.api_key = api_key
        self.model = model
    
    def analyze_cv_with_job(self, cv_content: str, job_description: str) -> Dict:
        """
        Analyze CV content against job description using LLM.
        
        Args:
            cv_content: The current CV content
            job_description: The job description text
            
        Returns:
            Dict with analysis results including matches, gaps, and suggestions
        """
        prompt = self._build_analysis_prompt(cv_content, job_description)
        
        # Try to get LLM response
        try:
            response = self._call_llm_api(prompt)
            if response:
                return self._parse_analysis_response(response)
        except Exception as e:
            print(f"LLM API call failed: {e}")
        
        # Fallback to rule-based analysis
        return self._fallback_analysis(cv_content, job_description)
    
    def _build_analysis_prompt(self, cv_content: str, job_description: str) -> str:
        """Build the prompt for LLM analysis."""
        return f"""Analyze the following CV content against the job description and provide specific recommendations.

CV Content:
{cv_content}

Job Description:
{job_description}

Please provide your analysis in the following JSON format:
{{
    "skills_match": {{
        "matched": ["list of skills that match job requirements"],
        "missing": ["list of skills that are missing from CV"],
        "strong_matches": ["skills that are well demonstrated in CV"]
    }},
    "experience_match": {{
        "relevant_experience": ["list of CV experiences relevant to the job"],
        "needs_highlighting": ["experiences that should be emphasized"],
        "weak_matches": ["experiences that don't clearly connect to job"]
    }},
    "recommendations": {{
        "additions": ["specific skills/experiences to add to CV"],
        "emphasize": ["current CV elements to emphasize"],
        "rephrase": ["suggestions for rephrasing CV content to better match job"]
    }},
    "match_percentage": estimated_match_percentage (0-100)
}}

Provide specific, actionable recommendations based on the job requirements."""
    
    def _call_llm_api(self, prompt: str) -> Optional[str]:
        """Get the analysis JSON via the central LLM client (local/OpenRouter)."""
        return complete(
            prompt,
            system_prompt=(
                "You are a technical recruiter. Respond ONLY with the "
                "requested JSON object, no prose and no markdown fences."
            ),
            task=Task.ANALYSIS,
            model=self.model,  # None -> resolved by task/provider
            temperature=0.2,  # Low temperature for focused, stable JSON
            max_tokens=1500,
            log_prefix="matcher",
        )
    
    def _parse_analysis_response(self, response: str) -> Dict:
        """Parse the LLM response into structured format."""
        import json

        # Some models wrap reasoning in <think>...</think>; drop it first.
        response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL)

        # Try to extract JSON from response
        try:
            # Try direct JSON parsing
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1

            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # If JSON parsing fails, create default structure
        return {
            "skills_match": {"matched": [], "missing": [], "strong_matches": []},
            "experience_match": {"relevant_experience": [], "needs_highlighting": [], "weak_matches": []},
            "recommendations": {"additions": [], "emphasize": [], "rephrase": []},
            "match_percentage": 50
        }
    
    def _fallback_analysis(self, cv_content: str, job_description: str) -> Dict:
        """Fallback rule-based analysis when LLM is unavailable."""
        from src.parser import JobDescriptionParser
        
        parser = JobDescriptionParser()
        job_analysis = parser.parse(job_description)

        # Extract skills from the job description (dedupe, keep order)
        job_skills = list(dict.fromkeys(job_analysis.get('skills', [])))

        # Alias-aware, word-boundary matching against the CV text.
        matched, missing = match_skills(cv_content, job_skills)
        
        # Extract relevant experiences
        relevant_exp = []
        if 'responsibilities' in job_analysis.get('sections', {}):
            relevant_exp = ["Your experience aligns with key responsibilities"]
        
        # Create recommendations
        recommendations = {
            "additions": missing[:5] if missing else ["Consider adding more specific achievements"],
            "emphasize": matched[:5] if matched else ["Your general skills match the requirements"],
            "rephrase": ["Use more specific action verbs", "Include quantifiable achievements"]
        }
        
        # Calculate match percentage
        total_job_skills = len(job_skills) if job_skills else 1
        match_pct = int((len(matched) / total_job_skills) * 100)
        
        return {
            "skills_match": {
                "matched": matched,
                "missing": missing,
                "strong_matches": matched[:3]
            },
            "experience_match": {
                "relevant_experience": relevant_exp,
                "needs_highlighting": ["Emphasize your relevant experience"],
                "weak_matches": []
            },
            "recommendations": recommendations,
            "match_percentage": min(match_pct, 100)
        }
    
    def generate_cv_modifications(self, cv_content: str, job_description: str, 
                                   analysis: Dict) -> Dict:
        """
        Generate specific modifications to adapt CV for the job.
        
        Args:
            cv_content: Current CV content
            job_description: Job description text
            analysis: Analysis results from analyze_cv_with_job
            
        Returns:
            Dict with suggested modifications
        """
        prompt = self._build_modification_prompt(cv_content, job_description, analysis)
        
        try:
            response = self._call_llm_api(prompt)
            if response:
                return self._parse_modification_response(response)
        except Exception as e:
            print(f"LLM API call failed: {e}")
        
        return self._fallback_modifications(analysis)
    
    def _build_modification_prompt(self, cv_content: str, job_description: str, 
                                   analysis: Dict) -> str:
        """Build prompt for generating CV modifications."""
        return f"""Based on the following analysis, provide specific modifications to adapt the CV for this job.

Current CV Content:
{cv_content}

Job Description:
{job_description}

Analysis Results:
Skills Matched: {analysis.get('skills_match', {}).get('matched', [])}
Skills Missing: {analysis.get('skills_match', {}).get('missing', [])}
Recommendations: {analysis.get('recommendations', {})}

Provide specific modifications in this JSON format:
{{
    "summary_modification": "suggested modification to professional summary",
    "skills_modification": "suggested modification to skills section",
    "experience_modifications": [
        {{"experience_item": "reference to CV experience", "suggested_modification": "how to modify it"}},
        ...
    ],
    "action_verbs": ["suggested action verbs to use"],
    "keywords_to_add": ["additional keywords from job description to include"]
}}

Keep modifications concise and focused on the job requirements."""
    
    def _parse_modification_response(self, response: str) -> Dict:
        """Parse the modification response."""
        import json

        response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL)

        try:
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        return {
            "summary_modification": "",
            "skills_modification": "",
            "experience_modifications": [],
            "action_verbs": [],
            "keywords_to_add": []
        }
    
    def _fallback_modifications(self, analysis: Dict) -> Dict:
        """Fallback modification suggestions."""
        missing = analysis.get('skills_match', {}).get('missing', [])
        recommendations = analysis.get('recommendations', {})
        
        return {
            "summary_modification": "Strengthen the profile around experience that is already present in the CV.",
            "skills_modification": "Prioritize skills that are both requested by the offer and supported by the CV.",
            "experience_modifications": [
                {"experience_item": "Your professional experience", 
                 "suggested_modification": "Emphasize achievements related to job requirements"}
            ],
            "action_verbs": ["Achieved", "Implemented", "Led", "Optimized"],
            "keywords_to_add": missing[:5] if missing else []
        }


def match_cv_to_job(cv_content: str, job_description: str, 
                    api_key: Optional[str] = None) -> Dict:
    """
    Convenience function to match CV to job.
    
    Args:
        cv_content: CV content
        job_description: Job description
        api_key: Optional API key for LLM
        
    Returns:
        Dict with analysis and recommendations
    """
    matcher = CVMatcher(api_key=api_key)
    analysis = matcher.analyze_cv_with_job(cv_content, job_description)
    modifications = matcher.generate_cv_modifications(cv_content, job_description, analysis)
    
    return {
        "analysis": analysis,
        "modifications": modifications
    }


def _job_description_to_text(job_description: Union[str, Dict]) -> str:
    """Convert parsed job data or raw text into text for matching."""
    if isinstance(job_description, str):
        return job_description

    if not isinstance(job_description, dict):
        return ""

    parts = []
    for key in ("text", "raw_text"):
        if job_description.get(key):
            parts.append(str(job_description[key]))

    skills = job_description.get("skills") or []
    if skills:
        parts.append("Skills: " + ", ".join(map(str, skills)))

    requirements = job_description.get("requirements") or []
    if requirements:
        parts.append("Requirements: " + ". ".join(map(str, requirements)))

    qualifications = job_description.get("qualifications") or []
    if qualifications:
        parts.append("Qualifications: " + ". ".join(map(str, qualifications)))

    return "\n".join(parts)


_REQUIREMENT_STOPWORDS = {
    "and", "or", "the", "a", "an", "of", "to", "in", "with", "for", "on", "at",
    "is", "are", "be", "as", "by", "from", "you", "your", "we", "our", "will",
    "have", "has", "experience", "years", "year", "plus", "strong", "ability",
    "work", "working", "team", "skills", "knowledge", "good", "excellent",
}


def _significant_words(text: str) -> List[str]:
    """Lowercase content words from a requirement line, minus filler."""
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.\-]{2,}", (text or "").lower())
    return [w for w in words if w not in _REQUIREMENT_STOPWORDS]


def _requirement_is_covered(requirement: str, cv_lower: str) -> bool:
    """Heuristic: a requirement is 'covered' when most of its content words
    appear somewhere in the CV text."""
    words = _significant_words(requirement)
    if not words:
        return False
    hits = sum(1 for w in words if w in cv_lower)
    return (hits / len(words)) >= 0.5


_STANDARD_SECTIONS = {
    "summary": ["summary", "profile", "objective", "profil"],
    "experience": ["experience", "expérience", "employment", "work history"],
    "education": ["education", "formation", "degree", "university", "école"],
    "skills": ["skills", "compétences", "competencies", "technologies"],
}


def _detect_missing_sections(cv_lower: str) -> List[str]:
    """Standard CV sections an ATS expects but the CV seems to lack."""
    missing = []
    for label, keywords in _STANDARD_SECTIONS.items():
        if not any(keyword in cv_lower for keyword in keywords):
            missing.append(label)
    return missing


def _build_ats_breakdown(
    matched: List[str],
    missing: List[str],
    job_description: Union[str, Dict],
    cv_text: str,
    recommendations: List[str],
) -> Dict:
    """A recruiter-style breakdown that replaces the single opaque score:
    matched/missing keywords, requirement coverage, weak sections, and the
    highest-leverage fixes to make next."""
    cv_lower = (cv_text or "").lower()

    requirements: List[str] = []
    if isinstance(job_description, dict):
        requirements = [str(r) for r in (job_description.get("requirements") or [])]

    requirements_covered = [
        {"requirement": req, "covered": _requirement_is_covered(req, cv_lower)}
        for req in requirements
    ]
    covered_count = sum(1 for r in requirements_covered if r["covered"])
    weak_sections = _detect_missing_sections(cv_lower)

    priority: List[str] = []
    for skill in missing[:4]:
        priority.append(
            f"Surface '{skill}' if you have it (add to Skills or evidence it in a bullet)."
        )
    for label in weak_sections:
        priority.append(f"Add a {label.capitalize()} section — ATS parsers look for it.")
    for rec in recommendations[:3]:
        if rec and rec not in priority:
            priority.append(rec)

    return {
        "matched_keywords": matched,
        "missing_keywords": missing,
        "requirements_total": len(requirements),
        "requirements_covered_count": covered_count,
        "requirements_covered": requirements_covered,
        "weak_sections": weak_sections,
        "priority_improvements": priority[:8],
    }


def _normalize_analysis(analysis: Dict, job_description: Union[str, Dict]) -> Dict:
    """Make matcher output compatible with the Flask frontend."""
    normalized = dict(analysis or {})
    skills_match = dict(normalized.get("skills_match") or {})
    cv_text = normalized.get("_cv_text", "")

    job_skills = []
    if isinstance(job_description, dict):
        job_skills = list(dict.fromkeys(job_description.get("skills") or []))

    if job_skills:
        # Always recompute coverage from the offer's skills so the displayed
        # matched/missing lists and score are deterministic and trustworthy,
        # regardless of what the LLM returned.
        matched, missing = match_skills(cv_text, job_skills)
    else:
        matched = list(skills_match.get("matched") or [])
        missing = list(skills_match.get("missing") or [])

    # Keep LLM-flagged strong matches only if they are genuinely matched.
    matched_lower = {str(s).lower() for s in matched}
    strong = [s for s in (skills_match.get("strong_matches") or []) if str(s).lower() in matched_lower]
    if not strong:
        strong = matched[:3]

    total_job_skills = len(job_skills) or (len(matched) + len(missing))
    coverage = round(len(matched) / total_job_skills * 100) if total_job_skills else 0

    skills_match.update({
        "matched": matched,
        "missing": missing,
        "strong_matches": strong,
        "total_job_skills": total_job_skills,
    })

    # When the offer exposes skills, coverage is the most honest score;
    # otherwise fall back to whatever estimate the LLM produced.
    if job_skills:
        score = coverage
    else:
        score = normalized.get("overall_score", normalized.get("match_percentage", 0))

    normalized["overall_score"] = score
    normalized["match_percentage"] = score
    normalized["skills_match"] = skills_match

    recommendations = normalized.get("recommendations") or []
    if isinstance(recommendations, dict):
        flattened = []
        for value in recommendations.values():
            if isinstance(value, list):
                flattened.extend(value)
            elif value:
                flattened.append(str(value))
        recommendations = flattened
    normalized["recommendations"] = recommendations

    # Detailed ATS breakdown (computed while we still have the CV text).
    normalized["ats"] = _build_ats_breakdown(
        matched, missing, job_description, cv_text, recommendations
    )

    normalized.pop("_cv_text", None)

    return normalized


def _escape_latex_text(value: str) -> str:
    """Escape plain text before inserting it into a LaTeX document."""
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
    }
    text = str(value)
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text


def _append_to_latex_section(latex: str, section_names: List[str], content: str) -> tuple[str, bool]:
    """Append content to the first matching LaTeX section."""
    section_pattern = "|".join(re.escape(name) for name in section_names)
    pattern = re.compile(
        rf"(\\section\*?\{{(?:{section_pattern})\}})(.*?)(?=\\section\*?\{{|\\end\{{document\}})",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(latex)
    if not match:
        return latex, False

    existing_section = match.group(0)
    if content.strip() in existing_section:
        return latex, True

    updated_section = existing_section.rstrip() + "\n\n" + content.strip() + "\n\n"
    return latex[:match.start()] + updated_section + latex[match.end():], True


def _get_latex_section(latex: str, section_names: List[str]) -> Optional[re.Match]:
    """Find the first matching LaTeX section."""
    section_pattern = "|".join(re.escape(name) for name in section_names)
    pattern = re.compile(
        rf"(\\section\*?\{{(?:{section_pattern})\}})(.*?)(?=\\section\*?\{{|\\end\{{document\}})",
        re.IGNORECASE | re.DOTALL,
    )
    return pattern.search(latex)


def _insert_before_end_document(latex: str, content: str) -> str:
    """Insert content before \\end{document}, or append if the document is partial."""
    if "\\end{document}" in latex:
        return latex.replace("\\end{document}", content.rstrip() + "\n\n\\end{document}", 1)
    return latex.rstrip() + "\n\n" + content.rstrip() + "\n"


def _insert_after_document_start(latex: str, content: str) -> str:
    """Insert content near the top of the CV, before the first real section."""
    begin_match = re.search(r"\\begin\{document\}\s*", latex)
    search_start = begin_match.end() if begin_match else 0

    first_section = re.search(r"\\section\*?\{", latex[search_start:])
    if first_section:
        idx = search_start + first_section.start()
        return latex[:idx] + content.rstrip() + "\n\n" + latex[idx:]

    maketitle_match = re.search(r"\\maketitle\s*", latex)
    if maketitle_match:
        idx = maketitle_match.end()
        return latex[:idx] + "\n\n" + content.rstrip() + "\n\n" + latex[idx:]

    if begin_match:
        idx = begin_match.end()
        return latex[:idx] + "\n\n" + content.rstrip() + "\n\n" + latex[idx:]

    return content.rstrip() + "\n\n" + latex


def _dedupe(values: List[str]) -> List[str]:
    """Deduplicate values while keeping the original order."""
    seen = set()
    result = []
    for value in values:
        key = value.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(value.strip())
    return result


def _offer_context(job_description: Union[str, Dict], job_text: str) -> Dict:
    """Extract lightweight offer context for tailored wording."""
    company = ""
    title = ""

    if isinstance(job_description, dict):
        company_info = job_description.get("company_info") or {}
        company = company_info.get("company_name", "")
        title = job_description.get("job_title") or job_description.get("title") or ""
        source_text = job_description.get("text") or job_description.get("raw_text") or job_text
    else:
        source_text = job_text

    if not title:
        for line in str(source_text).splitlines():
            line = line.strip(" -:\t")
            if 5 <= len(line) <= 100:
                title = line
                break

    return {"title": title, "company": company}


def _build_target_profile(skills: List[str], job_description: Union[str, Dict], job_text: str) -> str:
    """Create a concise profile paragraph tailored to the offer."""
    context = _offer_context(job_description, job_text)
    title = context.get("title") or "the target role"
    company = context.get("company")

    skill_text = ", ".join(_escape_latex_text(skill) for skill in skills[:6])
    role_text = _escape_latex_text(title)

    if skill_text and company:
        return (
            f"Profile tailored for {role_text} at {_escape_latex_text(company)}: "
            f"professional experience aligned with {skill_text}, with emphasis on delivery, "
            "collaboration, reliability, and measurable impact."
        )

    if skill_text:
        return (
            f"Profile tailored for {role_text}: professional experience aligned with "
            f"{skill_text}, with emphasis on delivery, collaboration, reliability, "
            "and measurable impact."
        )

    return (
        f"Profile tailored for {role_text}: relevant experience presented with stronger "
        "focus on the responsibilities and language of the offer."
    )


def _build_experience_items(skills: List[str], requirements: List[str]) -> List[str]:
    """Build grounded experience bullets using matched skills and offer requirements."""
    lower_skills = {skill.lower(): skill for skill in skills}
    items = []

    programming = [
        lower_skills[key]
        for key in lower_skills
        if key in {"python", "java", "javascript", "typescript", "sql", "react", "node.js", "django", "flask"}
    ][:4]
    devops = [
        lower_skills[key]
        for key in lower_skills
        if key in {"docker", "kubernetes", "aws", "azure", "terraform", "jenkins", "ci/cd", "git"}
    ][:4]
    practices = [
        lower_skills[key]
        for key in lower_skills
        if key in {"agile", "scrum", "testing", "debugging", "optimization", "scalability", "microservices"}
    ][:4]

    if programming:
        items.append(
            "Delivered and maintained software features using "
            + ", ".join(_escape_latex_text(skill) for skill in programming)
            + ", aligned with functional requirements and production constraints."
        )

    if devops:
        items.append(
            "Supported reliable delivery and deployment workflows with "
            + ", ".join(_escape_latex_text(skill) for skill in devops)
            + ", improving maintainability and operational readiness."
        )

    if practices:
        items.append(
            "Applied "
            + ", ".join(_escape_latex_text(skill) for skill in practices)
            + " practices to improve quality, collaboration, and long-term scalability."
        )

    if requirements and len(items) < 3:
        requirement = _escape_latex_text(requirements[0])
        items.append(
            "Aligned technical delivery with offer requirements such as "
            + requirement[:160].rstrip()
            + "."
        )

    return items[:3]


def _append_items_to_experience(latex: str, items: List[str]) -> tuple[str, bool]:
    """Append bullets inside the Experience section without creating a separate meta section."""
    if not items:
        return latex, False

    section_names = [
        "Experience",
        "Professional Experience",
        "Work Experience",
        "Experiences",
        "Expérience",
        "Expérience professionnelle",
    ]
    section_match = _get_latex_section(latex, section_names)
    if not section_match:
        return latex, False

    section = section_match.group(0)
    item_lines = "\n".join(f"    \\item {item}" for item in items)

    itemize_matches = list(re.finditer(r"\\begin\{itemize\}(?:\[[^\]]*\])?.*?\\end\{itemize\}", section, re.DOTALL))
    if itemize_matches:
        last_itemize = itemize_matches[-1]
        itemize_block = last_itemize.group(0)
        if all(item in itemize_block for item in items):
            return latex, True

        updated_itemize = itemize_block.replace("\\end{itemize}", item_lines + "\n\\end{itemize}", 1)
        updated_section = section[:last_itemize.start()] + updated_itemize + section[last_itemize.end():]
    else:
        extra_block = (
            "\n\n\\begin{itemize}[leftmargin=*]\n"
            f"{item_lines}\n"
            "\\end{itemize}\n"
        )
        updated_section = section.rstrip() + extra_block

    return latex[:section_match.start()] + updated_section + latex[section_match.end():], True


def adapt_uploaded_latex(
    cv_content: str,
    analysis: Dict,
    modifications: Dict,
    job_description: Union[str, Dict],
    job_text: str,
) -> str:
    """
    Preserve the uploaded CV and make clean job-focused edits.

    This avoids replacing the user's CV with a generated placeholder document.
    """
    optimized = cv_content
    skills_match = analysis.get("skills_match", {})
    matched = [str(skill) for skill in skills_match.get("matched", [])]
    strong_matches = [str(skill) for skill in skills_match.get("strong_matches", [])]
    grounded_skills = _dedupe(strong_matches + matched)[:12]

    if grounded_skills:
        skills_line = (
            "\\textbf{Relevant skills for this offer}: "
            + ", ".join(_escape_latex_text(skill) for skill in grounded_skills)
            + "."
        )
        optimized, found_skills = _append_to_latex_section(
            optimized,
            ["Skills", "Technical Skills", "Competences", "Compétences"],
            skills_line,
        )
        if not found_skills:
            optimized = _insert_before_end_document(
                optimized,
                "\\section{Skills}\n" + skills_line,
            )

    profile_text = _build_target_profile(grounded_skills, job_description, job_text)
    optimized, found_summary = _append_to_latex_section(
        optimized,
        ["Professional Summary", "Summary", "Profile", "Profil"],
        profile_text,
    )
    if not found_summary:
        optimized = _insert_after_document_start(
            optimized,
            "\\section{Professional Summary}\n" + profile_text,
        )

    requirements = []
    if isinstance(job_description, dict):
        requirements = [str(req) for req in job_description.get("requirements", [])]
    experience_items = _build_experience_items(grounded_skills, requirements)
    optimized, found_experience = _append_items_to_experience(optimized, experience_items)
    if experience_items and not found_experience:
        experience_section = (
            "\\section{Experience}\n"
            "\\begin{itemize}[leftmargin=*]\n"
            + "\n".join(f"    \\item {item}" for item in experience_items)
            + "\n\\end{itemize}"
        )
        optimized = _insert_before_end_document(optimized, experience_section)

    return optimized


def analyze_cv(cv_content: str, job_description: Union[str, Dict],
               api_key: Optional[str] = None) -> Dict:
    """
    Analyze CV content against a job description.

    This module-level wrapper is used by main.py and keeps the public API stable
    around the CVMatcher class implementation.
    """
    job_text = _job_description_to_text(job_description)
    matcher = CVMatcher(api_key=api_key)
    analysis = matcher.analyze_cv_with_job(cv_content, job_text)
    analysis["_cv_text"] = cv_content
    return _normalize_analysis(analysis, job_description)


def optimize_cv_for_job(cv_content: str, job_description: Union[str, Dict],
                        api_key: Optional[str] = None, language: str = "en") -> Dict:
    """
    Analyze a CV and return lightweight optimized sections for rendering.

    ``language`` (``en`` | ``fr`` | ``es``) controls the language of the
    rewritten prose and proposals.
    """
    job_text = _job_description_to_text(job_description)
    matcher = CVMatcher(api_key=api_key)

    # The analysis is a prerequisite for everything else, so it runs first.
    print("[optimize-cv] step 1/2: analysing CV vs offer…", flush=True)
    analysis = analyze_cv(cv_content, job_description, api_key=api_key)

    # Given `analysis`, these three are independent of one another and each is
    # its own LLM work (the rewrite is itself many calls), so run them at the
    # same time instead of back-to-back.
    rewritten_latex = cv_content
    rewritten_titles: List[str] = []
    section_diffs: List[Dict] = []
    proposed_additions: List[Dict] = []

    def _do_modifications():
        return matcher.generate_cv_modifications(cv_content, job_text, analysis)

    def _do_rewrite():
        from section_rewriter import rewrite_cv_sections
        return rewrite_cv_sections(
            cv_content, job_description, job_text, analysis, language=language
        )

    def _do_proposals():
        from section_rewriter import propose_additions
        return propose_additions(
            cv_content, job_description, job_text, analysis, language=language
        )

    print(
        "[optimize-cv] step 2/2: modifications + section rewrites + proposals "
        "running in parallel…",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_mod = pool.submit(_do_modifications)
        f_rewrite = pool.submit(_do_rewrite)
        f_proposals = pool.submit(_do_proposals)

        # generate_cv_modifications has its own internal fallback, so it won't
        # raise; the rewrite/proposal pair falls back to the rule-based path.
        modifications = f_mod.result()
        try:
            rewritten_latex, rewritten_titles, section_diffs = f_rewrite.result()
            proposed_additions = f_proposals.result()
        except Exception as exc:  # noqa: BLE001
            print(f"[matcher] section-by-section rewrite failed: {exc}", flush=True)

    skills_match = analysis.get("skills_match", {})
    matched = skills_match.get("matched", [])
    missing = skills_match.get("missing", [])
    keywords = modifications.get("keywords_to_add") or matched + missing
    experience_items = [
        f"    \\item {item.get('suggested_modification', '')}"
        for item in modifications.get("experience_modifications", [])
        if item.get("suggested_modification")
    ]
    experience_content = (
        "\\begin{itemize}[leftmargin=*]\n"
        + "\n".join(experience_items)
        + "\n\\end{itemize}"
    ) if experience_items else (
        "\\begin{itemize}[leftmargin=*]\n"
        "    \\item Emphasize achievements that directly match the job requirements.\n"
        "\\end{itemize}"
    )

    optimized_sections = {
        "summary": OptimizedSection(
            title="Professional Summary",
            content=modifications.get("summary_modification")
            or "Professional profile aligned with the target role requirements."
        ),
        "skills": OptimizedSection(
            title="Skills",
            content=", ".join(dict.fromkeys(map(str, keywords[:12])))
            or "Add role-relevant technical and professional skills."
        ),
        "experience": OptimizedSection(
            title="Experience",
            content=experience_content
        ),
    }

    if rewritten_titles:
        optimized_latex = rewritten_latex
    else:
        optimized_latex = adapt_uploaded_latex(
            cv_content,
            analysis,
            modifications,
            job_description,
            job_text,
        )

    return {
        "analysis": analysis,
        "modifications": modifications,
        "optimized_sections": optimized_sections,
        "optimized_latex": optimized_latex,
        "rewritten_sections": rewritten_titles,
        "section_diffs": section_diffs,
        "proposed_additions": proposed_additions,
    }
