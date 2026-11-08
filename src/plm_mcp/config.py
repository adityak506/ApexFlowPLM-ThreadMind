"""Configuration management for PLM MCP Server."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """PLM MCP Server settings loaded from environment or .env file."""

    # Backend selection: 'mock' (default) or 'windchill'
    plm_backend: str = "mock"

    # Mock backend configuration
    plm_sqlite_path: str = "plm_mock.db"
    plm_seed_on_startup: bool = True

    # Windchill backend configuration (stubs for future integration)
    # TODO: verify against Windchill docs
    windchill_base_url: str = ""
    windchill_username: str = ""
    windchill_password: str = ""
    windchill_container: str = "Demo Product"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

