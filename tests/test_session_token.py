"""Per-user session token: rotating it invalidates other sessions/devices.

Each ``app.test_client()`` keeps its own cookie jar, so two clients logged into
the same account stand in for two devices.
"""

from conftest import register


def _authenticated(c) -> bool:
    return c.get("/api/me").get_json()["authenticated"]


def test_password_change_signs_out_other_devices(client, app):
    # Device A registers (and is logged in by default).
    register(client, "sam@example.com", "originalpass")
    # Device B logs into the same account.
    device_b = app.test_client()
    assert device_b.post(
        "/login", json={"email": "sam@example.com", "password": "originalpass"}
    ).status_code == 200
    assert _authenticated(device_b) is True

    # Device A changes the password.
    r = client.post(
        "/api/account/password",
        json={"current_password": "originalpass", "new_password": "newpass123"},
    )
    assert r.status_code == 200

    # Device A stays logged in; device B is booted (token rotated underneath it).
    assert _authenticated(client) is True
    assert _authenticated(device_b) is False


def test_logout_others_revokes_other_sessions(client, app):
    register(client, "kim@example.com", "originalpass")
    device_b = app.test_client()
    device_b.post("/login", json={"email": "kim@example.com", "password": "originalpass"})
    assert _authenticated(device_b) is True

    assert client.post("/api/account/logout-others").status_code == 200

    assert _authenticated(client) is True       # current device kept
    assert _authenticated(device_b) is False    # the other device is gone


def test_password_reset_invalidates_existing_sessions(client, app):
    register(client, "lee@example.com", "originalpass")  # client is logged in
    assert _authenticated(client) is True

    with app.app_context():
        from autocv.models import User
        from autocv.tokens import make_token, PURPOSE_RESET

        u = User.query.filter_by(email="lee@example.com").first()
        token = make_token(PURPOSE_RESET, {"uid": u.id, "h": u.password_hash[-20:]})

    assert client.post(f"/reset-password/{token}", json={"password": "brandnewpass"}).status_code == 200
    # The session opened before the reset no longer validates.
    assert _authenticated(client) is False
