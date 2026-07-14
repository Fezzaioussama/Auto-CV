"""Authentication, password reset and email verification."""

from conftest import register, login


def test_register_logs_in_and_me(client):
    r = register(client, "alice@example.com")
    assert r.status_code == 200
    me = client.get("/api/me").get_json()
    assert me["authenticated"] is True
    assert me["user"]["email"] == "alice@example.com"
    assert me["user"]["email_verified"] is False


def test_duplicate_email_rejected(client):
    register(client, "bob@example.com")
    client.get("/logout")
    r = register(client, "bob@example.com")
    assert r.status_code == 409


def test_short_password_rejected(client):
    r = client.post("/register", json={"email": "x@example.com", "password": "short"})
    assert r.status_code == 400


def test_login_wrong_password(client):
    register(client, "carol@example.com", "rightpassword")
    client.get("/logout")
    r = login(client, "carol@example.com", "wrongpassword")
    assert r.status_code == 401


def test_password_reset_is_single_use(client, app):
    register(client, "dave@example.com", "originalpass")
    client.get("/logout")
    with app.app_context():
        from autocv.models import User
        from autocv.tokens import make_token, PURPOSE_RESET
        u = User.query.filter_by(email="dave@example.com").first()
        token = make_token(PURPOSE_RESET, {"uid": u.id, "h": u.password_hash[-20:]})

    # First use succeeds.
    r = client.post(f"/reset-password/{token}", json={"password": "brandnewpass"})
    assert r.status_code == 200
    # New password works (JSON login → 200 with success).
    client.get("/logout")
    r = login(client, "dave@example.com", "brandnewpass")
    assert r.status_code == 200 and r.get_json()["success"] is True
    # Reusing the same token now fails (password hash changed → token invalid).
    client.get("/logout")
    r = client.post(f"/reset-password/{token}", json={"password": "thirdpass"})
    assert r.status_code in (302, 400)  # redirected to forgot-password


def test_forgot_password_no_account_enumeration(client):
    # Unknown email returns the same generic success as a known one.
    r = client.post("/forgot-password", json={"email": "nobody@example.com"})
    assert r.status_code == 200
    assert r.get_json()["success"] is True


def test_verify_email(client, app):
    register(client, "erin@example.com")
    with app.app_context():
        from autocv.models import User
        from autocv.tokens import make_token, PURPOSE_VERIFY
        u = User.query.filter_by(email="erin@example.com").first()
        token = make_token(PURPOSE_VERIFY, u.id)
    client.get(f"/verify-email/{token}")
    with app.app_context():
        from autocv.models import User
        assert User.query.filter_by(email="erin@example.com").first().email_verified is True
