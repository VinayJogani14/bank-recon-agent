from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    anthropic_api_key: str = ""

    # LLM defaults
    llm_model: str = "claude-sonnet-4-5-20251001"
    llm_max_tokens: int = 1024

    # Match thresholds
    confidence_threshold: float = 0.85
    fuzzy_match_threshold: float = 85.0
    date_window_days: int = 7

    # Retry
    max_retries: int = 3

    # Cost per token (USD) — approximate for cost tracking
    cost_per_input_token: float = 3e-6
    cost_per_output_token: float = 15e-6


settings = Settings()
