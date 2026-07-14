"""Tests for the section-by-section template-fill generator.

The deterministic pieces (parsing, validation, contact extraction, slot
matching) run without any LLM. The fill/correct loop and the orchestrator are
driven by a fake ``complete`` so the validate -> resend -> retry behaviour is
exercised without a network call.
"""

from autocv import template_fill as tf

# A trimmed but representative copy of the house template.
TEMPLATE = r"""\documentclass[letterpaper,10pt]{article}
\usepackage{fontawesome5}
\begin{document}
\begin{center}
  \begin{minipage}[c]{0.80\textwidth}
    \documentTitle{Prénom Nom}{
      \href{tel:+33000000000}{\raisebox{-0.05\height}\faPhone\ +33 0 00 00 00 00} ~|~
      \href{mailto:email@example.com}{\raisebox{-0.15\height}\faEnvelope\ email@example.com}
    }
  \end{minipage}
\end{center}

\tinysection{Résumé}
% Bref paragraphe de présentation (2-3 lignes).

\section{Compétences}
\begin{tabular}{@{}l l@{}}
  \textbf{Catégorie 1 :} &  \\
\end{tabular}

\section{Expérience}
\headingBf{Nom de l'entreprise}{Mois Année -- Mois Année}
\begin{resume_list}
  \item Description de la mission.
\end{resume_list}

\section{Langues}
\begin{resume_list}
  \item \textbf{Langue 1 :} Niveau
\end{resume_list}

\end{document}
"""


CV = r"""\documentclass{article}
\begin{document}
\Huge{\textbf{Ada Lovelace}}
Contact: ada@analytical.io | linkedin.com/in/adalovelace | github.com/ada
Phone tel:+44 20 7946 0000

\section{Summary}
Backend engineer with 6 years building Python services.

\section{Skills}
Python, Django, PostgreSQL, Docker, Git

\section{Experience}
\textbf{Acme Corp} 2019--2024
\begin{itemize}
  \item Built billing APIs in Python and Django.
\end{itemize}
\end{document}
"""


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def test_parse_template_finds_section_and_tinysection_slots():
    parsed = tf.parse_template(TEMPLATE)
    titles = [s.title for s in parsed.slots]
    assert titles == ["Résumé", "Compétences", "Expérience", "Langues"]
    kinds = {s.title: s.kind for s in parsed.slots}
    assert kinds["Résumé"] == "summary"
    assert kinds["Compétences"] == "skills"
    assert kinds["Expérience"] == "experience"
    assert kinds["Langues"] == "languages"
    # The header (documentTitle) stays in the preamble, postamble has end-doc.
    assert "\\documentTitle" in parsed.preamble
    assert "\\end{document}" in parsed.postamble
    # The summary slot keeps the tinysection command for re-emission.
    summary = parsed.slots[0]
    assert summary.command == "tinysection"


def test_localized_header_translates_known_kinds_only():
    parsed = tf.parse_template(TEMPLATE)
    skills = next(s for s in parsed.slots if s.kind == "skills")
    assert tf.localized_header(skills, "en") == "\\section{Skills}"
    assert tf.localized_header(skills, "fr") == "\\section{Compétences}"
    summary = parsed.slots[0]
    assert tf.localized_header(summary, "en") == "\\tinysection{Summary}"


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def test_structural_problems_flags_imbalance_and_forbidden():
    assert tf.structural_problems("") == ["the section body is empty"]
    assert any("braces" in p for p in tf.structural_problems("\\textbf{x"))
    assert any("environment" in p for p in tf.structural_problems(
        "\\begin{itemize}\\item a"))
    assert any("forbidden" in p for p in tf.structural_problems(
        "\\section{Nope} body"))
    # A clean body has no problems.
    assert tf.structural_problems(
        "\\begin{itemize}\\item ok\\end{itemize}") == []


def test_faithfulness_flags_invented_skill_and_leftover_placeholder():
    source = "Python and Django services."
    # Kubernetes is in the offer gap and absent from the source -> invented.
    probs = tf.faithfulness_problems(
        "Expert in Kubernetes orchestration.", source, ["Kubernetes"])
    assert any("never listed" in p for p in probs)
    # Genuinely-present skill is fine.
    assert tf.faithfulness_problems(
        "Strong Python developer.", source, ["Kubernetes"]) == []
    # Leftover template placeholder is rejected.
    assert any("placeholder" in p for p in tf.faithfulness_problems(
        "\\headingBf{Nom de l'entreprise}{Mois Année}", source, []))


# --------------------------------------------------------------------------
# Contact extraction + header fill
# --------------------------------------------------------------------------


def test_extract_personal_info_pulls_real_contacts():
    info = tf.extract_personal_info(CV)
    assert info.name == "Ada Lovelace"
    assert info.email == "ada@analytical.io"
    assert "adalovelace" in info.linkedin
    assert info.github.endswith("/ada")
    assert "7946" in info.phone


def test_fill_header_writes_found_fields_and_drops_missing():
    parsed = tf.parse_template(TEMPLATE)
    info = tf.PersonalInfo(name="Ada Lovelace", email="ada@analytical.io")
    out = tf.fill_header(parsed.preamble, info)
    assert "Ada Lovelace" in out
    assert "ada@analytical.io" in out
    # The template's placeholder email is gone, and no phone segment invented.
    assert "email@example.com" not in out
    assert "faPhone" not in out


# --------------------------------------------------------------------------
# Source-to-slot matching
# --------------------------------------------------------------------------


def test_source_for_slot_matches_by_kind_then_title_then_fallback():
    by_kind, sections = tf.build_source_index(CV)
    parsed = tf.parse_template(TEMPLATE)
    skills_slot = next(s for s in parsed.slots if s.kind == "skills")
    assert "Django" in tf.source_for_slot(skills_slot, by_kind, sections, CV)
    # Languages has no source section -> fallback to whole CV text.
    lang_slot = next(s for s in parsed.slots if s.kind == "languages")
    assert tf.source_for_slot(lang_slot, by_kind, sections, CV) == CV.strip()


# --------------------------------------------------------------------------
# Fill + correct loop (fake LLM)
# --------------------------------------------------------------------------


def _slot(kind="skills", title="Compétences", command="section",
          skeleton="\\textbf{x}"):
    return tf.TemplateSlot(command=command, title=title, skeleton=skeleton, kind=kind)


def test_fill_slot_retries_until_valid(monkeypatch):
    analysis = {"skills_match": {"missing": ["Kubernetes"]}}
    calls = {"n": 0}

    def fake_complete(user_prompt, **_kw):
        calls["n"] += 1
        if calls["n"] == 1:
            # First attempt invents a missing skill -> must be rejected.
            return "Expert in Kubernetes and Python."
        # Correction prompt should describe the problem.
        assert "never listed" in user_prompt or "rejected" in user_prompt
        return "Strong Python and Django developer."

    monkeypatch.setattr(tf, "complete", fake_complete)
    res = tf.fill_slot(
        _slot(),
        source_content="Python, Django",
        full_source_text="Python, Django",
        job_description={},
        job_text="",
        analysis=analysis,
        language="en",
        max_attempts=3,
    )
    assert res.body is not None
    assert "Kubernetes" not in res.body
    assert res.attempts == 2
    assert not res.omitted


def test_fill_slot_omits_optional_empty_section_without_calling_llm(monkeypatch):
    def boom(*_a, **_k):  # would fail the test if called
        raise AssertionError("LLM should not be called for empty optional slot")

    monkeypatch.setattr(tf, "complete", boom)
    res = tf.fill_slot(
        _slot(kind="languages", title="Langues"),
        source_content="   ",
        full_source_text="",
        job_description={},
        job_text="",
        analysis={},
        language="en",
    )
    assert res.omitted and res.body is None and res.attempts == 0


def test_fill_slot_honors_omit_token(monkeypatch):
    monkeypatch.setattr(tf, "complete", lambda *_a, **_k: tf.OMIT_TOKEN)
    res = tf.fill_slot(
        _slot(kind="summary", title="Résumé", command="tinysection"),
        source_content="something",
        full_source_text="something",
        job_description={},
        job_text="",
        analysis={},
        language="en",
    )
    assert res.omitted and res.body is None


# --------------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------------


def test_fill_template_cv_assembles_and_omits(monkeypatch):
    analysis = {"skills_match": {"matched": ["Python"], "missing": []}}

    def fake_complete(user_prompt, **_kw):
        # The Langues section has no grounded content -> the model omits it.
        if "Langues" in user_prompt or "languages" in user_prompt:
            return tf.OMIT_TOKEN
        return "\\textbf{Real content} grounded in the CV."

    monkeypatch.setattr(tf, "complete", fake_complete)
    report = tf.fill_template_cv(
        CV, {"job_title": "Backend Engineer"}, "Backend role", analysis,
        language="en", template=TEMPLATE,
    )
    assert report.used_template
    # Summary, Skills, Experience filled; Languages omitted. Titles are
    # localized to English (the template's headings are French).
    assert "Languages" not in report.filled_titles
    assert "Languages" in report.omitted_titles
    assert "Skills" in report.filled_titles
    assert report.latex.startswith("\\documentclass")
    assert "\\end{document}" in report.latex
    assert "Ada Lovelace" in report.latex            # header filled
    assert "email@example.com" not in report.latex   # placeholder replaced
    # Diffs carry source -> tailored for the UI.
    assert all({"title", "before", "after"} <= d.keys() for d in report.section_diffs)


def test_fill_template_cv_falls_back_when_no_template():
    report = tf.fill_template_cv(
        CV, {}, "", {"skills_match": {}}, language="en", template="")
    assert report.used_template is False
    assert report.latex == CV
