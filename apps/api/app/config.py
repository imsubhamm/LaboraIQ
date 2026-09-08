from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    cors_origins: list[str] | str = "http://localhost:3000"
    # Comma-separated overlay IPs (e.g. Tailscale) allowed for analyzer TCP probes.
    analyzer_overlay_targets: list[str] | str = "100.122.201.68"
    lis_dispatch_mode: Literal["immediate", "outbox_only"] = "outbox_only"
    lis_outbound_host: str | None = None
    lis_outbound_port: int = Field(default=0, ge=0, le=65535)
    lis_outbound_use_mllp: bool = True
    lis_outbound_timeout_seconds: int = Field(default=5, ge=1, le=60)
    log_level: str = "INFO"
    health_availability_weight: float = Field(default=0.30, ge=0, le=1)
    health_order_success_weight: float = Field(default=0.25, ge=0, le=1)
    health_result_success_weight: float = Field(default=0.20, ge=0, le=1)
    health_latency_weight: float = Field(default=0.15, ge=0, le=1)
    health_queue_weight: float = Field(default=0.10, ge=0, le=1)
    health_healthy_min: float = Field(default=90, ge=0, le=100)
    health_warning_min: float = Field(default=75, ge=0, le=100)
    health_degraded_min: float = Field(default=50, ge=0, le=100)
    health_latency_good_ms: int = Field(default=200, ge=1, le=120_000)
    health_latency_critical_ms: int = Field(default=2000, ge=1, le=120_000)
    health_queue_warn: int = Field(default=5, ge=1, le=10_000)
    health_queue_critical: int = Field(default=20, ge=1, le=10_000)
    health_retry_rate_warn: float = Field(default=0.30, ge=0, le=1)
    health_order_fail_count_warn: int = Field(default=3, ge=1, le=10_000)
    health_delayed_result_hours: int = Field(default=4, ge=1, le=168)

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
        weights = (
            self.health_availability_weight
            + self.health_order_success_weight
            + self.health_result_success_weight
            + self.health_latency_weight
            + self.health_queue_weight
        )
        if abs(weights - 1.0) > 0.001:
            raise ValueError("Analyzer health score weights must sum to 1.0")
        if self.health_latency_critical_ms < self.health_latency_good_ms:
            raise ValueError("HEALTH_LATENCY_CRITICAL_MS must be >= HEALTH_LATENCY_GOOD_MS")
        if self.health_queue_critical < self.health_queue_warn:
            raise ValueError("HEALTH_QUEUE_CRITICAL must be >= HEALTH_QUEUE_WARN")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
