from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    # Postgres
    database_url: str = "postgresql+asyncpg://nms:nms@localhost:5432/nms"
    sync_database_url: str = "postgresql+psycopg2://nms:nms@localhost:5432/nms"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret_key: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Credential encryption (Fernet key, generate with cryptography.fernet.Fernet.generate_key())
    credential_encryption_key: str = "change-me-generate-a-fernet-key"

    # Worker tuning
    max_concurrent_polls: int = 50
    default_interval_critical: int = 30
    default_interval_normal: int = 60
    default_interval_low: int = 300
    poll_timeout_seconds: int = 10
    poll_retries: int = 1
    alert_consecutive_breaches: int = 2
    alert_consecutive_recoveries: int = 2

    # Discovery guardrails
    discovery_max_hosts: int = 4096
    discovery_max_prefix_len: int = 20  # smallest allowed prefix (i.e. blocks /19 and larger sweeps)
    discovery_rate_pps: int = 20

    # Seeded on first boot if no users exist yet
    initial_admin_email: str = "admin@example.com"
    initial_admin_password: str = "change-me-immediately"


@lru_cache
def get_settings() -> Settings:
    return Settings()
