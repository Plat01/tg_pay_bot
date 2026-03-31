"""Application configuration using pydantic-settings."""

from decimal import Decimal
from functools import lru_cache

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields from .env (like legacy variables)
    )

    # Telegram Bot
    bot_token: str
    bot_link: str = "https://t.me/testAiogram12Bot"  # Link to the bot for referral links

    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "tg_pay_bot"
    db_user: str = "postgres"
    db_password: str = "postgres"

    # Referral System
    referral_bonus_percent: Decimal = Decimal("10.00")
    referral_code_length: int = 8

    # Application
    debug: bool = False
    proxy_url: str = ""

    # Platega Payment Provider
    platega_api_url: str = "https://api.platega.io"
    platega_merchant_id: str = ""  # X-MerchantId header (UUID)
    platega_secret: str = ""  # X-Secret header (API key)
    platega_webhook_url: str = ""  # URL for receiving webhooks (must be publicly accessible)
    platega_webhook_secret: str = ""  # Secret for webhook signature verification
    default_payment_provider: str = "platega"

    @field_validator("debug", mode="before")
    @classmethod
    def validate_debug(cls, v: str | bool) -> bool:
        """Parse debug value, handling system DEBUG variable conflicts."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            # Handle truthy values
            if v.lower() in ("true", "1", "yes", "on"):
                return True
            # Handle falsy values (including system DEBUG=WARN from debuginfod)
            if v.lower() in ("false", "0", "no", "off", "warn", ""):
                return False
        return False

    # Admin IDs for notifications (comma-separated in .env, e.g. "123,456,789")
    admin_ids: str = ""

    @computed_field
    @property
    def admin_id_list(self) -> list[int]:
        """Parse admin IDs from comma-separated string."""
        if not self.admin_ids.strip():
            return []
        return [int(id.strip()) for id in self.admin_ids.split(",") if id.strip()]

    @property
    def database_url(self) -> str:
        """Build async database URL for PostgreSQL."""
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
