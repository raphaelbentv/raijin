from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"
    release_version: str = "local"

    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.05

    database_url: str = Field(
        default="postgresql+psycopg2://raijin:raijin_dev_password@postgres:5432/raijin",
    )

    celery_broker_url: str
    celery_result_backend: str

    s3_endpoint_url: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket_invoices: str
    s3_region: str = "eu-west-1"

    azure_di_endpoint: str = ""
    azure_di_key: str = ""
    azure_di_model: str = "prebuilt-invoice"
    azure_di_locale: str = "el-GR"
    azure_di_timeout_seconds: int = 120
    azure_di_mock_in_development: bool = True

    ocr_max_retries: int = 3
    ocr_retry_backoff_seconds: int = 30

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def sync_database_url(self) -> str:
        url = self.database_url
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
