"""Phase 5 authentication: session JWTs, OIDC exchange, production guards."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt
import pytest
from app.auth import get_auth_context
from app.config import Settings, get_settings
from app.main import app
from app.models import Organization, User
from app.session_tokens import create_session_token, verify_session_token
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_session_token_roundtrip() -> None:
    token, expires = create_session_token(email="admin@alpha.test", subject="user-1")
    assert expires > datetime.now(UTC)
    claims = verify_session_token(token)
    assert claims["email"] == "admin@alpha.test"
    assert claims["typ"] == "session"
    assert claims["aud"] == "laboraiq-api"


def test_bearer_session_authenticates(db: Session) -> None:
    org = Organization(name="Auth Org", code="AUTHORG")
    db.add(org)
    db.flush()
    user = User(
        organization_id=org.id,
        email="admin@alpha.test",
        display_name="Admin",
        auth_provider_id="test:admin",
    )
    db.add(user)
    db.commit()

    token, _ = create_session_token(email=user.email, subject=str(user.id))
    app.dependency_overrides.pop(get_auth_context, None)
    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        denied = client.get("/api/v1/auth/me")
        assert denied.status_code == 401
        ok = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert ok.status_code == 200
        body = ok.json()
        assert body["email"] == "admin@alpha.test"
        assert body["user_id"] == str(user.id)
    app.dependency_overrides.clear()


def test_mint_session_via_dev_header(db: Session) -> None:
    org = Organization(name="Auth Org", code="AUTHORG2")
    db.add(org)
    db.flush()
    user = User(
        organization_id=org.id,
        email="admin@dev.labora.local",
        display_name="Dev Admin",
        auth_provider_id="dev:admin",
    )
    db.add(user)
    db.commit()

    app.dependency_overrides.pop(get_auth_context, None)
    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/session",
            headers={"X-Dev-User-Email": "admin@dev.labora.local"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["token_type"] == "Bearer"
        claims = verify_session_token(payload["access_token"])
        assert claims["email"] == "admin@dev.labora.local"
    app.dependency_overrides.clear()


def test_permission_denied_with_session_token(db: Session) -> None:
    org = Organization(name="Auth Org", code="AUTHORG3")
    db.add(org)
    db.flush()
    user = User(
        organization_id=org.id,
        email="limited@alpha.test",
        display_name="Limited",
        auth_provider_id="test:limited",
    )
    db.add(user)
    db.commit()
    token, _ = create_session_token(email=user.email, subject=str(user.id))

    app.dependency_overrides.pop(get_auth_context, None)
    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/branches",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Blocked", "code": "BLOCKED", "time_zone": "UTC"},
        )
        assert response.status_code == 403
        assert "Missing permission" in response.json()["detail"]
    app.dependency_overrides.clear()


def test_production_settings_forbid_dev_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEV_AUTH_ENABLED", "true")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("SESSION_SECRET", "strong-production-session-secret")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        Settings()


def test_production_settings_require_strong_session_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEV_AUTH_ENABLED", "false")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("SESSION_SECRET", "dev-insecure-session-secret-change-me")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        Settings()


def test_oidc_session_exchange(db: Session) -> None:
    org = Organization(name="Auth Org", code="AUTHORG4")
    db.add(org)
    db.flush()
    user = User(
        organization_id=org.id,
        email="oidc.user@alpha.test",
        display_name="OIDC User",
        auth_provider_id="dev:oidc-user",
    )
    db.add(user)
    db.commit()

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    now = datetime.now(UTC)
    id_token = jwt.encode(
        {
            "iss": "https://idp.example.com",
            "aud": "laboraiq-web",
            "sub": "oidc-sub-123",
            "email": "oidc.user@alpha.test",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        private_pem,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )

    class _Key:
        def __init__(self, key: object) -> None:
            self.key = key

    class _Client:
        def get_signing_key_from_jwt(self, _token: str) -> _Key:
            return _Key(private_key.public_key())

    app.dependency_overrides.pop(get_auth_context, None)
    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: db

    with (
        patch("app.oidc.oidc_enabled", return_value=True),
        patch("app.oidc.discover_jwks_uri", return_value="https://idp.example.com/jwks"),
        patch("app.oidc._jwks_client", return_value=_Client()),
        patch(
            "app.oidc.get_settings",
            return_value=Settings(
                database_url="sqlite://",
                oidc_issuer="https://idp.example.com",
                oidc_audience="laboraiq-web",
                oidc_client_id="laboraiq-web",
                session_secret="dev-insecure-session-secret-change-me",
            ),
        ),
        TestClient(app) as client,
    ):
        response = client.post("/api/v1/auth/oidc/session", json={"id_token": id_token})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["email"] == "oidc.user@alpha.test"
        claims = verify_session_token(body["access_token"])
        assert claims["email"] == "oidc.user@alpha.test"

    db.refresh(user)
    assert user.auth_provider_id == "oidc-sub-123"
    app.dependency_overrides.clear()


def test_oidc_metadata_when_disabled() -> None:
    with TestClient(app) as client:
        # Override auth not needed; endpoint is public but TestClient still boots app.
        response = client.get("/api/v1/auth/oidc/metadata")
        assert response.status_code == 200
        assert response.json()["enabled"] is False
