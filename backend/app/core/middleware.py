import time
import uuid
from collections.abc import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.observability import http_metrics


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        logger = structlog.get_logger("raijin.http")

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.exception("http.error", duration_ms=duration_ms)
            http_metrics.record(
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration_seconds=duration_ms / 1000,
            )
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        http_metrics.record(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_seconds=duration_ms / 1000,
        )
        response.headers["x-request-id"] = request_id
        logger.info(
            "http.request",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response
