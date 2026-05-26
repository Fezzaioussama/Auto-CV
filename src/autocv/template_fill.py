"""Fill the house template (``template_cv.tex``) section by section.

Unlike :mod:`section_rewriter`, which edits the *uploaded* CV in place, this
module pours the candidate's real content into a fixed, polished template so
every generated CV shares the same layout. The flow, per section:

1. parse ``template_cv.tex`` into preamble (with the name/contact header),
   ordered slots (``\\section`` and ``\\tinysection``), and postamble;
2. ground each slot in the matching content of the source CV plus the job
   offer, asking the LLM to *fill the template's structure* with real facts;
3. validate the result — both as LaTeX (balanced braces/environments, no
   stray top-level commands) and for faithfulness (no skill the offer wants
   but the candidate never listed); and
4. on any problem, resend the slot to the LLM with the exact errors and the
   previous attempt, retrying a few times before falling back safely.

Every slot is independent, so the slots are filled in parallel. A section the
source CV has nothing for is dropped (the model returns ``%%OMIT%%``) rather
than fabricated. The assembled document still passes through the whole-document
compile+repair loop in :mod:`latex_repair` as a final safety net.
"""

from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

try:  # importable both as a bare module (main.py) and as the src package
    from llm_client import Task, complete, get_max_workers
    from section_rewriter import (
        _clean_llm_latex,
        _introduces_unclaimed_skill,
        _language_clause,
        classify_section,
        split_latex,
    )
except ImportError:  # pragma: no cover
    from .llm_client import Task, complete, get_max_workers
    from .section_rewriter import (
        _clean_llm_latex,
        _introduces_unclaimed_skill,
        _language_clause,
        classify_section,
        split_latex,
    )


# Both a normal heading and the template's compact "\tinysection" start a slot.
SLOT_REGEX = re.compile(r"\\(?:section\*?|tinysection)\{([^{}]+)\}")
# The model returns exactly this when the source CV has nothing for a section.
OMIT_TOKEN = "%%OMIT%%"

# How many correction round-trips per section before we stop and fall back.
DEFAULT_FILL_ATTEMPTS = max(1, int(os.environ.get("SECTION_FILL_ATTEMPTS", "3")))


# Localized headings per known kind, so an English/Spanish CV does not keep the
# template's French section titles. Unknown kinds keep the template's own title.
HEADER_TITLES: Dict[str, Dict[str, str]] = {
    "summary": {"en": "Summary", "fr": "Résumé", "es": "Resumen"},
    "skills": {"en": "Skills", "fr": "Compétences", "es": "Competencias"},
    "experience": {"en": "Experience", "fr": "Expérience", "es": "Experiencia"},
    "education": {"en": "Education", "fr": "Formation", "es": "Formación"},
    "projects": {"en": "Projects", "fr": "Projets", "es": "Proyectos"},
    "certifications": {
        "en": "Certifications", "fr": "Certifications", "es": "Certificaciones",
    },
    "languages": {"en": "Languages", "fr": "Langues", "es": "Idiomas"},
}

# Section kinds we will only emit when the source CV actually has content for
# them. Core kinds (summary/skills/experience/education) are always attempted —
# the LLM still returns OMIT if there is genuinely nothing to say.
OPTIONAL_KINDS = {"projects", "certifications", "languages"}


SYSTEM_PROMPT = (
    "You are a senior technical recruiter filling ONE section of a fixed CV "
    "template with a candidate's real content, tailored to a target job "
    "offer. You receive the template section's LaTeX skeleton (the exact "
    "structure and commands to reuse), the candidate's matching source "
    "content, and structured job context.\n\n"
    "Hard rules:\n"
    "- GROUND every fact in the candidate's source content: company names, "
    "role titles, dates, schools, diplomas, certifications, languages, and "
    "any numbers. NEVER invent employers, dates, schools, projects, metrics, "
    "or achievements.\n"
    "- For skills the candidate GENUINELY has, mirror the EXACT terminology "
    "from the offer (same keywords, same casing) so ATS screening matches.\n"
    "- NEVER add a skill, tool, or technology absent from the source content. "
    "Do not insert the offer's missing skills, and never present a skill the "
    "candidate lacks as if they have it.\n"
    "- Reuse the template skeleton's LaTeX commands and environments exactly "
    "(\\headingBf, \\headingIt, resume_list, itemize, multicols, tabular, "
    "\\textbf, \\href, etc.). Replace ALL placeholder text with real content; "
    "leave no 'Nom de', 'Mois Année', 'example.com', or lorem placeholders.\n"
    "- Output ONLY the section body in LaTeX. Do NOT repeat the section "
    "header (\\section{...} / \\tinysection{...}); it is added for you.\n"
    "- Escape LaTeX specials in any prose you write (&, %, $, #, _).\n"
    "- If the candidate's source content has NOTHING that belongs in this "
    "section, output exactly " + OMIT_TOKEN + " and nothing else. Do not "
    "fabricate a section just to fill it.\n"
    "- No markdown fences, no commentary, no <think> tags."
)


def _system_prompt_for(language: str) -> str:
    return SYSTEM_PROMPT + _language_clause(language)


# ---------------------------------------------------------------------------
# Template loading + parsing
# ---------------------------------------------------------------------------


def default_template_path() -> str:
    """Path to the house template, overridable via ``TEMPLATE_CV_PATH``."""
    override = os.environ.get("TEMPLATE_CV_PATH", "").strip()
    if override:
        return override
    # This file lives at <repo>/src/autocv/template_fill.py.
    repo_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    return os.path.join(repo_root, "template_cv.tex")


def load_template(path: Optional[str] = None) -> Optional[str]:
    """Read the template file, or ``None`` if it is missing/unreadable."""
    path = path or default_template_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


@dataclass
class TemplateSlot:
    """One fillable region of the template."""

    command: str            # "section", "section*" or "tinysection"
    title: str              # the raw heading text from the template
    skeleton: str           # the placeholder body to mirror
    kind: str               # classified kind (summary/skills/...) or "other"


@dataclass
class ParsedTemplate:
    preamble: str
    slots: List[TemplateSlot]
    postamble: str


_CMD_RE = re.compile(r"\\(section\*?|tinysection)\{")


def parse_template(latex: str) -> ParsedTemplate:
    """Split the template into preamble (incl. header), slots, postamble."""
    end_doc = latex.find("\\end{document}")
    body_end = end_doc if end_doc != -1 else len(latex)
    postamble = latex[body_end:] if end_doc != -1 else ""

    matches = [m for m in SLOT_REGEX.finditer(latex) if m.start() < body_end]
    if not matches:
        return ParsedTemplate(latex[:body_end], [], postamble)

    preamble = latex[: matches[0].start()]
    slots: List[TemplateSlot] = []
    for i, match in enumerate(matches):
        body_start = match.end()
        body_close = matches[i + 1].start() if i + 1 < len(matches) else body_end
        cmd_match = _CMD_RE.match(match.group(0))
        command = cmd_match.group(1) if cmd_match else "section"
        title = match.group(1).strip()
        slots.append(
            TemplateSlot(
                command=command,
                title=title,
                skeleton=latex[body_start:body_close].strip("\n"),
                kind=classify_section(title),
            )
        )
    return ParsedTemplate(preamble, slots, postamble)


def localized_title(slot: TemplateSlot, language: str) -> str:
    """The slot's heading text, localized when the kind is known."""
    lang = (language or "en").lower()
    mapping = HEADER_TITLES.get(slot.kind)
    if mapping and lang in mapping:
        return mapping[lang]
    return slot.title


def localized_header(slot: TemplateSlot, language: str) -> str:
    """The slot's heading command, localized when the kind is known."""
    return f"\\{slot.command}{{{localized_title(slot, language)}}}"


# ---------------------------------------------------------------------------
# Personal info (header) — extracted, never invented
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_LINKEDIN_RE = re.compile(r"linkedin\.com/(?:in/)?[^\s)}\"'>]+", re.IGNORECASE)
_GITHUB_RE = re.compile(r"github\.com/[^\s)}\"'>]+", re.IGNORECASE)
_TEL_HREF_RE = re.compile(r"tel:([+\d][\d\s().-]{6,})")
_PHONE_RE = re.compile(r"(?<!\w)(\+?\d[\d\s().-]{7,}\d)(?!\w)")


@dataclass
class PersonalInfo:
    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""


def _first_name_guess(text: str) -> str:
    """Best-effort name from common LaTeX headers; '' when unsure."""
    for pat in (
        r"\\documentTitle\{([^{}]+)\}",
        r"\\name\{([^{}]+)\}\{?([^{}]*)\}?",
        r"\\Huge\{?\s*\\textbf\{([^{}]+)\}",
        r"\\textbf\{\\Huge\s*([^{}]+)\}",
    ):
        m = re.search(pat, text)
        if m:
            parts = [p.strip() for p in m.groups() if p and p.strip()]
            candidate = " ".join(parts).strip()
            # Reject obvious template placeholders.
            if candidate and "nom" not in candidate.lower() and len(candidate) < 60:
                return candidate
    return ""


def extract_personal_info(source_text: str) -> PersonalInfo:
    """Pull contact facts out of the source CV. Missing fields stay empty."""
    info = PersonalInfo()
    if not source_text:
        return info
    info.name = _first_name_guess(source_text)
    email = _EMAIL_RE.search(source_text)
    if email and "example.com" not in email.group(0):
        info.email = email.group(0)
    tel = _TEL_HREF_RE.search(source_text)
    if tel:
        info.phone = tel.group(1).strip()
    else:
        phone = _PHONE_RE.search(source_text)
        if phone:
            info.phone = phone.group(1).strip()
    li = _LINKEDIN_RE.search(source_text)
    if li and "username" not in li.group(0).lower():
        info.linkedin = li.group(0)
    gh = _GITHUB_RE.search(source_text)
    if gh and "username" not in gh.group(0).lower():
        info.github = gh.group(0)
    return info


def fill_header(preamble: str, info: PersonalInfo) -> str:
    """Replace the template's ``\\documentTitle`` placeholders with real data.

    Only fields we actually found are written; an absent field's contact
    segment is dropped rather than left as a placeholder or invented.
    """
    match = re.search(r"\\documentTitle\{([^{}]*)\}\{", preamble)
    if not match:
        return preamble

    name = info.name or "Prénom Nom"
    segments: List[str] = []
    if info.phone:
        segments.append(
            f"\\href{{tel:{info.phone.replace(' ', '')}}}{{"
            f"\\raisebox{{-0.05\\height}}\\faPhone\\ {info.phone}}}"
        )
    if info.email:
        segments.append(
            f"\\href{{mailto:{info.email}}}{{"
            f"\\raisebox{{-0.15\\height}}\\faEnvelope\\ {info.email}}}"
        )
    if info.linkedin:
        url = info.linkedin if info.linkedin.startswith("http") else f"https://{info.linkedin}"
        segments.append(
            f"\\href{{{url}}}{{\\raisebox{{-0.15\\height}}\\faLinkedin\\ {info.linkedin}}}"
        )
    if info.github:
        url = info.github if info.github.startswith("http") else f"https://{info.github}"
        segments.append(
            f"\\href{{{url}}}{{\\raisebox{{-0.15\\height}}\\faGithub\\ {info.github}}}"
        )
    contact = " ~|~\n      ".join(segments)

    # Rebuild the whole \documentTitle{...}{...} call with balanced braces.
    start = match.start()
    name_close = preamble.index("}", match.start(1))
    # The contact argument opens right after the name's closing brace.
    contact_open = preamble.index("{", name_close)
    depth = 0
    i = contact_open
    while i < len(preamble):
        if preamble[i] == "{":
            depth += 1
        elif preamble[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    contact_close = i
    new_call = f"\\documentTitle{{{name}}}{{\n      {contact}\n    }}"
    return preamble[:start] + new_call + preamble[contact_close + 1 :]


# ---------------------------------------------------------------------------
# Source-CV content per slot
# ---------------------------------------------------------------------------


def build_source_index(cv_content: str) -> Tuple[Dict[str, str], List[Tuple[str, str]]]:
    """Index the source CV by section kind and by (title, body).

    Returns ``(by_kind, sections)`` where ``by_kind`` maps a known kind to the
    concatenated bodies of every source section of that kind, and ``sections``
    is the ordered list of ``(raw_title, body)`` pairs for title matching.
    """
    _pre, sections, _post = split_latex(cv_content)
    by_kind: Dict[str, str] = {}
    ordered: List[Tuple[str, str]] = []
    for sec in sections:
        body = sec.body.strip()
        ordered.append((sec.raw_title, body))
        if sec.kind != "other":
            by_kind[sec.kind] = (by_kind.get(sec.kind, "") + "\n" + body).strip()
    return by_kind, ordered


def source_for_slot(
    slot: TemplateSlot,
    by_kind: Dict[str, str],
    sections: List[Tuple[str, str]],
    full_text: str,
) -> str:
    """Pick the source content most relevant to a template slot."""
    if slot.kind != "other" and by_kind.get(slot.kind):
        return by_kind[slot.kind]
    # Title-based match for "other" kinds (Publications, Interests, ...).
    title_l = slot.title.strip().lower()
    for raw_title, body in sections:
        rt = raw_title.strip().lower()
        if rt and (rt in title_l or title_l in rt):
            return body
    # No specific match: hand over the whole CV and rely on OMIT.
    return full_text.strip()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_COMMENT_RE = re.compile(r"(?<!\\)%.*?$", re.MULTILINE)
_BEGIN_RE = re.compile(r"\\begin\{([^{}]+)\}")
_END_RE = re.compile(r"\\end\{([^{}]+)\}")
_FORBIDDEN = (
    r"\documentclass",
    r"\begin{document}",
    r"\end{document}",
    r"\section{",
    r"\section*{",
    r"\tinysection{",
)


def _strip_for_brace_count(text: str) -> str:
    """Remove comments and escaped braces so brace counting is meaningful."""
    no_comments = _COMMENT_RE.sub("", text)
    return no_comments.replace("\\{", "").replace("\\}", "").replace("\\\\", "")


def structural_problems(body: str) -> List[str]:
    """LaTeX problems that would break compilation of this section body."""
    problems: List[str] = []
    if not body or not body.strip():
        return ["the section body is empty"]
    for token in _FORBIDDEN:
        if token in body:
            problems.append(f"contains the forbidden top-level command '{token}'")
    cleaned = _strip_for_brace_count(body)
    opens, closes = cleaned.count("{"), cleaned.count("}")
    if opens != closes:
        problems.append(
            f"unbalanced curly braces ({opens} '{{' vs {closes} '}}')"
        )
    begins = _BEGIN_RE.findall(body)
    ends = _END_RE.findall(body)
    for name in set(begins) | set(ends):
        nb, ne = begins.count(name), ends.count(name)
        if nb != ne:
            problems.append(
                f"unbalanced environment '{name}' ({nb} \\begin vs {ne} \\end)"
            )
    return problems


def _has_leftover_placeholder(body: str) -> bool:
    """Cheap check for obviously-unfilled template placeholders."""
    needles = (
        "nom de l", "mois année", "intitulé du", "titre du projet",
        "example.com", "prénom nom", "catégorie 1", "langue 1",
        "nom de la certification", "description de la mission",
    )
    low = body.lower()
    return any(n in low for n in needles)


def faithfulness_problems(
    new_body: str, source_text: str, missing_skills: List[str]
) -> List[str]:
    """Content problems: invented skills, or leftover template placeholders."""
    problems: List[str] = []
    if _introduces_unclaimed_skill(source_text, new_body, missing_skills or []):
        offenders = [
            s for s in (missing_skills or [])
            if s and s.lower() in new_body.lower()
        ]
        problems.append(
            "claims skill(s) the candidate never listed in their CV: "
            + (", ".join(offenders[:5]) or "a skill from the offer's gap list")
        )
    if _has_leftover_placeholder(new_body):
        problems.append(
            "still contains unfilled template placeholder text "
            "(e.g. 'Nom de...', 'Mois Année', 'example.com')"
        )
    return problems


def validate_filled_section(
    body: str, source_text: str, missing_skills: List[str]
) -> List[str]:
    """All problems (structure + faithfulness). Empty list means valid."""
    return structural_problems(body) + faithfulness_problems(
        body, source_text, missing_skills
    )


# ---------------------------------------------------------------------------
# Prompting + the per-section fill/correct loop
# ---------------------------------------------------------------------------


def _job_facts(job_description: Union[str, Dict], analysis: Dict) -> Dict[str, str]:
    skills_match = (analysis or {}).get("skills_match", {}) or {}
    matched = ", ".join(map(str, skills_match.get("matched", [])[:12])) or "—"
    missing = ", ".join(map(str, skills_match.get("missing", [])[:12])) or "—"
    requirements: List[str] = []
    job_title = ""
    company = ""
    if isinstance(job_description, dict):
        requirements = [str(r) for r in (job_description.get("requirements") or [])][:8]
        job_title = job_description.get("job_title") or job_description.get("title") or ""
        company = (job_description.get("company_info") or {}).get("company_name", "")
    return {
        "matched": matched,
        "missing": missing,
        "requirements": str(requirements or "see offer text"),
        "job_title": job_title or "unspecified",
        "company": company or "unspecified",
    }


def _build_fill_prompt(
    slot: TemplateSlot, header: str, source_content: str,
    job_text: str, facts: Dict[str, str],
) -> str:
    return (
        f"Target role: {facts['job_title']}\n"
        f"Company: {facts['company']}\n"
        f"Top requirements: {facts['requirements']}\n"
        f"Skills the candidate already has that the offer wants (safe to "
        f"emphasize, re-label with the offer's exact wording): {facts['matched']}\n"
        f"Skills the offer wants but the candidate has NOT demonstrated "
        f"(DO NOT add or claim these): {facts['missing']}\n\n"
        f"Job offer text (truncated):\n{(job_text or '')[:2000]}\n\n"
        f"--- Template section to fill ---\n"
        f"Heading (added for you, do NOT repeat it): {header}\n"
        f"Classified as: {slot.kind}\n"
        f"LaTeX skeleton to mirror exactly:\n{slot.skeleton}\n"
        f"--- end skeleton ---\n\n"
        f"--- Candidate source content for this section ---\n"
        f"{source_content.strip() or '(none found in the CV)'}\n"
        f"--- end source ---\n\n"
        f"Fill the skeleton with the candidate's real, offer-tailored content "
        f"following the hard rules. Output only the LaTeX body, or "
        f"{OMIT_TOKEN} if the source has nothing for this section."
    )


def _build_correction_prompt(
    slot: TemplateSlot, header: str, previous: str, problems: List[str],
) -> str:
    bullet_problems = "\n".join(f"- {p}" for p in problems)
    return (
        f"Your previous attempt at the '{slot.title}' section body was "
        f"rejected. Fix EVERY problem below while keeping all real facts and "
        f"the template structure. Do not introduce new problems.\n\n"
        f"Problems:\n{bullet_problems}\n\n"
        f"Heading (do NOT repeat it): {header}\n"
        f"Your previous (rejected) body:\n{previous}\n\n"
        f"Return the corrected LaTeX body only, or {OMIT_TOKEN} if the section "
        f"should be dropped."
    )


def _call_llm(user_prompt: str, system_prompt: str, max_tokens: int = 1400) -> Optional[str]:
    return complete(
        user_prompt,
        system_prompt=system_prompt,
        task=Task.SECTION_FILL,
        temperature=0.2,
        max_tokens=max_tokens,
        log_prefix="template-fill",
    )


@dataclass
class SlotResult:
    slot: TemplateSlot
    header: str
    body: Optional[str]            # None => omit this section
    source: str = ""
    attempts: int = 0
    omitted: bool = False
    fell_back: bool = False


def fill_slot(
    slot: TemplateSlot,
    *,
    source_content: str,
    full_source_text: str,
    job_description: Union[str, Dict],
    job_text: str,
    analysis: Dict,
    language: str,
    max_attempts: int = DEFAULT_FILL_ATTEMPTS,
) -> SlotResult:
    """Fill one slot, validating and resending to the LLM until correct."""
    header = localized_header(slot, language)
    facts = _job_facts(job_description, analysis)
    missing_skills = (analysis or {}).get("skills_match", {}).get("missing", [])
    system = _system_prompt_for(language)

    # Optional sections with no grounding content are dropped without a call.
    if slot.kind in OPTIONAL_KINDS and not source_content.strip():
        return SlotResult(slot, header, None, source_content, 0, omitted=True)

    user_prompt = _build_fill_prompt(
        slot, header, source_content, job_text, facts
    )
    best_valid: Optional[str] = None
    last_clean = ""

    for attempt in range(1, max_attempts + 1):
        raw = _call_llm(user_prompt, system)
        if not raw:
            break
        cleaned = _clean_llm_latex(raw)
        last_clean = cleaned

        if cleaned.strip().rstrip(".") == OMIT_TOKEN or cleaned.strip() == OMIT_TOKEN:
            return SlotResult(slot, header, None, source_content, attempt, omitted=True)

        problems = validate_filled_section(
            cleaned, full_source_text, missing_skills
        )
        if not problems:
            return SlotResult(slot, header, cleaned, source_content, attempt)

        # Keep the first structurally-valid attempt as a fallback candidate.
        if best_valid is None and not structural_problems(cleaned):
            best_valid = cleaned

        print(
            f"[template-fill]   ✗ '{slot.title}' attempt {attempt} rejected: "
            f"{'; '.join(problems)}",
            flush=True,
        )
        if attempt < max_attempts:
            user_prompt = _build_correction_prompt(
                slot, header, cleaned, problems
            )

    # Out of attempts: prefer a structurally-valid (compilable) body so the
    # final document still renders; otherwise drop the section rather than
    # emit broken LaTeX or a fabricated one.
    if best_valid is not None:
        return SlotResult(
            slot, header, best_valid, source_content, max_attempts, fell_back=True
        )
    if last_clean and not structural_problems(last_clean):
        return SlotResult(
            slot, header, last_clean, source_content, max_attempts, fell_back=True
        )
    return SlotResult(
        slot, header, None, source_content, max_attempts, omitted=True, fell_back=True
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


@dataclass
class FillReport:
    latex: str
    filled_titles: List[str] = field(default_factory=list)
    omitted_titles: List[str] = field(default_factory=list)
    section_diffs: List[Dict] = field(default_factory=list)
    used_template: bool = True


def fill_template_cv(
    cv_content: str,
    job_description: Union[str, Dict],
    job_text: str,
    analysis: Dict,
    *,
    language: str = "en",
    template: Optional[str] = None,
    max_attempts: int = DEFAULT_FILL_ATTEMPTS,
) -> FillReport:
    """Produce a job-tailored CV by filling the house template in parallel.

    Returns a :class:`FillReport`. ``used_template`` is ``False`` (and
    ``latex`` is the unchanged source) when the template is missing or has no
    slots, so callers can fall back to the in-place rewrite path.
    """
    template_src = template if template is not None else load_template()
    if not template_src:
        print("[template-fill] template not found; skipping template fill.", flush=True)
        return FillReport(cv_content, [], [], [], used_template=False)

    parsed = parse_template(template_src)
    if not parsed.slots:
        print("[template-fill] template has no slots; skipping.", flush=True)
        return FillReport(cv_content, [], [], [], used_template=False)

    by_kind, sections = build_source_index(cv_content)
    full_text = cv_content or ""
    info = extract_personal_info(cv_content)
    preamble = fill_header(parsed.preamble, info)

    total = len(parsed.slots)
    workers = min(get_max_workers(), total)
    print(
        f"[template-fill] filling {total} template section(s) in parallel "
        f"(up to {workers} at once)…",
        flush=True,
    )

    def _worker(item):
        i, slot = item
        print(f"[template-fill]   → start ({i}/{total}) {slot.title}", flush=True)
        source_content = source_for_slot(slot, by_kind, sections, full_text)
        res = fill_slot(
            slot,
            source_content=source_content,
            full_source_text=full_text,
            job_description=job_description,
            job_text=job_text,
            analysis=analysis,
            language=language,
            max_attempts=max_attempts,
        )
        status = "omit" if res.omitted else ("fallback" if res.fell_back else "ok")
        print(
            f"[template-fill]   ✓ done  ({i}/{total}) {slot.title} [{status}]",
            flush=True,
        )
        return res

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results: List[SlotResult] = list(
            pool.map(_worker, enumerate(parsed.slots, start=1))
        )

    parts: List[str] = [preamble.rstrip() + "\n\n"]
    filled_titles: List[str] = []
    omitted_titles: List[str] = []
    diffs: List[Dict] = []
    for res in results:
        display_title = localized_title(res.slot, language)
        if res.body is None:
            omitted_titles.append(display_title)
            continue
        parts.append(res.header + "\n" + res.body.strip() + "\n\n")
        filled_titles.append(display_title)
        diffs.append({
            "title": display_title,
            "kind": res.slot.kind,
            "before": res.source.strip(),
            "after": res.body.strip(),
        })

    parts.append(parsed.postamble)
    return FillReport(
        latex="".join(parts),
        filled_titles=filled_titles,
        omitted_titles=omitted_titles,
        section_diffs=diffs,
        used_template=True,
    )
