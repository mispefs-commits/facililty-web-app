from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    secret_key: str = "dev-only-secret-change-me"
    access_token_minutes: int = 60
    database_url: str = "sqlite:///./helpdesk.db"
    upload_dir: str = "./uploads"
    max_upload_mb: int = 10
    cors_origins: str = "http://localhost:5173"
    seed_demo: bool = False
    demo_password: str = "ChangeMe@123"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"


settings = Settings()
