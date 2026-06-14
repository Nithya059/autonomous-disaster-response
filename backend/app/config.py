from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = "sqlite:///./disaster_response.db"

    # LLM
    openai_api_key: str = ""

    # External APIs
    gdacs_api_url: str = "https://www.gdacs.org/xml/rss.xml"
    openweather_api_key: str = ""

    # CORS — stored as raw string, parsed into list by validator
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # WebSocket
    ws_heartbeat_interval: int = 30

    # Scheduler
    scheduler_interval_seconds: int = 60

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return upper

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        allowed = {"development", "production", "test"}
        lower = v.lower()
        if lower not in allowed:
            raise ValueError(f"app_env must be one of {allowed}")
        return lower

    def get_cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS_ORIGINS string into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def use_mock_data(self) -> bool:
        """Fall back to mock data when external API keys are absent."""
        return not self.openweather_api_key and self.app_env != "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached Settings singleton.
    Use as a FastAPI dependency: Depends(get_settings)
    or call directly: get_settings()
    """
    return Settings()
