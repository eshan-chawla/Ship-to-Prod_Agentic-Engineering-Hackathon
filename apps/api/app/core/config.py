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
    tinyfish_search_url: str = "https://api.search.tinyfish.ai"
    tinyfish_fetch_url: str = "https://api.fetch.tinyfish.ai"
    tinyfish_agent_url: str = "https://agent.tinyfish.ai/v1/automation/run"
    tinyfish_timeout_seconds: float = Field(default=20.0, gt=0)
    tinyfish_max_retries: int = Field(default=2, ge=0, le=5)
    risk_alert_threshold: int = Field(default=70, ge=0, le=100)
    vapi_api_key: str | None = None
    vapi_webhook_secret: str | None = None
    vapi_mock_mode: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
