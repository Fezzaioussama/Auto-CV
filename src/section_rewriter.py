"""Section-by-section LLM rewrite for an uploaded LaTeX CV.

The goal is a coherent, job-tailored CV: every \\section{...} in the user's
LaTeX is sent to vLLM individually with the job context, and the LLM is
asked to rewrite just that section's body — preserving facts, reusing the
same LaTeX commands, optionally adding a couple of bullets that connect
existing experience to the offer.
"""

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

import requests


VLLM_API_URL = os.environ.get("VLLM_API_URL", "http://127.0.0.1:8002/v1")
VLLM_MODEL = os.environ.get("VLLM_MODEL", "Qwen/Qwen3-Coder-Next-FP8")
VLLM_API_KEY = os.environ.get("VLLM_API_KEY")
VLLM_CONNECT_TIMEOUT = float(os.environ.get("VLLM_CONNECT_TIMEOUT", "10"))
VLLM_TIMEOUT = float(os.environ.get("VLLM_TIMEOUT", "3600"))
# (connect, read): fail fast if unreachable, allow a slow model a long read.
VLLM_REQUEST_TIMEOUT = (VLLM_CONNECT_TIMEOUT, VLLM_TIMEOUT)
# Section rewrites are independent of each other, so they run concurrently.
# Cap how many hit the vLLM server at once (it batches, but be polite).
VLLM_MAX_WORKERS = max(1, int(os.environ.get("VLLM_MAX_WORKERS", "5")))


SECTION_REGEX = re.compile(r"\\section\*?\{([^{}]+)\}")


SECTION_TYPE_KEYWORDS = {
    "summary": [
        "summary", "profile", "objective", "profil", "objectif",
        "résumé", "resume", "about me",
    ],
    "skills": [
        "skills", "competences", "compétences", "technical skills",
        "tech stack", "technologies",
    ],
    "experience": [
        "experience", "expérience", "work experience",
        "professional experience", "employment", "career history",
    ],
    "education": [
        "education", "éducation", "formation", "academic background",
        "studies",
    ],
    "projects": ["projects", "projets", "portfolio", "selected projects"],
    "certifications": [
        "certifications", "certificates", "certificats", "courses",
    ],
    "languages": ["languages", "langues"],
}


SYSTEM_PROMPT = (
    "You are a senior technical recruiter rewriting one CV section at a time "
    "to match a target job offer. You receive a single section body in LaTeX "
    "and structured job context. Your job is REPHRASING, not invention: keep "
    "the candidate's real content and re-word it so it speaks the offer's "
    "language. Rewrite ONLY the body in LaTeX.\n\n"
    "Hard rules:\n"
    "- Keep every concrete fact from the original: company names, role titles, "
    "employment dates, school names, diplomas, certification names, languages, "
    "and any numeric metrics. Never invent employers, dates, schools, or fake "
    "achievements.\n"
    "- For skills the candidate GENUINELY has, mirror the EXACT terminology "
    "used in the offer (same keywords, same casing) so automated screening "
    "(ATS) matches them.\n"
    "- NEVER add a skill, tool, or technology that is absent from the original "
    "section. Do NOT insert the offer's missing skills, and never present a "
    "skill the candidate lacks as if they possess it. A Skills list may only "
    "be reordered and re-labelled, not extended with new technologies.\n"
    "- Prefer rephrasing and reordering existing bullets, and sharpening weak "
    "verbs into strong action verbs. You may add AT MOST ONE new bullet, and "
    "only to reframe existing experience as a transferable skill the offer "
    "asks for — never to assert a new job or unproven result.\n"
    "- Preserve all LaTeX commands/environments already used in the body "
    "(itemize, cventry, \\textbf, \\textit, \\\\, etc.). Do not change the "
    "section header — it is not part of your output.\n"
    "- Escape LaTeX special characters in any new text you write "
    "(&, %, $, #, _).\n"
    "- Output only valid LaTeX for the section body. No markdown fences, no "
    "commentary, no <think> tags."
)


@dataclass
class LatexSection:
    """One \\section{...} block of a LaTeX document."""

    header: str
    raw_title: str
    body: str
    start: int
    end: int

    @property
    def kind(self) -> str:
        return classify_section(self.raw_title)


def classify_section(title: str) -> str:
    """Map a section title to a known type, or 'other'."""
    lowered = title.strip().lower()
    for kind, keywords in SECTION_TYPE_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return kind
    return "other"


def split_latex(latex: str) -> Tuple[str, List[LatexSection], str]:
    """Split a LaTeX document into (preamble, sections, postamble).

    Postamble starts at \\end{document} when present. Sections run from one
    \\section{...} header to the next (or to \\end{document}). If the
    document has no \\section commands the section list is empty.
    """
    end_doc = latex.find("\\end{document}")
    body_end = end_doc if end_doc != -1 else len(latex)
    postamble = latex[body_end:] if end_doc != -1 else ""

    matches = [m for m in SECTION_REGEX.finditer(latex) if m.start() < body_end]
    if not matches:
        return latex[:body_end], [], postamble

    preamble = latex[: matches[0].start()]
    sections: List[LatexSection] = []
    for i, match in enumerate(matches):
        body_start = match.end()
        body_close = matches[i + 1].start() if i + 1 < len(matches) else body_end
        sections.append(
            LatexSection(
                header=match.group(0),
                raw_title=match.group(1).strip(),
                body=latex[body_start:body_close],
                start=match.start(),
                end=body_close,
            )
        )
    return preamble, sections, postamble


def assemble(
    preamble: str, sections: List[LatexSection], postamble: str
) -> str:
    """Inverse of split_latex."""
    parts: List[str] = [preamble]
    for section in sections:
        parts.append(section.header)
        if not section.body.startswith("\n"):
            parts.append("\n")
        parts.append(section.body)
    parts.append(postamble)
    return "".join(parts)


def _call_vllm(
    user_prompt: str,
    *,
    system_prompt: str = SYSTEM_PROMPT,
    max_tokens: int = 1500,
    temperature: float = 0.25,
) -> Optional[str]:
    """POST a chat completion to the configured vLLM endpoint."""
    headers = {"Content-Type": "application/json"}
    if VLLM_API_KEY:
        headers["Authorization"] = f"Bearer {VLLM_API_KEY}"

    try:
        response = requests.post(
            f"{VLLM_API_URL}/chat/completions",
            json={
                "model": VLLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            },
            headers=headers,
            timeout=VLLM_REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        print(f"[section-rewriter] vLLM call failed: {exc}", flush=True)
        return None

    if response.status_code != 200:
        print(
            f"[section-rewriter] vLLM HTTP {response.status_code}: "
            f"{response.text[:200]}",
            flush=True,
        )
        return None

    try:
        data = response.json()
    except ValueError:
        return None
    return (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        or None
    )


_FENCE_RE = re.compile(r"```(?:latex|tex)?\s*\n?(.*?)```", re.DOTALL)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _clean_llm_latex(response: str) -> str:
    """Strip code fences, think tags, and leading/trailing prose."""
    text = _THINK_RE.sub("", response).strip()
    fence = _FENCE_RE.search(text)
    if fence:
        text = fence.group(1)
    return text.strip("\n").rstrip() + "\n"


def _looks_like_valid_section_body(text: str) -> bool:
    """Cheap sanity check: must not contain forbidden top-level commands."""
    if not text or not text.strip():
        return False
    forbidden = (
        r"\documentclass",
        r"\begin{document}",
        r"\end{document}",
        r"\section{",
        r"\section*{",
    )
    return not any(token in text for token in forbidden)


def _introduces_unclaimed_skill(
    old_body: str, new_body: str, missing_skills: List[str]
) -> bool:
    """Whether the rewrite added an offer skill the candidate did not have.

    Compares the new body against the original with the same alias-aware
    matcher used for scoring. A skill counts as fabricated only if it appears
    in the rewrite but was absent from the original section, so genuinely
    listed skills (that the matcher may have missed elsewhere) are never
    penalised. This is the honesty guarantee behind "just rephrase".
    """
    if not missing_skills:
        return False
    try:
        from matcher import _text_contains_skill
    except Exception:  # noqa: BLE001 - guardrail must never crash the rewrite
        return False

    old_lower = (old_body or "").lower()
    new_lower = (new_body or "").lower()
    for skill in missing_skills:
        if _text_contains_skill(new_lower, skill) and not _text_contains_skill(
            old_lower, skill
        ):
            return True
    return False


def _build_user_prompt(
    section: LatexSection,
    job_description: Union[str, Dict],
    job_text: str,
    analysis: Dict,
) -> str:
    """Compose the per-section user prompt sent to vLLM."""
    skills_match = analysis.get("skills_match", {}) if analysis else {}
    matched = ", ".join(map(str, skills_match.get("matched", [])[:12])) or "—"
    missing = ", ".join(map(str, skills_match.get("missing", [])[:12])) or "—"

    requirements: List[str] = []
    job_title = ""
    company = ""
    if isinstance(job_description, dict):
        requirements = [
            str(req) for req in (job_description.get("requirements") or [])
        ][:8]
        job_title = (
            job_description.get("job_title")
            or job_description.get("title")
            or ""
        )
        company = (
            (job_description.get("company_info") or {}).get("company_name", "")
        )

    truncated_job_text = (job_text or "")[:2200]

    return (
        f"Job title: {job_title or 'unspecified'}\n"
        f"Company: {company or 'unspecified'}\n"
        f"Top requirements: {requirements or 'see offer text'}\n"
        f"Skills the candidate already has that the offer wants (safe to "
        f"emphasize and re-label using the offer's exact wording): {matched}\n"
        f"Skills the offer wants but the candidate has NOT demonstrated "
        f"(DO NOT add these to any skills list and DO NOT claim them; at most "
        f"reframe genuinely related existing experience): {missing}\n\n"
        f"Job offer text (truncated):\n{truncated_job_text}\n\n"
        f"--- CV section to rewrite ---\n"
        f"Section header (do NOT include in your output): "
        f"{section.header}\n"
        f"Classified as: {section.kind}\n"
        f"Current LaTeX body:\n{section.body.strip()}\n"
        f"--- end of section ---\n\n"
        f"Rewrite the LaTeX body so this section reads as a coherent, "
        f"job-tailored block. Emphasize matched skills naturally, keep the "
        f"existing LaTeX structure, and respect the hard rules from the "
        f"system message. Output only the new LaTeX body."
    )


def rewrite_section(
    section: LatexSection,
    job_description: Union[str, Dict],
    job_text: str,
    analysis: Dict,
) -> Optional[str]:
    """Ask vLLM to rewrite one section body. Returns None on failure."""
    if section.kind == "other":
        return None

    prompt = _build_user_prompt(section, job_description, job_text, analysis)
    raw = _call_vllm(prompt)
    if not raw:
        return None

    cleaned = _clean_llm_latex(raw)
    if not _looks_like_valid_section_body(cleaned):
        print(
            f"[section-rewriter] discarded suspicious LLM output for "
            f"'{section.raw_title}'",
            flush=True,
        )
        return None

    missing_skills = []
    if analysis:
        missing_skills = (analysis.get("skills_match") or {}).get("missing", [])
    if _introduces_unclaimed_skill(section.body, cleaned, missing_skills):
        print(
            f"[section-rewriter] discarded '{section.raw_title}': rewrite "
            f"introduced a skill the candidate had not listed",
            flush=True,
        )
        return None

    return cleaned


def rewrite_cv_sections(
    latex: str,
    job_description: Union[str, Dict],
    job_text: str,
    analysis: Dict,
) -> Tuple[str, List[str]]:
    """Walk every \\section in the CV and rewrite it via vLLM.

    Returns ``(new_latex, rewritten_titles)``. ``rewritten_titles`` is
    empty when no section was successfully rewritten — callers can use
    that as a signal to fall back to the rule-based pipeline.
    """
    preamble, sections, postamble = split_latex(latex)
    if not sections:
        return latex, []

    total = len(sections)
    workers = min(VLLM_MAX_WORKERS, total)
    print(
        f"[section-rewriter] rewriting {total} section(s) in parallel "
        f"(up to {workers} at once)…",
        flush=True,
    )

    def _worker(item):
        i, section = item
        title = (section.raw_title or "section").strip()
        print(f"[section-rewriter]   → start ({i}/{total}) {title}", flush=True)
        new_body = rewrite_section(section, job_description, job_text, analysis)
        print(f"[section-rewriter]   ✓ done  ({i}/{total}) {title}", flush=True)
        return section, new_body

    # rewrite_section only reads its section, so the calls are independent.
    # map() preserves input order; we mutate sections afterwards on the main
    # thread to keep ordering and title collection deterministic.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_worker, enumerate(sections, start=1)))

    rewritten_titles: List[str] = []
    for section, new_body in results:
        if new_body:
            section.body = "\n" + new_body
            rewritten_titles.append(section.raw_title)

    return assemble(preamble, sections, postamble), rewritten_titles


# ---------------------------------------------------------------------------
# Proposing brand-new sections / content for gaps the offer asks for
# ---------------------------------------------------------------------------

PROPOSAL_SYSTEM_PROMPT = (
    "You are a career coach helping a candidate strengthen their CV for ONE "
    "specific job offer. Here you only PROPOSE optional additions — you do not "
    "edit existing content, and you NEVER fabricate facts.\n\n"
    "Rules:\n"
    "- Only propose additions that genuinely help for THIS offer: a section "
    "the CV is missing but the offer clearly values (e.g. Projects, "
    "Certifications, a tailored Professional Summary), or a concrete place to "
    "surface a required skill the CV currently lacks.\n"
    "- Do NOT propose a section the CV already has.\n"
    "- For anything only the candidate can know (employers, dates, project "
    "names, metrics, or a skill they may not have), insert a clearly bracketed "
    "placeholder such as [your project name] or [e.g. 6 months with Docker]. "
    "Never invent these.\n"
    "- Each proposal's \"latex\" must be a self-contained snippet that can be "
    "pasted before \\end{document}: it MUST start with \\section{...} and may "
    "use itemize. Escape LaTeX specials (&, %, $, #, _).\n"
    "- Respond with a JSON array ONLY — no prose, no markdown fences, no "
    "<think> tags. Each element is "
    '{"type": "new_section" | "skill_gap", "title": "short label", '
    '"reason": "why it helps for this offer", "latex": "the LaTeX snippet"}.'
)


def _looks_like_valid_proposal(latex_snippet: str) -> bool:
    """A proposal must be a section snippet, not a whole document."""
    if not latex_snippet or not latex_snippet.strip():
        return False
    forbidden = (r"\documentclass", r"\begin{document}", r"\end{document}")
    if any(token in latex_snippet for token in forbidden):
        return False
    return "\\section" in latex_snippet


def _parse_proposals(raw: str) -> List[Dict]:
    """Extract the JSON array of proposals from the model response."""
    text = _THINK_RE.sub("", raw).strip()
    fence = _FENCE_RE.search(text)
    if fence:
        text = fence.group(1)
    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end <= start:
        return []
    try:
        data = json.loads(text[start:end])
    except (ValueError, TypeError):
        return []
    return data if isinstance(data, list) else []


def _build_proposal_prompt(
    existing_titles: List[str],
    matched: str,
    missing: str,
    requirements: List[str],
    job_title: str,
    company: str,
    job_text: str,
    max_items: int,
) -> str:
    return (
        f"Target role: {job_title or 'unspecified'}\n"
        f"Company: {company or 'unspecified'}\n"
        f"Sections already in the CV (do not duplicate these): "
        f"{existing_titles or 'none detected'}\n"
        f"Skills the candidate already has: {matched}\n"
        f"Skills the offer wants but the CV is missing: {missing}\n"
        f"Top offer requirements: {requirements or 'see offer text'}\n\n"
        f"Job offer text (truncated):\n{(job_text or '')[:2000]}\n\n"
        f"Propose AT MOST {max_items} optional additions that would make this "
        f"CV stronger for the offer, following the rules. Use bracketed "
        f"placeholders for any fact the candidate must supply. Respond with "
        f"the JSON array only."
    )


def propose_additions(
    latex: str,
    job_description: Union[str, Dict],
    job_text: str,
    analysis: Dict,
    *,
    max_items: int = 4,
) -> List[Dict]:
    """Ask the LLM for optional new sections/content the CV is missing.

    Returns a list of ``{type, title, reason, latex}`` proposals. New content
    uses bracketed placeholders for anything the candidate must supply, so the
    candidate stays in control and nothing is fabricated. Returns an empty
    list when the model is unreachable or returns nothing usable.
    """
    _, sections, _ = split_latex(latex)
    existing_titles = [s.raw_title for s in sections]
    existing_kinds = {s.kind for s in sections if s.kind != "other"}

    skills_match = (analysis or {}).get("skills_match", {}) or {}
    matched = ", ".join(map(str, skills_match.get("matched", [])[:12])) or "—"
    missing = ", ".join(map(str, skills_match.get("missing", [])[:12])) or "—"

    requirements: List[str] = []
    job_title = ""
    company = ""
    if isinstance(job_description, dict):
        requirements = [
            str(req) for req in (job_description.get("requirements") or [])
        ][:8]
        job_title = (
            job_description.get("job_title")
            or job_description.get("title")
            or ""
        )
        company = (job_description.get("company_info") or {}).get(
            "company_name", ""
        )

    prompt = _build_proposal_prompt(
        existing_titles, matched, missing, requirements, job_title, company,
        job_text, max_items,
    )
    raw = _call_vllm(
        prompt,
        system_prompt=PROPOSAL_SYSTEM_PROMPT,
        max_tokens=1800,
        temperature=0.3,
    )
    if not raw:
        return []

    proposals: List[Dict] = []
    seen_titles = {t.strip().lower() for t in existing_titles}
    for item in _parse_proposals(raw):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        snippet = str(item.get("latex") or "").strip()
        if not title or not _looks_like_valid_proposal(snippet):
            continue
        # Skip proposals that duplicate an existing section (by title or kind).
        proposed_kind = classify_section(title)
        title_match = SECTION_REGEX.search(snippet)
        proposed_section_title = (
            title_match.group(1).strip() if title_match else title
        )
        if proposed_section_title.strip().lower() in seen_titles:
            continue
        if proposed_kind != "other" and proposed_kind in existing_kinds:
            continue
        proposals.append(
            {
                "type": str(item.get("type") or "new_section"),
                "title": title,
                "reason": str(item.get("reason") or "").strip(),
                "latex": snippet,
            }
        )
        seen_titles.add(proposed_section_title.strip().lower())
        if len(proposals) >= max_items:
            break

    return proposals
