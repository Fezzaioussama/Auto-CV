"""Signed, expiring tokens for email links (password reset, verification).

Tokens are stateless: we sign a small payload with the app ``SECRET_KEY`` using
``itsdangerous`` (a Flask dependency), so no extra DB table is needed and a
token automatically becomes useless after ``max_age``. Each purpose uses its own
salt, so a password-reset token can never be replayed as an email-verification
token (or vice-versa).
"""

from __future__ import annotations

from typing import Any, Optional

from flask import current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

# Purposes double as the cryptographic salt; keep them stable once shipped.
PURPOSE_RESET = "password-reset"
PURPOSE_VERIFY = "email-verify"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def make_token(purpose: str, payload: Any) -> str:
    """Create a signed token carrying ``payload`` for the given ``purpose``."""
    return _serializer().dumps(payload, salt=purpose)


def read_token(purpose: str, token: str, *, max_age: int) -> Optional[Any]:
    """Return the payload if the token is valid and unexpired, else ``None``.

    ``max_age`` is in seconds. Any tampering, wrong purpose, or expiry yields
    ``None`` so callers can show a single "invalid or expired link" message.
    """
    if not token:
        return None
    try:
        return _serializer().loads(token, salt=purpose, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
