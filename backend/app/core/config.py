from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    release_version: str = "local"

    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.05

    database_url: PostgresDsn

    redis_url: str
    celery_broker_url: str
    celery_result_backend: str

    s3_endpoint_url: str
    s3_public_url: str = ""
    s3_access_key: str
    s3_secret_key: str
    s3_bucket_invoices: str
    s3_region: str = "eu-west-1"
    s3_signed_url_ttl_seconds: int = 900

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 30
    jwt_refresh_ttl_days: int = 14

    azure_di_endpoint: str = ""
    azure_di_key: str = ""
    azure_di_model: str = "prebuilt-invoice"
    azure_di_locale: str = "el-GR"

    encryption_key: str = ""

    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_tenant: str = "common"
    microsoft_redirect_uri: str = "http://localhost:6200/integrations/outlook/callback"
    microsoft_scopes: str = "Mail.Read offline_access User.Read"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:6200/integrations/google/callback"
    google_scopes: str = (
        "https://www.googleapis.com/auth/gmail.readonly "
        "https://www.googleapis.com/auth/drive.readonly "
        "openid email"
    )

    frontend_url: str = "http://localhost:6100"
    backend_public_url: str = "http://localhost:6200"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "no-reply@raijin.local"
    smtp_use_tls: bool = True
    resend_api_key: str = ""
    resend_from_email: str = "Raijin <no-reply@raijin.local>"

    upload_max_size_mb: int = 20
    upload_allowed_mime: str = "application/pdf,image/jpeg,image/png"

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:6100"])

    rate_limit_login_per_min: int = 10
    rate_limit_register_per_min: int = 3

    @property
    def upload_max_size_bytes(self) -> int:
        return self.upload_max_size_mb * 1024 * 1024

    @property
    def allowed_mime_set(self) -> set[str]:
        return {m.strip() for m in self.upload_allowed_mime.split(",") if m.strip()}

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
