from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SiteWatch"
    secret_key: str = "change-me-to-a-long-random-string"
    admin_email: str = "admin@sitewatch.app"
    admin_password: str = "admin123"

    database_url: str = "postgresql+asyncpg://sitewatch:sitewatch@localhost:5432/sitewatch"
    redis_url: str = "redis://localhost:6379/0"
    frontend_url: str = "http://localhost:3000"

    max_concurrent_checks: int = 20
    scheduler_tick_seconds: int = 10
    default_check_interval: int = 60
    failure_threshold: int = 3
    recovery_threshold: int = 2
    slow_threshold_ms: int = 2000
    check_retention_days: int = 7
    failed_email_retention_days: int = 10

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "SiteWatch <alerts@yourdomain.com>"
    smtp_use_tls: bool = True
    alert_email: str = "admin@sitewatch.app"
    notifications_enabled: bool = True

    access_token_expire_minutes: int = 60 * 24 * 7


@lru_cache
def get_settings() -> Settings:
    return Settings()
