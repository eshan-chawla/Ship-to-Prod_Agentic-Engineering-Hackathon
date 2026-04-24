from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./market_os.db"
    redis_url: str = "redis://localhost:6379/0"
    dev_auth_email: str = "demo@market-os.local"
    dev_auth_password: str = "demo-password"
    tinyfish_api_key: str | None = None
    tinyfish_base_url: str = "https://api.tinyfish.io"
    risk_alert_threshold: int = Field(default=70, ge=0, le=100)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

