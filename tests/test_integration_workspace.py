"""End-to-end integration tests for the per-user workspace API.

Exercises the full CRUD lifecycle of saved jobs, CV documents, version history,
restore, and cover-letter listing through the HTTP layer (test client + DB),
the way the SPA actually uses them. Ownership/isolation has its own suite in
``test_isolation.py``; here we focus on the happy paths and per-endpoint
validation that weren't covered before.
"""

from conftest import register


SAMPLE_LATEX = r"""\documentclass{article}\begin{document}
\section{Experience}\item Built APIs in Python.
\end{document}"""


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


def test_job_full_lifecycle(client):
    """Create, list, fetch, status-transition, and delete a saved job."""
    register(client, "jobs@example.com")

    # Empty list to start.
    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert r.get_json()["jobs"] == []

    # Create.
    r = client.post("/api/jobs", json={
        "title": "Backend Engineer",
        "company": "Acme",
        "text": "Python, Flask and SQL required.",
        "url": "https://example.com/job/1",
    })
    assert r.status_code == 201
    job = r.get_json()["job"]
    job_id = job["id"]
    assert job["status"] == "saved"
    assert job["applied_at"] is None
    assert job["raw_text"] == "Python, Flask and SQL required."

    # It shows up in the list now.
    r = client.get("/api/jobs")
    assert [j["id"] for j in r.get_json()["jobs"]] == [job_id]

    # Fetch a single job (includes the raw text + parsed payload).
    r = client.get(f"/api/jobs/{job_id}")
    assert r.status_code == 200
    assert r.get_json()["job"]["title"] == "Backend Engineer"

    # Moving to 'applied' stamps applied_at the first time.
    r = client.patch(f"/api/jobs/{job_id}", json={"status": "applied", "notes": "referred"})
    assert r.status_code == 200
    patched = r.get_json()["job"]
    assert patched["status"] == "applied"
    assert patched["applied_at"] is not None
    assert patched["notes"] == "referred"

    # Delete, then it's gone (404 on fetch).
    assert client.delete(f"/api/jobs/{job_id}").status_code == 200
    assert client.get(f"/api/jobs/{job_id}").status_code == 404


def test_create_job_requires_text(client):
    register(client, "jobs2@example.com")
    assert client.post("/api/jobs", json={"title": "No text"}).status_code == 400


def test_update_job_rejects_invalid_status(client):
    register(client, "jobs3@example.com")
    job_id = client.post("/api/jobs", json={"text": "x"}).get_json()["job"]["id"]
    r = client.patch(f"/api/jobs/{job_id}", json={"status": "bogus"})
    assert r.status_code == 400


def test_unknown_status_on_create_defaults_to_saved(client):
    register(client, "jobs4@example.com")
    r = client.post("/api/jobs", json={"text": "x", "status": "nonsense"})
    assert r.get_json()["job"]["status"] == "saved"


def test_jobs_require_login(client):
    assert client.get("/api/jobs").status_code == 401
    assert client.post("/api/jobs", json={"text": "x"}).status_code == 401


# ---------------------------------------------------------------------------
# CV documents + version history
# ---------------------------------------------------------------------------


def test_cv_document_and_version_lifecycle(client):
    """Create a CV, add versions, fetch, restore an old one, then delete."""
    register(client, "cv@example.com")

    # New document is created with its initial version.
    r = client.post("/api/cv", json={"latex": SAMPLE_LATEX, "name": "Master CV"})
    assert r.status_code == 201
    doc = r.get_json()["document"]
    doc_id = doc["id"]
    assert doc["name"] == "Master CV"
    assert doc["version_count"] == 1
    first_version_id = doc["versions"][0]["id"]

    # Listing shows the one document.
    r = client.get("/api/cv")
    assert [d["id"] for d in r.get_json()["documents"]] == [doc_id]

    # Append a second version.
    r = client.post(f"/api/cv/{doc_id}/versions", json={
        "latex": SAMPLE_LATEX + "\n% v2",
        "label": "Tailored for Acme",
    })
    assert r.status_code == 201
    v2 = r.get_json()["version"]
    assert v2["label"] == "Tailored for Acme"
    assert "latex" in v2  # include_latex=True on creation

    # The document now reports two versions.
    r = client.get(f"/api/cv/{doc_id}")
    assert r.get_json()["document"]["version_count"] == 2

    # Fetch a single version with its latex.
    r = client.get(f"/api/cv/versions/{first_version_id}")
    assert r.status_code == 200
    assert r.get_json()["version"]["latex"] == SAMPLE_LATEX

    # Restore the first version → appends a third version with its content.
    r = client.post(f"/api/cv/versions/{first_version_id}/restore")
    assert r.status_code == 201
    restored = r.get_json()["version"]
    assert restored["latex"] == SAMPLE_LATEX
    assert f"#{first_version_id}" in restored["label"]
    assert client.get(f"/api/cv/{doc_id}").get_json()["document"]["version_count"] == 3

    # Delete just the second version.
    assert client.delete(f"/api/cv/versions/{v2['id']}").status_code == 200
    assert client.get(f"/api/cv/versions/{v2['id']}").status_code == 404

    # Delete the whole document; its remaining versions cascade away.
    assert client.delete(f"/api/cv/{doc_id}").status_code == 200
    assert client.get(f"/api/cv/{doc_id}").status_code == 404
    assert client.get(f"/api/cv/versions/{first_version_id}").status_code == 404


def test_create_cv_requires_latex(client):
    register(client, "cv2@example.com")
    assert client.post("/api/cv", json={"name": "Empty"}).status_code == 400


def test_add_version_requires_latex(client):
    register(client, "cv3@example.com")
    doc_id = client.post("/api/cv", json={"latex": SAMPLE_LATEX}).get_json()["document"]["id"]
    assert client.post(f"/api/cv/{doc_id}/versions", json={"latex": ""}).status_code == 400


def test_cv_endpoints_require_login(client):
    assert client.get("/api/cv").status_code == 401
    assert client.post("/api/cv", json={"latex": SAMPLE_LATEX}).status_code == 401


def test_missing_document_returns_404(client):
    register(client, "cv4@example.com")
    assert client.get("/api/cv/999999").status_code == 404
    assert client.get("/api/cv/versions/999999").status_code == 404


# ---------------------------------------------------------------------------
# Cover-letter listing (rows are created by features.py, listed here)
# ---------------------------------------------------------------------------


def test_cover_letters_listing_and_job_filter(client):
    register(client, "cl@example.com")

    # No letters yet.
    assert client.get("/api/cover-letters").get_json()["cover_letters"] == []

    job_id = client.post("/api/jobs", json={"text": "Need a Pythonista."}).get_json()["job"]["id"]

    # Generate + persist a cover letter tied to the job.
    r = client.post("/api/cover-letter", json={
        "cv_latex": SAMPLE_LATEX,
        "job_description": "Need a Pythonista.",
        "kinds": ["cover_letter"],
        "save": True,
        "job_id": job_id,
    })
    assert r.status_code == 200
    assert r.get_json()["results"]["cover_letter"]

    # Now it lists, and the job_id filter both matches and excludes correctly.
    assert len(client.get("/api/cover-letters").get_json()["cover_letters"]) == 1
    assert len(client.get(f"/api/cover-letters?job_id={job_id}").get_json()["cover_letters"]) == 1
    assert client.get("/api/cover-letters?job_id=999999").get_json()["cover_letters"] == []
