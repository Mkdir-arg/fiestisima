from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    # 32 bytes is HS256's own recommended minimum key length (RFC 7518
    # 3.2); PyJWT warns below it. Enforced here, not just by convention, so
    # a short secret fails fast at startup instead of quietly signing
    # tokens with less entropy than the algorithm assumes.
    jwt_secret: str = Field(min_length=32)
    site_url: str = "http://localhost:8081"
    cors_origins: list[str] = ["http://localhost:8081"]
    resend_api_key: str | None = None
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
