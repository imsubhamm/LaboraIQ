"""OIDC ID token verification against the issuer JWKS."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

from app.config import get_settings


class OidcNotConfiguredError(RuntimeError):
    pass


def oidc_enabled() -> bool:
    settings = get_settings()
    return bool(settings.oidc_issuer and settings.oidc_client_id and settings.oidc_audience)


def discover_jwks_uri(issuer: str) -> str:
    settings = get_settings()
    if settings.oidc_jwks_url:
        return settings.oidc_jwks_url
    metadata_url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    with urllib.request.urlopen(metadata_url, timeout=5) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    jwks_uri = payload.get("jwks_uri")
    if not jwks_uri:
        raise OidcNotConfiguredError("OIDC discovery document missing jwks_uri")
    return str(jwks_uri)


@lru_cache(maxsize=4)
def _jwks_client(jwks_uri: str) -> PyJWKClient:
    return PyJWKClient(jwks_uri, cache_keys=True, lifespan=3600)


def verify_oidc_id_token(id_token: str) -> dict[str, Any]:
    if not oidc_enabled():
        raise OidcNotConfiguredError("OIDC is not configured")
    settings = get_settings()
    assert settings.oidc_issuer and settings.oidc_client_id and settings.oidc_audience
    jwks_uri = discover_jwks_uri(settings.oidc_issuer)
    client = _jwks_client(jwks_uri)
    signing_key = client.get_signing_key_from_jwt(id_token)
    issuers = {settings.oidc_issuer.rstrip("/"), settings.oidc_issuer.rstrip("/") + "/"}
    claims: dict[str, Any] | None = None
    last_error: Exception | None = None
    for issuer in issuers:
        try:
            claims = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=settings.oidc_audience,
                issuer=issuer,
                options={"require": ["exp", "iat", "sub"]},
            )
            break
        except jwt.InvalidIssuerError as error:
            last_error = error
    if claims is None:
        raise last_error or jwt.InvalidIssuerError("OIDC issuer mismatch")
    # Prefer azp/client_id match when present.
    client_claim = claims.get("azp") or claims.get("client_id")
    if client_claim and client_claim != settings.oidc_client_id:
        raise jwt.InvalidTokenError("OIDC client_id/azp mismatch")
    email = claims.get("email")
    if not email and isinstance(claims.get("preferred_username"), str):
        email = claims["preferred_username"]
    if not email:
        raise jwt.InvalidTokenError("OIDC token missing email claim")
    claims["email"] = str(email).lower().strip()
    return claims


def clear_oidc_caches() -> None:
    _jwks_client.cache_clear()
    # tiny sleep helper for tests that rotate keys
    time.sleep(0)


def fetch_oidc_authorization_endpoint() -> str | None:
    if not oidc_enabled():
        return None
    settings = get_settings()
    assert settings.oidc_issuer
    if settings.oidc_authorization_endpoint:
        return settings.oidc_authorization_endpoint
    metadata_url = settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration"
    try:
        with urllib.request.urlopen(metadata_url, timeout=5) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
        return str(payload.get("authorization_endpoint") or "") or None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None
