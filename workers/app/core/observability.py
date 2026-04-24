from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger

_logger = get_logger("raijin.worker.observability")


def init_sentry(service_name: str) -> bool:
    settings = get_settings()
    if not settings.sentry_dsn:
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    except ImportError:
        _logger.warning("sentry.unavailable", service=service_name)
        return False

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=settings.release_version,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        integrations=[
            CeleryIntegration(),
            LoggingIntegration(event_level=None),
            SqlalchemyIntegration(),
        ],
        send_default_pii=False,
        server_name=service_name,
    )
    _logger.info("sentry.enabled", service=service_name)
    return True
