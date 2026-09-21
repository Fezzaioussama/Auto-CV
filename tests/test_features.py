"""Export, demo, public pages, and the auth boundary on paid endpoints."""

import io
import zipfile

from conftest import register


SAMPLE_LATEX = r"""\documentclass{article}\begin{document}
\section{Experience}\begin{itemize}\item Built APIs in Python.\end{itemize}
\end{document}"""


def test_export_docx_and_txt(client):
    register(client, "exp@example.com")
    r = client.post("/api/export", json={"latex": SAMPLE_LATEX, "format": "docx"})
    assert r.status_code == 200
    assert "wordprocessingml" in r.mimetype
    assert zipfile.is_zipfile(io.BytesIO(r.data))

    r = client.post("/api/export", json={"latex": SAMPLE_LATEX, "format": "txt"})
    assert r.status_code == 200
    assert b"EXPERIENCE" in r.data


def test_export_bad_format_and_empty(client):
    register(client, "exp2@example.com")
    # 'rtf' is unsupported (docx/pdf/txt are the supported formats).
    assert client.post("/api/export", json={"latex": SAMPLE_LATEX, "format": "rtf"}).status_code == 422
    assert client.post("/api/export", json={"latex": "", "format": "docx"}).status_code == 400


def test_export_requires_login(client):
    assert client.post("/api/export", json={"latex": SAMPLE_LATEX, "format": "docx"}).status_code == 401


def test_parse_job_requires_login(client):
    # Was previously open; must now require auth so anon can't burn LLM budget.
    assert client.post("/api/parse-job", json={"text": "Some job"}).status_code == 401


def test_public_pages_are_reachable_anonymously(client):
    for path in ["/how-it-works", "/demo", "/privacy", "/terms", "/login", "/register"]:
        assert client.get(path).status_code == 200


def test_root_serves_the_spa_shell(client):
    # Every HTML route now returns the React SPA shell (200); auth is enforced
    # client-side by RequireAuth and server-side by the /api/* endpoints.
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 200


def test_optimizer_page_serves_spa_but_its_api_requires_login(client):
    # The page route hands back the SPA shell to anyone...
    assert client.get("/optimizer", follow_redirects=False).status_code == 200
    # ...but the data endpoint it drives rejects anonymous callers with 401,
    # so no one can run an optimization without an account.
    assert client.post("/api/optimize-cv", json={"cv_latex": SAMPLE_LATEX}).status_code == 401


def test_demo_runs_without_login(client):
    job = "Senior Python Engineer. Requirements: Python, Flask, SQL, Docker."
    r = client.post("/api/demo", json={"job_text": job})
    assert r.status_code == 200
    data = r.get_json()
    assert data["used_sample_cv"] is True
    assert "_cv_text" not in data["analysis"]  # internal field not leaked


def test_demo_requires_job_text(client):
    assert client.post("/api/demo", json={}).status_code == 400
