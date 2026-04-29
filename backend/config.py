from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_provider: str = "openai"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
