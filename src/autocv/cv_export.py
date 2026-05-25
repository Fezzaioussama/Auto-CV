"""Export a CV to recruiter-friendly formats: Word (.docx) and plain text.

The optimizer's working format is LaTeX, but most recruiters and job portals want
a Word document or plain text they can paste into an ATS form. This module turns
the (tailored) LaTeX into a clean, readable .docx / .txt — it is intentionally a
pragmatic converter, not a full TeX engine: it keeps the structure (headings,
bullets, paragraphs) and the text, and drops formatting commands.
"""

from __future__ import annotations

import io
import os
import re
from typing import List, Dict, Tuple

_FONT_DIR = os.path.join(os.path.dirname(__file__), "assets", "fonts")


class ExportError(Exception):
    """Raised when a CV cannot be exported in the requested format."""


# ---------------------------------------------------------------------------
# LaTeX → structured blocks
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(r"\\(?:section)\*?\{(.*?)\}")
_SUBSECTION_RE = re.compile(r"\\(?:subsection|subsubsection)\*?\{(.*?)\}")
_ITEM_RE = re.compile(r"^\s*\\item\b\s*(.*)$")
_HREF_RE = re.compile(r"\\href\{([^}]*)\}\{([^}]*)\}")
# Formatting wrappers whose argument we keep verbatim.
_WRAP_RE = re.compile(
    r"\\(?:textbf|textit|emph|underline|texttt|textsc|textnormal|mbox|text|"
    r"large|Large|LARGE|small|footnotesize|textsf|textrm)\{([^{}]*)\}"
)
# Any remaining "\cmd[opt]{arg}" — keep the argument, drop the command.
_CMD_ARG_RE = re.compile(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}")
# Bare "\cmd" or "\cmd[opt]" with no argument — drop entirely.
_CMD_RE = re.compile(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?")
_ENV_RE = re.compile(r"\\(?:begin|end)\{[^}]*\}")
_COMMENT_RE = re.compile(r"(?<!\\)%.*$")


def _clean_inline(text: str) -> str:
    """Reduce a LaTeX fragment to readable plain text."""
    if not text:
        return ""

    def _href(m):
        url = m.group(1).replace("mailto:", "")
        label = m.group(2)
        if not label or label == url:
            return url
        return f"{label} ({url})"

    text = _HREF_RE.sub(_href, text)
    # Resolve nested formatting wrappers a few times.
    for _ in range(4):
        new = _WRAP_RE.sub(r"\1", text)
        if new == text:
            break
        text = new
    text = _ENV_RE.sub("", text)
    for _ in range(3):
        new = _CMD_ARG_RE.sub(r"\1", text)
        if new == text:
            break
        text = new
    text = _CMD_RE.sub("", text)
    text = text.replace("{", "").replace("}", "")
    # Unescape LaTeX specials and tidy spacing characters.
    text = re.sub(r"\\([&%$#_{}])", r"\1", text)
    text = text.replace("~", " ").replace("\\,", " ").replace("\\&", "&")
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text


def _strip_to_body(latex: str) -> str:
    """Return the document body (between begin/end document) when present."""
    begin = latex.find(r"\begin{document}")
    if begin != -1:
        latex = latex[begin + len(r"\begin{document}"):]
    end = latex.find(r"\end{document}")
    if end != -1:
        latex = latex[:end]
    return latex


def latex_to_blocks(latex: str) -> List[Dict[str, str]]:
    """Parse CV LaTeX into ordered blocks: heading / subheading / bullet / text."""
    body = _strip_to_body(latex or "")
    body = _COMMENT_RE.sub("", body)
    body = body.replace(r"\\", "\n")  # LaTeX line breaks → real line breaks

    blocks: List[Dict[str, str]] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue

        m = _SECTION_RE.search(line)
        if m and line.lstrip().startswith("\\section"):
            heading = _clean_inline(m.group(1))
            if heading:
                blocks.append({"kind": "heading", "text": heading})
            continue

        m = _SUBSECTION_RE.search(line)
        if m and line.lstrip().startswith("\\sub"):
            sub = _clean_inline(m.group(1))
            if sub:
                blocks.append({"kind": "subheading", "text": sub})
            continue

        m = _ITEM_RE.match(line)
        if m:
            text = _clean_inline(m.group(1))
            if text:
                blocks.append({"kind": "bullet", "text": text})
            continue

        if line.lstrip().startswith("\\begin") or line.lstrip().startswith("\\end"):
            continue

        text = _clean_inline(line)
        if text:
            blocks.append({"kind": "text", "text": text})
    return blocks


# ---------------------------------------------------------------------------
# Blocks → output formats
# ---------------------------------------------------------------------------


def blocks_to_text(blocks: List[Dict[str, str]]) -> str:
    out: List[str] = []
    for b in blocks:
        kind, text = b["kind"], b["text"]
        if kind == "heading":
            out.append("")
            out.append(text.upper())
            out.append("-" * len(text))
        elif kind == "subheading":
            out.append("")
            out.append(text)
        elif kind == "bullet":
            out.append(f"  • {text}")
        else:
            out.append(text)
    return "\n".join(out).strip() + "\n"


def blocks_to_docx(blocks: List[Dict[str, str]]) -> bytes:
    try:
        import docx  # python-docx
    except ImportError as exc:  # pragma: no cover - dependency declared
        raise ExportError("Word export is not available (pip install python-docx).") from exc

    document = docx.Document()
    for b in blocks:
        kind, text = b["kind"], b["text"]
        if kind == "heading":
            document.add_heading(text, level=1)
        elif kind == "subheading":
            document.add_heading(text, level=2)
        elif kind == "bullet":
            document.add_paragraph(text, style="List Bullet")
        else:
            document.add_paragraph(text)

    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


def blocks_to_pdf(blocks: List[Dict[str, str]]) -> bytes:
    """Render parsed CV blocks to a clean, readable PDF (pure Python).

    Uses fpdf2 with a bundled DejaVu Unicode font so accented text (e.g. French
    CVs) and common typography render correctly. This is the rendering path on
    hosts without a LaTeX toolchain (Vercel): it doesn't reproduce the LaTeX
    template, but it produces a tidy A4 document with the same content and
    structure (title, section headings, sub-headings, bullets, paragraphs).
    """
    try:
        from fpdf import FPDF
    except ImportError as exc:  # pragma: no cover - dependency declared
        raise ExportError("PDF export is not available (pip install fpdf2).") from exc

    regular = os.path.join(_FONT_DIR, "DejaVuSans.ttf")
    bold = os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf")

    pdf = FPDF(format="A4", unit="mm")
    pdf.set_margins(18, 16, 18)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("DejaVu", "", regular)
    pdf.add_font("DejaVu", "B", bold)
    pdf.add_page()
    width = pdf.epw  # effective (printable) page width

    seen_heading = False
    seen_title = False
    for block in blocks:
        kind, text = block["kind"], block["text"]
        if not text:
            continue

        if kind == "heading":
            seen_heading = True
            pdf.ln(2.5)
            pdf.set_font("DejaVu", "B", 12.5)
            pdf.set_text_color(20, 20, 20)
            pdf.multi_cell(width, 6.5, text.upper())
            rule_y = pdf.get_y() + 0.5
            pdf.set_draw_color(170, 170, 170)
            pdf.line(pdf.l_margin, rule_y, pdf.l_margin + width, rule_y)
            pdf.ln(2)
        elif kind == "subheading":
            pdf.ln(1)
            pdf.set_font("DejaVu", "B", 10.5)
            pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(width, 5.5, text)
        elif kind == "bullet":
            pdf.set_font("DejaVu", "", 10)
            pdf.set_text_color(0, 0, 0)
            saved_margin = pdf.l_margin
            pdf.set_left_margin(saved_margin + 5)
            pdf.set_x(saved_margin + 5)
            pdf.multi_cell(width - 5, 5, f"•  {text}")
            pdf.set_left_margin(saved_margin)
        else:  # plain text
            # Before the first section heading, treat the first line as the
            # name/title and any following lines as a centred contact line.
            if not seen_heading and not seen_title:
                seen_title = True
                pdf.set_font("DejaVu", "B", 18)
                pdf.set_text_color(15, 15, 15)
                pdf.multi_cell(width, 9, text, align="C")
                pdf.ln(0.5)
            elif not seen_heading:
                pdf.set_font("DejaVu", "", 9.5)
                pdf.set_text_color(90, 90, 90)
                pdf.multi_cell(width, 5, text, align="C")
            else:
                pdf.set_font("DejaVu", "", 10)
                pdf.set_text_color(0, 0, 0)
                pdf.multi_cell(width, 5, text)

    return bytes(pdf.output())


_FORMATS = {
    "docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "docx",
    ),
    "txt": ("text/plain; charset=utf-8", "txt"),
    "pdf": ("application/pdf", "pdf"),
}


def export_cv(latex: str, fmt: str) -> Tuple[bytes, str, str]:
    """Return ``(bytes, mimetype, extension)`` for the requested format.

    ``fmt`` is ``docx``, ``pdf`` or ``txt``. Raises :class:`ExportError` on bad
    input.
    """
    fmt = (fmt or "").lower().strip()
    if fmt not in _FORMATS:
        raise ExportError(
            f"Unsupported export format: {fmt!r}. Use 'docx', 'pdf' or 'txt'."
        )
    if not (latex or "").strip():
        raise ExportError("No CV content to export.")

    blocks = latex_to_blocks(latex)
    if not blocks:
        # Nothing parsed (e.g. already plain text) — fall back to raw text.
        blocks = [{"kind": "text", "text": line.strip()}
                  for line in (latex or "").splitlines() if line.strip()]

    mimetype, ext = _FORMATS[fmt]
    if fmt == "docx":
        data = blocks_to_docx(blocks)
    elif fmt == "pdf":
        data = blocks_to_pdf(blocks)
    else:
        data = blocks_to_text(blocks).encode("utf-8")
    return data, mimetype, ext
