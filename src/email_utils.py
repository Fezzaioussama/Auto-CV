"""Transactional email delivery (password reset, email verification).

Follows the same philosophy as the rest of the app: everything is driven by
environment variables and it **degrades gracefully**. If no SMTP host is
configured (e.g. local dev), emails are not sent over the network — instead the
full message, including any action link, is logged so the developer can copy the
link from the console. That keeps the reset/verify flows fully usable offline.

Environment
-----------
* ``SMTP_HOST``       — SMTP server. **If unset, dev log-only mode is used.**
* ``SMTP_PORT``       — default 587.
* ``SMTP_USERNAME`` / ``SMTP_PASSWORD`` — credentials (optional for open relays).
* ``SMTP_USE_TLS``    — STARTTLS, default ``true``.
* ``SMTP_USE_SSL``    — implicit TLS (e.g. port 465), default ``false``.
* ``MAIL_FROM``       — From header, default ``Auto-CV <no-reply@auto-cv.local>``.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from flask import current_app


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _mail_from() -> str:
    return os.environ.get("MAIL_FROM", "").strip() or "Auto-CV <no-reply@auto-cv.local>"


def is_configured() -> bool:
    """True when a real SMTP host is set; otherwise we run in dev log-only mode."""
    return bool(os.environ.get("SMTP_HOST", "").strip())


def send_email(to: str, subject: str, body_text: str, *, body_html: str | None = None) -> bool:
    """Send an email. Returns True on success (or in dev log-only mode).

    Never raises: SMTP problems are logged and reported as ``False`` so a failed
    send can't 500 a request or leak provider errors to the user.
    """
    if not is_configured():
        # Dev fallback: log the whole message so the link is reachable locally.
        current_app.logger.warning(
            "[email:DEV] SMTP not configured — not sending. "
            "To=%s | Subject=%s\n%s",
            to, subject, body_text,
        )
        return True

    host = os.environ["SMTP_HOST"].strip()
    port = int(os.environ.get("SMTP_PORT", "587") or "587")
    username = os.environ.get("SMTP_USERNAME", "").strip() or None
    password = os.environ.get("SMTP_PASSWORD", "") or None
    use_ssl = _bool_env("SMTP_USE_SSL", default=False)
    use_tls = _bool_env("SMTP_USE_TLS", default=not use_ssl)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _mail_from()
    msg["To"] = to
    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    try:
        if use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=15) as server:
                if username:
                    server.login(username, password or "")
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                if use_tls:
                    server.starttls(context=ssl.create_default_context())
                if username:
                    server.login(username, password or "")
                server.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001 - never propagate mail errors
        current_app.logger.error("Email send to %s failed: %s", to, exc)
        return False


def send_password_reset(to: str, reset_url: str) -> bool:
    subject = "Reset your Auto-CV password"
    text = (
        "We received a request to reset your Auto-CV password.\n\n"
        f"Reset it here (the link expires in 1 hour):\n{reset_url}\n\n"
        "If you didn't request this, you can safely ignore this email — your "
        "password won't change."
    )
    return send_email(to, subject, text)


def send_email_verification(to: str, verify_url: str) -> bool:
    subject = "Confirm your Auto-CV email"
    text = (
        "Welcome to Auto-CV! Please confirm your email address.\n\n"
        f"Confirm here (the link expires in 24 hours):\n{verify_url}\n\n"
        "If you didn't create this account, you can ignore this email."
    )
    return send_email(to, subject, text)
