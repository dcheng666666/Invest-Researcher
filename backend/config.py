from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "openai"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # Optional override for SessionMiddleware signing (min 16 chars). If empty, secret is read from SQLite app_meta.
    app_session_secret: str = ""

    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
    )

    @field_validator("app_session_secret")
    @classmethod
    def app_session_secret_min_len(cls, v: str) -> str:
        s = v.strip()
        if s and len(s) < 16:
            raise ValueError("APP_SESSION_SECRET must be at least 16 characters when set")
        return v

    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


settings = Settings()
