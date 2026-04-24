from __future__ import annotations

import os
import threading
import time
from collections import Counter
from decimal import Decimal
from typing import TYPE_CHECKING

from raijin_shared.models.erp import ErpExport, ErpExportStatus
from raijin_shared.models.invoice import Invoice, InvoiceStatus
from raijin_shared.models.mydata import MyDataSubmission, MyDataSubmissionStatus
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


_logger = get_logger("raijin.observability")


class HttpMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: Counter[tuple[str, str, str]] = Counter()
        self._duration_seconds: Counter[tuple[str, str]] = Counter()

    def record(self, *, method: str, path: str, status_code: int, duration_seconds: float) -> None:
        status_class = f"{status_code // 100}xx"
        route = _normalize_path(path)
        with self._lock:
            self._requests[(method.upper(), route, status_class)] += 1
            self._duration_seconds[(method.upper(), route)] += duration_seconds

    def snapshot(self) -> tuple[dict[tuple[str, str, str], int], dict[tuple[str, str], float]]:
        with self._lock:
            return dict(self._requests), dict(self._duration_seconds)


http_metrics = HttpMetrics()


def _normalize_path(path: str) -> str:
    if path.startswith("/invoices/") and len(path.split("/")) > 2:
        return "/invoices/{id}"
    if path.startswith("/suppliers/") and len(path.split("/")) > 2:
        return "/suppliers/{id}"
    if path.startswith("/admin/users/") and len(path.split("/")) > 3:
        return "/admin/users/{id}"
    return path or "/"


def init_sentry(service_name: str) -> bool:
    settings = get_settings()
    if not settings.sentry_dsn:
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
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
        profiles_sample_rate=0.0,
        integrations=[
            FastApiIntegration(),
            LoggingIntegration(event_level=None),
            SqlalchemyIntegration(),
        ],
        send_default_pii=False,
        server_name=service_name,
    )
    _logger.info("sentry.enabled", service=service_name)
    return True


def prometheus_line(name: str, value: int | float | Decimal, labels: dict[str, str] | None = None) -> str:
    label_text = ""
    if labels:
        pairs = [f'{key}="{_escape_label(str(val))}"' for key, val in sorted(labels.items())]
        label_text = "{" + ",".join(pairs) + "}"
    return f"{name}{label_text} {float(value) if isinstance(value, Decimal) else value}"


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


async def render_prometheus_metrics(db: AsyncSession) -> str:
    settings = get_settings()
    lines: list[str] = [
        "# HELP raijin_build_info Build and runtime metadata.",
        "# TYPE raijin_build_info gauge",
        prometheus_line(
            "raijin_build_info",
            1,
            {
                "environment": settings.environment,
                "release": settings.release_version,
                "service": "backend",
            },
        ),
        "# HELP raijin_http_requests_total HTTP requests observed by the API process.",
        "# TYPE raijin_http_requests_total counter",
    ]

    requests, durations = http_metrics.snapshot()
    for (method, route, status_class), count in requests.items():
        lines.append(
            prometheus_line(
                "raijin_http_requests_total",
                count,
                {"method": method, "route": route, "status_class": status_class},
            )
        )

    lines.extend(
        [
            "# HELP raijin_http_request_duration_seconds_total Total HTTP duration observed by the API process.",
            "# TYPE raijin_http_request_duration_seconds_total counter",
        ]
    )
    for (method, route), duration in durations.items():
        lines.append(
            prometheus_line(
                "raijin_http_request_duration_seconds_total",
                round(duration, 6),
                {"method": method, "route": route},
            )
        )

    invoice_rows = await db.execute(
        select(Invoice.status, func.count(Invoice.id)).group_by(Invoice.status)
    )
    lines.extend(
        [
            "# HELP raijin_invoices_total Invoices grouped by processing status.",
            "# TYPE raijin_invoices_total gauge",
        ]
    )
    invoice_counts = {status.value: 0 for status in InvoiceStatus}
    for status, count in invoice_rows.all():
        key = status.value if hasattr(status, "value") else str(status)
        invoice_counts[key] = int(count)
    for status, count in invoice_counts.items():
        lines.append(prometheus_line("raijin_invoices_total", count, {"status": status}))

    confidence_avg = await db.scalar(
        select(func.avg(Invoice.ocr_confidence)).where(Invoice.ocr_confidence.is_not(None))
    )
    failed = invoice_counts[InvoiceStatus.FAILED.value]
    processed = invoice_counts[InvoiceStatus.READY_FOR_REVIEW.value] + invoice_counts[
        InvoiceStatus.CONFIRMED.value
    ]
    ocr_success_rate = processed / (processed + failed) if processed + failed else 0
    lines.extend(
        [
            "# HELP raijin_ocr_success_ratio OCR success ratio for processed invoices.",
            "# TYPE raijin_ocr_success_ratio gauge",
            prometheus_line("raijin_ocr_success_ratio", round(ocr_success_rate, 4)),
            "# HELP raijin_ocr_confidence_avg Average OCR confidence.",
            "# TYPE raijin_ocr_confidence_avg gauge",
            prometheus_line("raijin_ocr_confidence_avg", float(confidence_avg or 0)),
        ]
    )

    await _append_status_counts(
        db,
        lines,
        model=MyDataSubmission,
        enum=MyDataSubmissionStatus,
        metric="raijin_mydata_submissions_total",
        help_text="myDATA submissions grouped by status.",
    )
    await _append_status_counts(
        db,
        lines,
        model=ErpExport,
        enum=ErpExportStatus,
        metric="raijin_erp_exports_total",
        help_text="ERP exports grouped by status.",
    )

    return "\n".join(lines) + "\n"


async def _append_status_counts(
    db: AsyncSession,
    lines: list[str],
    *,
    model,
    enum,
    metric: str,
    help_text: str,
) -> None:
    rows = await db.execute(select(model.status, func.count(model.id)).group_by(model.status))
    counts = {status.value: 0 for status in enum}
    for status, count in rows.all():
        key = status.value if hasattr(status, "value") else str(status)
        counts[key] = int(count)

    lines.extend([f"# HELP {metric} {help_text}", f"# TYPE {metric} gauge"])
    for status, count in counts.items():
        lines.append(prometheus_line(metric, count, {"status": status}))


def monotonic_seconds() -> float:
    return time.perf_counter()


def release_from_env() -> str:
    return os.getenv("RELEASE_VERSION") or os.getenv("COMMIT_SHA") or "local"
