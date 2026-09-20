from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    site_url: str = "http://localhost:8081"
    cors_origins: list[str] = ["http://localhost:8081"]
    resend_api_key: str | None = None
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
