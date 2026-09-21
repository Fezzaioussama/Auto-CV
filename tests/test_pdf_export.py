"""Pure-Python PDF export + the /api/render-latex fallback.

On Vercel there's no LaTeX toolchain, so the app renders the CV to PDF in pure
Python (fpdf2). These tests check the bytes are a real PDF, Unicode survives,
and the render endpoint falls back to this path when pdflatex is unavailable.
"""

import io

from pypdf import PdfReader
from conftest import register

from autocv import cv_export


_LATEX = r"""\documentclass{article}\begin{document}
\textbf{\Large Marie Curie}
Paris, France · marie@example.com
\section{Expérience}
\subsection{Chercheuse — Université de Paris}
\begin{itemize}
\item Recherche en radioactivité — deux prix Nobel obtenus.
\item Encadrement d'étudiants (réduction de 30\% du temps de thèse).
\end{itemize}
\end{document}"""


def test_export_pdf_is_valid_and_keeps_unicode():
    data, mime, ext = cv_export.export_cv(_LATEX, "pdf")
    assert mime == "application/pdf"
    assert ext == "pdf"
    assert data[:5] == b"%PDF-"

    text = PdfReader(io.BytesIO(data)).pages[0].extract_text() or ""
    # Accented headings/content must survive (bundled DejaVu Unicode font).
    assert "Expérience" in text or "radioactivité" in text
    assert "Marie Curie" in text


def test_unsupported_format_rejected():
    try:
        cv_export.export_cv(_LATEX, "rtf")
    except cv_export.ExportError:
        return
    raise AssertionError("expected ExportError for an unsupported format")


def test_render_latex_falls_back_to_python_pdf(client, monkeypatch):
    """When no LaTeX toolchain exists (Vercel), the endpoint still returns a PDF."""
    def no_toolchain(*_args, **_kwargs):
        raise FileNotFoundError("pdflatex")

    monkeypatch.setattr("autocv.latex_repair.render_pdf", no_toolchain)

    register(client, "pdf@example.com")  # frictionless register also logs in
    resp = client.post("/api/render-latex", json={"latex": _LATEX})

    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.headers.get("X-PDF-Engine") == "python"
    assert resp.data[:5] == b"%PDF-"
