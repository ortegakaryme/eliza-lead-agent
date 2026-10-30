"""Runtime configuration.

All secrets come from environment variables (or a local .env file in development).
If a required variable is missing, the app fails at startup with a clear message
instead of failing later in the middle of a live call.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    notion_api_key: str = Field(min_length=10)
    notion_database_id: str = Field(min_length=10)
    webhook_secret: str = Field(min_length=16)
    log_level: str = "INFO"
    timezone: str = "America/Mexico_City"  # Toluca/Metepec use Central Mexico time


@lru_cache
def get_settings() -> Settings:
    return Settings()
