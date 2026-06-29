"""A single end-to-end user journey across the whole app.

This walks one account through the full product flow the SPA drives — sign up,
paste a job, analyze and optimize a CV, save everything to the workspace,
generate outreach, export, pull a GDPR data export, and finally delete the
account — asserting state is threaded correctly between steps and that erasure
really removes the data. It runs on the keyless fallback path (see conftest).
"""

import io
import zipfile

from conftest import login


CV_LATEX = r"""\documentclass{article}\begin{document}
\section{Summary}Backend-leaning engineer, 6 years of Python and Flask.
\section{Experience}\item Built Python/Flask REST APIs serving 100k users.
\item Designed PostgreSQL schemas and CI pipelines.
\section{Skills}Python, Flask, SQL, PostgreSQL, Docker, Git.
\end{document}"""

JOB_TEXT = (
    "Senior Backend Engineer at Acme. Requirements: Python, Flask, SQL, Docker, "
    "REST APIs, CI/CD. 5+ years building production web services."
)


def test_full_user_journey(client, app):
    # 1) Sign up — registration logs the user straight in.
    r = client.post("/register", json={
        "email": "journey@example.com", "password": "password123", "name": "Jordan",
    })
    assert r.status_code == 200
    assert client.get("/api/me").get_json()["authenticated"] is True

    # 2) Parse the pasted job description.
    parsed = client.post("/api/parse-job", json={"text": JOB_TEXT}).get_json()
    assert parsed["success"] is True
    assert "python" in [s.lower() for s in parsed["skills"]]

    # 3) Analyze the current CV against the parsed offer.
    analysis = client.post(
        "/api/analyze-cv", json={"cv_latex": CV_LATEX, "job_description": parsed}
    ).get_json()["analysis"]
    assert "_cv_text" not in analysis

    # 4) Optimize the CV for the offer.
    opt = client.post("/api/optimize-cv", json={
        "cv_latex": CV_LATEX, "job_description": parsed, "language": "en",
    }).get_json()
    optimized_latex = opt["optimized_latex"]
    assert optimized_latex.strip()

    # 5) Save the job to the workspace and mark it applied.
    job_id = client.post("/api/jobs", json={
        "title": "Senior Backend Engineer", "company": "Acme",
        "text": JOB_TEXT, "parsed": parsed,
    }).get_json()["job"]["id"]
    client.patch(f"/api/jobs/{job_id}", json={"status": "applied"})

    # 6) Save the optimized CV as a document, then add a tailored version.
    doc = client.post("/api/cv", json={
        "latex": CV_LATEX, "name": "Master CV",
    }).get_json()["document"]
    doc_id = doc["id"]
    initial_version_id = doc["versions"][0]["id"]
    tailored = client.post(f"/api/cv/{doc_id}/versions", json={
        "latex": optimized_latex, "label": "Tailored for Acme",
        "job_id": job_id, "analysis": analysis,
    }).get_json()["version"]
    assert tailored["job_id"] == job_id

    # 7) Restore the original version (version history works end to end).
    client.post(f"/api/cv/versions/{initial_version_id}/restore")
    assert client.get(f"/api/cv/{doc_id}").get_json()["document"]["version_count"] == 3

    # 8) Generate + persist a cover letter tied to the saved job.
    cl = client.post("/api/cover-letter", json={
        "cv_latex": optimized_latex, "job_description": JOB_TEXT,
        "kinds": ["cover_letter"], "save": True, "job_id": job_id,
    }).get_json()
    assert cl["results"]["cover_letter"].strip()
    assert len(client.get("/api/cover-letters").get_json()["cover_letters"]) == 1

    # 9) Export the tailored CV as a Word document.
    export = client.post("/api/export", json={"latex": optimized_latex, "format": "docx"})
    assert export.status_code == 200
    assert zipfile.is_zipfile(io.BytesIO(export.data))

    # 10) GDPR export reflects everything we created above.
    dump = client.get("/api/account/export").get_json()
    assert dump["account"]["email"] == "journey@example.com"
    assert len(dump["jobs"]) == 1
    assert len(dump["cv_documents"]) == 1
    assert len(dump["cover_letters"]) == 1

    # 11) Delete the account; data is erased and the session ends.
    r = client.post("/api/account/delete", json={"password": "password123"})
    assert r.status_code == 200
    assert client.get("/api/me").get_json()["authenticated"] is False

    # 12) The account is truly gone — the old credentials no longer log in.
    assert login(client, "journey@example.com", "password123").status_code == 401

    # And no orphaned rows remain in the database.
    with app.app_context():
        from autocv.models import User, Job, CVDocument, CVVersion, CoverLetter
        assert User.query.filter_by(email="journey@example.com").first() is None
        assert Job.query.count() == 0
        assert CVDocument.query.count() == 0
        assert CVVersion.query.count() == 0
        assert CoverLetter.query.count() == 0
