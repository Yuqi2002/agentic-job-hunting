from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    discord_webhook_url: str = ""
    discord_bot_token: str = ""
    discord_channel_id: int = 0
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    # Stored as comma-separated strings in .env, split in validator
    target_cities: str = "San Francisco,New York,Seattle,Austin"
    target_roles: str = "software engineer,ai engineer,ml engineer,machine learning engineer,forward deployed engineer,solutions engineer,sales engineer"
    max_experience_years: int = 4
    db_path: Path = Path("data/jobs.db")
    log_level: str = "INFO"
    cache_dir: Path = Path("data/cache")

    @property
    def cities_list(self) -> list[str]:
        return [c.strip() for c in self.target_cities.split(",") if c.strip()]

    @property
    def roles_list(self) -> list[str]:
        return [r.strip() for r in self.target_roles.split(",") if r.strip()]


settings = Settings()
