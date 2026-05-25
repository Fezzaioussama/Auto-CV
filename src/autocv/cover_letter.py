"""Generate application outreach from the CV + job context.

Produces a full cover letter and short messages (recruiter note, LinkedIn DM,
application email) in one LLM call, returning a dict keyed by ``kind``. Falls
back to grounded templates when the model is unavailable so the feature always
returns something usable.
"""

from __future__ import annotations

import re
from typing import Dict, List, Union

try:  # importable both as a bare module (main.py) and as the src package
    from llm_client import Task
    from llm_json import request_json
    from section_rewriter import LANGUAGE_NAMES
except ImportError:  # pragma: no cover
    from .llm_client import Task
    from .llm_json import request_json
    from .section_rewriter import LANGUAGE_NAMES


# What the UI can request, with per-kind guidance baked into the prompt.
KINDS: Dict[str, str] = {
    "cover_letter": "A full cover letter, 3-4 short paragraphs, professional and specific.",
    "recruiter_message": "A short message to a recruiter, 4-6 sentences, warm and direct.",
    "linkedin_message": "A LinkedIn connection/DM note under 300 characters.",
    "email": "A concise application email with a subject line, ready to send.",
}


def _latex_to_text(latex: str) -> str:
    """Best-effort strip of LaTeX commands to readable text for prompting."""
    text = re.sub(r"<think>.*?</think>", "", latex or "", flags=re.DOTALL)
    text = re.sub(r"\\section\*?\{([^}]*)\}", r"\n\1\n", text)
    text = re.sub(r"\\textbf\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\textit\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\item", "- ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})?", " ", text)
    text = text.replace("{", "").replace("}", "").replace("\\\\", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def _job_context(job_description: Union[str, Dict]) -> Dict[str, str]:
    if isinstance(job_description, dict):
        return {
            "title": job_description.get("job_title") or job_description.get("title") or "",
            "company": (job_description.get("company_info") or {}).get("company_name", ""),
            "text": job_description.get("text") or job_description.get("raw_text") or "",
        }
    return {"title": "", "company": "", "text": str(job_description or "")}


_SYSTEM_PROMPT = (
    "You are an expert career writer. Using ONLY facts present in the candidate's "
    "CV, write application outreach tailored to the job. Never invent employers, "
    "skills, metrics, or qualifications the CV does not support. Keep a confident, "
    "human, non-generic tone. Where a fact is required but missing (e.g. a hiring "
    "manager's name), use a clearly bracketed placeholder like [Hiring Manager].\n\n"
    "Respond with a JSON object ONLY (no prose, no markdown fences, no <think> "
    "tags). Keys are the requested kinds; each value is the finished text as a "
    "single string (use \\n for line breaks)."
)


def _build_prompt(cv_text: str, ctx: Dict[str, str], kinds: List[str],
                  applicant_name: str, language: str) -> str:
    wanted = "\n".join(f'- "{k}": {KINDS[k]}' for k in kinds if k in KINDS)
    lang = LANGUAGE_NAMES.get((language or "en").lower(), "English")
    return (
        f"Write the outreach in {lang}.\n"
        f"Candidate name: {applicant_name or '[Your Name]'}\n"
        f"Target role: {ctx['title'] or 'the role'}\n"
        f"Company: {ctx['company'] or 'the company'}\n\n"
        f"Requested items (use these exact JSON keys):\n{wanted}\n\n"
        f"--- Candidate CV (facts you may use) ---\n{cv_text[:5000]}\n\n"
        f"--- Job offer ---\n{ctx['text'][:3000]}\n\n"
        f"Return the JSON object now."
    )


def _fallback(kind: str, ctx: Dict[str, str], applicant_name: str) -> str:
    role = ctx["title"] or "the role"
    company = ctx["company"] or "your company"
    name = applicant_name or "[Your Name]"
    if kind == "linkedin_message":
        return (
            f"Hi [Name], I'm very interested in the {role} role at {company}. "
            f"My background lines up well with what you're looking for — "
            f"would love to connect. — {name}"
        )
    if kind == "recruiter_message":
        return (
            f"Hello [Recruiter], I'd like to apply for the {role} position at {company}. "
            f"My experience maps closely to the requirements in your posting, and I'd "
            f"welcome the chance to discuss how I can contribute. I've attached my CV. "
            f"Thank you for your time.\n\n{name}"
        )
    if kind == "email":
        return (
            f"Subject: Application for {role}\n\n"
            f"Dear [Hiring Manager],\n\n"
            f"I'm writing to apply for the {role} position at {company}. My experience "
            f"aligns with the requirements outlined in your posting, and I've attached "
            f"my tailored CV for your review.\n\n"
            f"I would welcome the opportunity to discuss my fit for the role.\n\n"
            f"Best regards,\n{name}"
        )
    return (
        f"Dear [Hiring Manager],\n\n"
        f"I am excited to apply for the {role} position at {company}. The role aligns "
        f"closely with my professional experience, and I am confident I can make a "
        f"meaningful contribution.\n\n"
        f"Across my career I have focused on delivering reliable, high-quality work and "
        f"collaborating effectively with my teams. I would relish the opportunity to "
        f"bring that same focus to {company}.\n\n"
        f"Thank you for considering my application. I would welcome the chance to "
        f"discuss how my background fits your needs.\n\n"
        f"Sincerely,\n{name}"
    )


def generate_outreach(
    cv: str,
    job_description: Union[str, Dict],
    *,
    kinds: List[str] = None,
    language: str = "en",
    applicant_name: str = "",
) -> Dict[str, str]:
    """Return ``{kind: text}`` for each requested outreach kind."""
    kinds = [k for k in (kinds or ["cover_letter"]) if k in KINDS] or ["cover_letter"]
    ctx = _job_context(job_description)
    cv_text = _latex_to_text(cv) if "\\" in (cv or "") else (cv or "")

    results: Dict[str, str] = {}
    try:
        obj, _meta = request_json(
            _build_prompt(cv_text, ctx, kinds, applicant_name, language),
            system_prompt=_SYSTEM_PROMPT,
            expect="object",
            task=Task.PROPOSAL,
            temperature=0.5,
            max_tokens=1800,
            log_prefix="cover-letter",
        )
        if isinstance(obj, dict):
            results = {k: str(v) for k, v in obj.items()}
    except Exception as exc:  # noqa: BLE001
        print(f"[cover-letter] generation failed, using fallback: {exc}", flush=True)

    # Guarantee every requested kind comes back with usable content.
    for kind in kinds:
        if not results.get(kind, "").strip():
            results[kind] = _fallback(kind, ctx, applicant_name)
    return {k: results[k] for k in kinds}
