"""LaTeX CV templates + plain-text → LaTeX conversion.

Two jobs:

1. Offer a small library of CV *styles* (preambles) the user can pick from, all
   compilable with a stock ``pdflatex`` + standard packages.
2. Turn the plain text extracted from a PDF/DOCX upload into a structured LaTeX
   CV (LLM-assisted, with a robust rule-based fallback) so non-LaTeX users get a
   real document to optimize and download.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

try:  # importable both as a bare module (main.py) and as the src package
    from llm_client import complete, Task
except ImportError:  # pragma: no cover
    from .llm_client import complete, Task


# Each template is a self-contained preamble. ``{BODY}`` is replaced with the
# section content; the document wrapper is added by :func:`render_document`.
TEMPLATES: Dict[str, Dict[str, str]] = {
    "ats_simple": {
        "name": "ATS Simple",
        "description": "Clean single-column layout that parses cleanly in ATS systems.",
        "preamble": r"""\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[margin=1in]{geometry}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\setlist[itemize]{leftmargin=*,nosep}
\pagestyle{empty}
""",
    },
    "modern": {
        "name": "Modern",
        "description": "Coloured section headings, sans-serif — modern tech look.",
        "preamble": r"""\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[margin=0.9in]{geometry}
\usepackage{enumitem}
\usepackage{xcolor}
\usepackage{titlesec}
\usepackage[hidelinks]{hyperref}
\renewcommand{\familydefault}{\sfdefault}
\definecolor{accent}{HTML}{6366F1}
\titleformat{\section}{\large\bfseries\color{accent}}{}{0em}{}[\titlerule]
\setlist[itemize]{leftmargin=*,nosep}
\pagestyle{empty}
""",
    },
    "compact": {
        "name": "Compact one-page",
        "description": "Tighter margins and spacing to fit more on a single page.",
        "preamble": r"""\documentclass[10pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[margin=0.6in]{geometry}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage[hidelinks]{hyperref}
\titlespacing*{\section}{0pt}{6pt}{2pt}
\setlist[itemize]{leftmargin=*,nosep,topsep=0pt}
\pagestyle{empty}
""",
    },
    "academic": {
        "name": "Academic",
        "description": "Serif, formal headings — suited to research/academic CVs.",
        "preamble": r"""\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[margin=1in]{geometry}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage[hidelinks]{hyperref}
\titleformat{\section}{\large\scshape}{}{0em}{}[\titlerule]
\setlist[itemize]{leftmargin=*}
\pagestyle{empty}
""",
    },
}

DEFAULT_TEMPLATE = "ats_simple"


def list_templates() -> List[Dict[str, str]]:
    """Template metadata for the picker UI."""
    return [
        {"id": tid, "name": t["name"], "description": t["description"]}
        for tid, t in TEMPLATES.items()
    ]


def render_document(template_id: str, body: str, header_latex: str = "") -> str:
    """Wrap a LaTeX body (sections) in the chosen template's document shell."""
    template = TEMPLATES.get(template_id) or TEMPLATES[DEFAULT_TEMPLATE]
    header = (header_latex + "\n\n") if header_latex else ""
    return (
        template["preamble"]
        + "\n\\begin{document}\n\n"
        + header
        + body.strip()
        + "\n\n\\end{document}\n"
    )


def apply_template(latex: str, template_id: str) -> str:
    """Re-skin an existing CV: keep its sections, swap in a new preamble.

    Falls back to returning the input unchanged if we cannot locate a document
    body to recompose.
    """
    try:
        from section_rewriter import split_latex, assemble
    except ImportError:  # pragma: no cover
        from .section_rewriter import split_latex, assemble

    preamble, sections, _ = split_latex(latex)
    if not sections:
        return latex
    body = assemble("", sections, "").strip()
    # Preserve a \maketitle / name header that lived in the old preamble body
    # by carrying over anything between \begin{document} and the first section.
    header = ""
    begin = preamble.find("\\begin{document}")
    if begin != -1:
        header = preamble[begin + len("\\begin{document}"):].strip()
    return render_document(template_id, body, header_latex=header)


# ---------------------------------------------------------------------------
# Plain text -> LaTeX (for PDF/DOCX uploads)
# ---------------------------------------------------------------------------

_LATEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape_latex(text: str) -> str:
    out = []
    for ch in str(text):
        out.append(_LATEX_SPECIALS.get(ch, ch))
    return "".join(out)


_CONVERT_SYSTEM_PROMPT = (
    "You convert a candidate's raw CV text (extracted from a PDF or Word file) "
    "into clean LaTeX. Output ONLY the document BODY — the part that goes "
    "between \\begin{document} and \\end{document}. Do NOT output \\documentclass, "
    "package imports, \\begin{document}, or \\end{document}.\n\n"
    "Rules:\n"
    "- Preserve every fact exactly: names, employers, dates, schools, metrics. "
    "Invent nothing.\n"
    "- Start with the candidate's name in \\textbf{\\Large ...} and a contact "
    "line if present.\n"
    "- Group content into \\section{...} blocks (Summary, Experience, Education, "
    "Skills, Projects, etc.) based on what the text contains.\n"
    "- Use \\begin{itemize} ... \\item ... \\end{itemize} for bullet lists.\n"
    "- Escape LaTeX special characters (&, %, $, #, _).\n"
    "- No markdown, no code fences, no commentary, no <think> tags."
)


def _fallback_text_to_body(text: str) -> str:
    """Rule-based conversion when the LLM is unavailable.

    Treats short ALL-CAPS or title-case lines as section headers and groups the
    following lines into an itemize list. Always escapes user text.
    """
    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    # First non-empty line is treated as the candidate name.
    name = ""
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx < len(lines):
        name = lines[idx].strip()
        idx += 1

    out: List[str] = []
    if name:
        out.append(f"\\textbf{{\\Large {escape_latex(name)}}}\\\\[4pt]")

    def _is_header(line: str) -> bool:
        s = line.strip()
        if not (2 <= len(s) <= 40):
            return False
        letters = [c for c in s if c.isalpha()]
        if not letters:
            return False
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        return upper_ratio > 0.8 or s.endswith(":")

    open_list = False

    def _close_list():
        nonlocal open_list
        if open_list:
            out.append("\\end{itemize}")
            open_list = False

    for line in lines[idx:]:
        stripped = line.strip()
        if not stripped:
            continue
        if _is_header(stripped):
            _close_list()
            title = escape_latex(stripped.rstrip(":").title())
            out.append(f"\n\\section*{{{title}}}")
        else:
            if not open_list:
                out.append("\\begin{itemize}")
                open_list = True
            out.append(f"  \\item {escape_latex(stripped)}")
    _close_list()
    return "\n".join(out).strip() or f"\\textbf{{{escape_latex(name or 'CV')}}}"


def _clean_body(raw: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    fence = re.search(r"```(?:latex|tex)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    # Strip anything the model leaked outside the body.
    for token in ("\\documentclass", "\\begin{document}"):
        i = text.find(token)
        if token == "\\begin{document}" and i != -1:
            text = text[i + len(token):]
    text = text.replace("\\end{document}", "")
    text = re.sub(r"\\documentclass.*?(?=\\section|\\textbf|$)", "", text, flags=re.DOTALL)
    return text.strip()


def plain_text_to_latex(text: str, template_id: str = DEFAULT_TEMPLATE,
                        language: str = "en") -> str:
    """Convert raw CV text into a complete, compilable LaTeX document."""
    body = ""
    try:
        lang_clause = ""
        if (language or "en").lower() != "en":
            lang_clause = (
                f"\n- Keep the content in its original language; do not translate."
            )
        raw = complete(
            f"Raw CV text to convert into a LaTeX body:\n\n{text[:8000]}",
            system_prompt=_CONVERT_SYSTEM_PROMPT + lang_clause,
            task=Task.SMART_CV,
            temperature=0.2,
            max_tokens=2200,
            log_prefix="cv-convert",
        )
        if raw:
            body = _clean_body(raw)
    except Exception as exc:  # noqa: BLE001
        print(f"[cv-convert] LLM conversion failed, using fallback: {exc}", flush=True)

    if not body or "\\section" not in body and "\\textbf" not in body:
        body = _fallback_text_to_body(text)

    return render_document(template_id, body)
