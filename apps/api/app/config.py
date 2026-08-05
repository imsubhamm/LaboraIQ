from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str
    dev_auth_enabled: bool = True
    dev_auth_user_email: str = "admin@dev.labora.local"
    dev_auth_organization_code: str = "DEVLAB"
    session_ttl_minutes: int = Field(default=60, ge=5, le=1440)
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
