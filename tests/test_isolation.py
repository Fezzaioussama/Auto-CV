"""Multi-tenant isolation: one user must never reach another's data.

This is the highest-stakes property of the app — these tests guard against a
regression that would let a logged-in user read or mutate someone else's jobs,
CVs or CV versions by guessing IDs.
"""

from conftest import register


def _two_users(app):
    a = app.test_client()
    b = app.test_client()
    register(a, "owner@example.com")
    register(b, "intruder@example.com")
    return a, b


def test_other_user_cannot_read_or_mutate_job(app):
    a, b = _two_users(app)
    job_id = a.post("/api/jobs", json={"text": "Secret offer", "title": "Owner job"}).get_json()["job"]["id"]

    assert b.get(f"/api/jobs/{job_id}").status_code == 404
    assert b.patch(f"/api/jobs/{job_id}", json={"status": "applied"}).status_code == 404
    assert b.delete(f"/api/jobs/{job_id}").status_code == 404

    # Owner still has it, untouched.
    owner_view = a.get(f"/api/jobs/{job_id}").get_json()["job"]
    assert owner_view["status"] == "saved"

    # B's own job list is empty.
    assert b.get("/api/jobs").get_json()["jobs"] == []


def test_other_user_cannot_read_cv_or_versions(app):
    a, b = _two_users(app)
    doc = a.post("/api/cv", json={"latex": r"\documentclass{article}\begin{document}Hi\end{document}"}).get_json()["document"]
    doc_id = doc["id"]
    version_id = doc["versions"][0]["id"]

    assert b.get(f"/api/cv/{doc_id}").status_code == 404
    assert b.delete(f"/api/cv/{doc_id}").status_code == 404
    assert b.get(f"/api/cv/versions/{version_id}").status_code == 404
    assert b.delete(f"/api/cv/versions/{version_id}").status_code == 404
    assert b.post(f"/api/cv/versions/{version_id}/restore").status_code == 404


def test_export_excludes_other_users_data(app):
    a, b = _two_users(app)
    a.post("/api/jobs", json={"text": "Owner only job", "title": "Owner job"})
    export_b = b.get("/api/account/export").get_json()
    assert export_b["account"]["email"] == "intruder@example.com"
    assert export_b["jobs"] == []
