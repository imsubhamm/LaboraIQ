from functools import lru_cache
from typing import Annotated, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str
    dev_auth_enabled: bool = True
    dev_auth_user_email: str = "admin@dev.labora.local"
    dev_auth_organization_code: str = "DEVLAB"
    session_ttl_minutes: int = Field(default=60, ge=5, le=1440)
    session_secret: str = "dev-insecure-session-secret-change-me"
    db_pool_size: int = Field(default=10, ge=1, le=50)
    db_max_overflow: int = Field(default=20, ge=0, le=50)
    db_pool_timeout: int = Field(default=30, ge=1, le=120)
    db_pool_recycle: int = Field(default=300, ge=30, le=3600)
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_client_id: str | None = None
    oidc_jwks_url: str | None = None
    oidc_authorization_endpoint: str | None = None
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    # Comma-separated overlay IPs (e.g. Tailscale) allowed for analyzer TCP probes.
    analyzer_overlay_targets: Annotated[list[str], NoDecode] = ["100.122.201.68"]
    log_level: str = "INFO"

    @field_validator("cors_origins", "analyzer_overlay_targets", mode="before")
    @classmethod
    def parse_csv_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator(
        "oidc_issuer", "oidc_audience", "oidc_client_id", "oidc_jwks_url", mode="before"
    )
    @classmethod
    def empty_oidc_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def enforce_production_auth(self) -> Self:
        if self.environment.lower() == "production" and self.dev_auth_enabled:
            raise ValueError("DEV_AUTH_ENABLED must be false when ENVIRONMENT=production")
        if self.environment.lower() == "production" and (
            not self.session_secret or self.session_secret.startswith("dev-insecure-session-secret")
        ):
            raise ValueError("SESSION_SECRET must be set to a strong value in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
