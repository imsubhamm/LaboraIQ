"""LaboraIQ signed session tokens (HS256)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.config import get_settings

ALGORITHM = "HS256"


def create_session_token(
    *,
    email: str,
    subject: str,
    ttl_minutes: int | None = None,
    extra: dict[str, Any] | None = None,
) -> tuple[str, datetime]:
    settings = get_settings()
    secret = settings.session_secret
    if not secret:
        raise RuntimeError("SESSION_SECRET is required to issue session tokens")
    expires = datetime.now(UTC) + timedelta(minutes=ttl_minutes or settings.session_ttl_minutes)
    payload: dict[str, Any] = {
        "iss": "laboraiq",
        "aud": "laboraiq-api",
        "sub": subject,
        "email": email.lower().strip(),
        "iat": datetime.now(UTC),
        "exp": expires,
        "typ": "session",
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, secret, algorithm=ALGORITHM)
    return token, expires


def verify_session_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    secret = settings.session_secret
    if not secret:
        raise jwt.InvalidTokenError("SESSION_SECRET is not configured")
    return jwt.decode(
        token,
        secret,
        algorithms=[ALGORITHM],
        audience="laboraiq-api",
        issuer="laboraiq",
        options={"require": ["exp", "sub", "email", "typ"]},
    )
