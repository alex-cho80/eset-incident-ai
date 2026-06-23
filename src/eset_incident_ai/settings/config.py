from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "eset-incident-ai"
    environment: str = "development"
    log_level: str = "INFO"

    eset_base_url: str = Field(default="https://eu.incident-management.eset.systems")
    eset_auth_url: str = Field(default="https://eu.business-account.iam.eset.systems/oauth/token")
    eset_username: str = ""
    eset_password: str = ""
    eset_client_id: str = ""
    eset_client_secret: str = ""
    eset_access_token: str = ""
    eset_access_token_expires_in: int = 3600
    eset_poll_interval_seconds: int = 300
    eset_page_size: int = 100
    incident_notify_limit: int = 10
    incident_notify_cron_hour: int = 10
    incident_notify_cron_minute: int = 0
    incident_notify_timezone: str = "Asia/Seoul"

    database_url: str = "postgresql+psycopg://incident_ai:password@postgres:5432/incident_ai"
    redis_url: str = "redis://redis:6379/0"

    discord_webhook_url: str = ""
    discord_enabled: bool = False

    llm_provider: str = "anthropic"
    llm_model: str = ""
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"

    sanitizer_hmac_secret: str = ""
