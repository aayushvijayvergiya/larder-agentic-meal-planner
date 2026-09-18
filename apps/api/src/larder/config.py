"""Application settings, loaded from environment variables (LLD §2.4)."""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["local", "test", "production"] = "local"
    database_url: str
    checkpoint_database_url: str | None = None
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    supabase_anon_key: str = ""  # sent as `apikey` when fetching JWKS (needed by the local gateway)
    auth_mode: Literal["jwks", "hs256"] = "jwks"
    jwt_audience: str = "authenticated"
    llm_provider: Literal["groq", "fake"] | None = None
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-120b"
    llm_timeout_seconds: int = 60
    scheduler_secret: str = ""
    cors_origins: str = "http://localhost:3000"
    plan_history_weeks: int = 8

    @model_validator(mode="after")
    def _defaults(self) -> "Settings":
        if self.llm_provider is None:
            self.llm_provider = "groq" if self.groq_api_key else "fake"
        if self.checkpoint_database_url is None:
            self.checkpoint_database_url = self.database_url.replace("postgresql+asyncpg://", "postgresql://")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
