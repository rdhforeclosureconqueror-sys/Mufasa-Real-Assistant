from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Community Quest Engine"
    env: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./quest_engine.db"

    jwt_secret: str = Field(default="dev-secret-change-me", min_length=16)
    jwt_algorithm: str = "HS256"
    jwt_exp_minutes: int = 60 * 24

    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    stt_url: str = ""
    tts_url: str = ""

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        if self.env == "production" and self.jwt_secret == "dev-secret-change-me":
            raise ValueError("JWT_SECRET must be set in production.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
