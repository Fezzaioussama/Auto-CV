"""Account management + GDPR endpoints."""

from conftest import register, login


def test_change_password_requires_current(client):
    register(client, "p1@example.com", "originalpass")
    assert client.post("/api/account/password",
                       json={"current_password": "WRONG", "new_password": "newpassword1"}).status_code == 403
    assert client.post("/api/account/password",
                       json={"current_password": "originalpass", "new_password": "newpassword1"}).status_code == 200
    client.post("/logout")
    r = login(client, "p1@example.com", "newpassword1")  # JSON login → 200
    assert r.status_code == 200 and r.get_json()["success"] is True


def test_change_email_requires_password_and_reverifies(client, app):
    register(client, "e1@example.com", "mypassword1")
    r = client.post("/api/account/email", json={"email": "e2@example.com", "password": "mypassword1"})
    assert r.status_code == 200
    me = client.get("/api/me").get_json()
    assert me["user"]["email"] == "e2@example.com"
    assert me["user"]["email_verified"] is False


def test_change_email_conflict(app):
    a = app.test_client(); b = app.test_client()
    register(a, "taken@example.com")
    register(b, "mover@example.com", "moverpass1")
    assert b.post("/api/account/email", json={"email": "taken@example.com", "password": "moverpass1"}).status_code == 409


def test_delete_account_removes_data(client, app):
    register(client, "del@example.com", "deletepass1")
    client.post("/api/jobs", json={"text": "a job", "title": "t"})
    assert client.post("/api/account/delete", json={"password": "WRONG"}).status_code == 403
    assert client.post("/api/account/delete", json={"password": "deletepass1"}).status_code == 200
    with app.app_context():
        from autocv.models import User, Job
        assert User.query.filter_by(email="del@example.com").first() is None
        assert Job.query.count() == 0  # cascade removed the job too


def test_export_has_disposition(client):
    register(client, "exp@example.com")
    r = client.get("/api/account/export")
    assert r.status_code == 200
    assert "attachment" in r.headers.get("Content-Disposition", "")
