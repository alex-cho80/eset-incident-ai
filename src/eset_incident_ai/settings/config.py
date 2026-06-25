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
    eset_detection_page_size: int = 1000
    incident_notify_limit: int = 10
    incident_notify_cron_hour: int = 10
    incident_notify_cron_minute: int = 0
    incident_notify_timezone: str = "Asia/Seoul"
    detection_notify_limit: int = 500
    detection_max_pages_per_run: int = 1000
    detection_backfill_window_days: int = 30
    detection_notify_cron_interval_minutes: int = 60

    database_url: str = "postgresql+psycopg://incident_ai:password@postgres:5432/incident_ai"
    redis_url: str = "redis://redis:6379/0"

    discord_webhook_url: str = ""
    discord_enabled: bool = False

    llm_provider: str = "ollama"
    llm_model: str = ""
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:7b-instruct-q4_K_M"
    ollama_keep_alive: str = "0s"
    llm_timeout_seconds: float = 240.0
    llm_max_retries: int = 2
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"

    sanitizer_hmac_secret: str = ""
