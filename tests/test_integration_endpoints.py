"""Integration tests for the feature, diagnostics, and LLM-backed API endpoints.

These hit the real HTTP routes end-to-end. The test environment runs keyless
(no network, no LLM — see conftest), so every endpoint here is verified on its
rule-based / fallback path, which is exactly what must keep working when the
provider is unavailable.
"""

import io

from conftest import register


SAMPLE_LATEX = r"""\documentclass{article}\begin{document}
\section{Experience}\item Built Python/Flask REST APIs serving 100k users.
\section{Skills}Python, Flask, SQL, Docker.
\end{document}"""

SAMPLE_JOB_TEXT = (
    "Senior Python Engineer. Requirements: Python, Flask, SQL, Docker, REST APIs. "
    "5+ years building web services."
)


# ---------------------------------------------------------------------------
# Diagnostics + samples (public, no login)
# ---------------------------------------------------------------------------


def test_csrf_token_endpoint(client):
    r = client.get("/api/csrf-token")
    assert r.status_code == 200
    assert isinstance(r.get_json()["csrf_token"], str)


def test_llm_health_reports_config_without_key(client):
    r = client.get("/api/llm/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    assert data["source"]  # active provider is reported
    # The raw secret must never be exposed: the keyless test env reports it masked.
    assert "api_key=none" in str(data["config"]).lower()


def test_sample_cv_and_sample_job(client):
    cv = client.get("/api/sample-cv")
    assert cv.status_code == 200
    sample = cv.get_json()["cv"]
    assert isinstance(sample, dict) and sample.get("sections")

    job = client.get("/api/sample-job")
    assert job.status_code == 200
    payload = job.get_json()["job"]
    assert "python" in payload["skills"]
    assert payload["requirements"]


# ---------------------------------------------------------------------------
# Templates + re-skinning (public list, login-gated apply)
# ---------------------------------------------------------------------------


def test_templates_list_is_public(client):
    r = client.get("/api/templates")
    assert r.status_code == 200
    templates = r.get_json()["templates"]
    assert isinstance(templates, list) and templates
    assert all("id" in t for t in templates)


def test_apply_template_reskins_latex(client):
    register(client, "tmpl@example.com")
    r = client.post("/api/apply-template", json={"latex": SAMPLE_LATEX, "template": "ats_simple"})
    assert r.status_code == 200
    assert "\\section{Experience}" in r.get_json()["latex"]


def test_apply_template_requires_latex(client):
    register(client, "tmpl2@example.com")
    assert client.post("/api/apply-template", json={"latex": ""}).status_code == 400


def test_apply_template_requires_login(client):
    assert client.post("/api/apply-template", json={"latex": SAMPLE_LATEX}).status_code == 401


# ---------------------------------------------------------------------------
# File ingestion (multipart upload)
# ---------------------------------------------------------------------------


def test_extract_cv_from_txt_upload(client):
    register(client, "extract@example.com")
    data = {
        "file": (io.BytesIO(b"Jane Doe\nPython engineer with 6 years experience."), "cv.txt"),
        "template": "ats_simple",
        "language": "en",
    }
    r = client.post("/api/extract-cv", data=data, content_type="multipart/form-data")
    assert r.status_code == 200
    body = r.get_json()
    assert body["source_format"] == "text"
    assert "Jane Doe" in body["text"]
    assert body["latex"].strip()  # converted to a LaTeX document


def test_extract_cv_rejects_unsupported_type(client):
    register(client, "extract2@example.com")
    data = {"file": (io.BytesIO(b"binary"), "malware.exe")}
    r = client.post("/api/extract-cv", data=data, content_type="multipart/form-data")
    assert r.status_code == 400


def test_extract_cv_requires_a_file(client):
    register(client, "extract3@example.com")
    r = client.post("/api/extract-cv", data={}, content_type="multipart/form-data")
    assert r.status_code == 400


def test_extract_cv_requires_login(client):
    data = {"file": (io.BytesIO(b"hi"), "cv.txt")}
    r = client.post("/api/extract-cv", data=data, content_type="multipart/form-data")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Job parsing / CV analysis / optimization (LLM endpoints, fallback path)
# ---------------------------------------------------------------------------


def test_parse_job_success_path(client):
    register(client, "parse@example.com")
    r = client.post("/api/parse-job", json={"text": SAMPLE_JOB_TEXT})
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    assert "python" in [s.lower() for s in data["skills"]]


def test_parse_job_requires_text(client):
    register(client, "parse2@example.com")
    assert client.post("/api/parse-job", json={}).status_code == 400


def test_analyze_cv_returns_match_breakdown(client):
    register(client, "analyze@example.com")
    parsed = client.post("/api/parse-job", json={"text": SAMPLE_JOB_TEXT}).get_json()
    r = client.post("/api/analyze-cv", json={"cv_latex": SAMPLE_LATEX, "job_description": parsed})
    assert r.status_code == 200
    analysis = r.get_json()["analysis"]
    # Internal CV text must be stripped from the public-facing analysis.
    assert "_cv_text" not in analysis


def test_analyze_cv_validates_inputs(client):
    register(client, "analyze2@example.com")
    assert client.post("/api/analyze-cv", json={"job_description": {"x": 1}}).status_code == 400
    assert client.post("/api/analyze-cv", json={"cv_latex": SAMPLE_LATEX}).status_code == 400


def test_optimize_cv_returns_latex_and_analysis(client):
    register(client, "optimize@example.com")
    parsed = client.post("/api/parse-job", json={"text": SAMPLE_JOB_TEXT}).get_json()
    r = client.post("/api/optimize-cv", json={
        "cv_latex": SAMPLE_LATEX,
        "job_description": parsed,
        "language": "en",
    })
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    assert data["optimized_latex"].strip()
    assert "analysis" in data


def test_optimize_cv_requires_inputs(client):
    register(client, "optimize2@example.com")
    assert client.post("/api/optimize-cv", json={"cv_latex": SAMPLE_LATEX}).status_code == 400


def test_llm_endpoints_require_login(client):
    assert client.post("/api/analyze-cv", json={"cv_latex": "x", "job_description": {}}).status_code == 401
    assert client.post("/api/optimize-cv", json={"cv_latex": "x", "job_description": {}}).status_code == 401


# ---------------------------------------------------------------------------
# Cover letters + interview review (generation, fallback path)
# ---------------------------------------------------------------------------


def test_cover_letter_generation_without_saving(client):
    register(client, "cover@example.com")
    r = client.post("/api/cover-letter", json={
        "cv_latex": SAMPLE_LATEX,
        "job_description": SAMPLE_JOB_TEXT,
        "kinds": ["cover_letter", "recruiter_message"],
    })
    assert r.status_code == 200
    results = r.get_json()["results"]
    assert results["cover_letter"].strip()
    assert results["recruiter_message"].strip()
    # Nothing was persisted (save not requested).
    assert client.get("/api/cover-letters").get_json()["cover_letters"] == []


def test_cover_letter_requires_inputs(client):
    register(client, "cover2@example.com")
    assert client.post("/api/cover-letter", json={}).status_code == 400


def test_interview_review_returns_feedback(client):
    register(client, "review@example.com")
    r = client.post("/api/interview/review", json={
        "question": {"prompt": "Explain a REST API you built.", "type": "behavioral"},
        "answer": "I built a Flask API serving 100k users with pagination and caching.",
    })
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert body["review"]


def test_interview_review_requires_a_question(client):
    register(client, "review2@example.com")
    assert client.post("/api/interview/review", json={"answer": "x"}).status_code == 400


# ---------------------------------------------------------------------------
# Auth boundary + SPA routing
# ---------------------------------------------------------------------------


def test_me_endpoint_reflects_auth_state(client):
    # Anonymous first.
    r = client.get("/api/me")
    assert r.get_json() == {"authenticated": False, "user": None}
    # Then signed in.
    register(client, "me@example.com")
    r = client.get("/api/me")
    body = r.get_json()
    assert body["authenticated"] is True
    assert body["user"]["email"] == "me@example.com"


def test_logout_clears_session(client):
    register(client, "logout@example.com")
    assert client.get("/api/me").get_json()["authenticated"] is True
    r = client.post("/logout", json={})
    assert r.status_code == 200
    assert client.get("/api/me").get_json()["authenticated"] is False


def test_resend_verification_when_already_verified_is_noop(client):
    register(client, "resend@example.com")
    r = client.post("/resend-verification", json={})
    assert r.status_code == 200
    assert r.get_json()["success"] is True


def test_unknown_api_path_returns_json_404(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    assert "error" in r.get_json()


def test_spa_catch_all_serves_app_for_deep_links(client):
    # An arbitrary client-side route should serve the SPA shell, not 404.
    assert client.get("/some/deep/link").status_code == 200
