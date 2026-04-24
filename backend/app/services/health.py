from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

import httpx
import redis.asyncio as redis
from raijin_shared.models.erp import ErpConnector
from raijin_shared.models.mydata import MyDataConnector
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_client import get_celery
from app.core.config import get_settings
from app.core.storage import _s3_client

DependencyStatus = dict[str, Any]


@dataclass(frozen=True)
class Probe:
    name: str
    critical: bool
    check: Callable[[], Awaitable[DependencyStatus]]


def rollup_status(dependencies: list[DependencyStatus]) -> str:
    critical_down = any(
        dep["critical"] and dep["status"] in {"down", "degraded"} for dep in dependencies
    )
    if critical_down:
        return "down"
    if any(dep["status"] in {"down", "degraded"} for dep in dependencies):
        return "degraded"
    return "ok"


async def build_full_health(db: AsyncSession) -> dict[str, Any]:
    settings = get_settings()
    db_probes = [
        Probe("postgres", True, lambda: _check_postgres(db)),
        Probe("mydata_connectors", False, lambda: _check_connector_reachability(db, MyDataConnector)),
        Probe("erp_connectors", False, lambda: _check_connector_reachability(db, ErpConnector)),
    ]
    async_probes = [
        Probe("redis", True, _check_redis),
        Probe("object_storage", True, _check_object_storage),
        Probe("worker", True, _check_worker),
        Probe("azure_document_intelligence", settings.is_production, _check_azure_di),
    ]

    db_dependencies = [await _run_probe(probe) for probe in db_probes]
    async_dependencies = await asyncio.gather(*[_run_probe(probe) for probe in async_probes])
    dependencies = db_dependencies + async_dependencies
    return {
        "status": rollup_status(dependencies),
        "service": "raijin-backend",
        "environment": settings.environment,
        "release": settings.release_version,
        "dependencies": dependencies,
    }


async def _run_probe(probe: Probe) -> DependencyStatus:
    start = perf_counter()
    try:
        result = await probe.check()
    except Exception as exc:
        result = {"status": "down", "error": str(exc)}

    result.setdefault("status", "ok")
    result["name"] = probe.name
    result["critical"] = probe.critical
    result["latency_ms"] = round((perf_counter() - start) * 1000, 2)
    return result


async def _check_postgres(db: AsyncSession) -> DependencyStatus:
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}


async def _check_redis() -> DependencyStatus:
    settings = get_settings()
    client = redis.from_url(settings.redis_url)
    try:
        pong = await client.ping()
        return {"status": "ok" if pong else "down"}
    finally:
        await client.aclose()


async def _check_object_storage() -> DependencyStatus:
    settings = get_settings()
    client = _s3_client()
    await asyncio.to_thread(client.head_bucket, Bucket=settings.s3_bucket_invoices)
    return {"status": "ok", "bucket": settings.s3_bucket_invoices}


async def _check_worker() -> DependencyStatus:
    celery = get_celery()

    def _ping() -> str:
        result = celery.send_task("health.ping", expires=5)
        return str(result.get(timeout=5))

    value = await asyncio.to_thread(_ping)
    return {"status": "ok" if value == "pong" else "degraded", "result": value}


async def _check_azure_di() -> DependencyStatus:
    settings = get_settings()
    if not settings.azure_di_endpoint or not settings.azure_di_key:
        return {
            "status": "down" if settings.is_production else "skipped",
            "reason": "azure_di_not_configured",
        }

    endpoint = settings.azure_di_endpoint.rstrip("/")
    url = (
        f"{endpoint}/documentintelligence/documentModels/{settings.azure_di_model}"
        "?api-version=2024-11-30"
    )
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(url, headers={"Ocp-Apim-Subscription-Key": settings.azure_di_key})

    if response.status_code < 400:
        return {"status": "ok", "status_code": response.status_code}
    return {
        "status": "down" if response.status_code in {401, 403} else "degraded",
        "status_code": response.status_code,
    }


async def _check_connector_reachability(db: AsyncSession, model) -> DependencyStatus:
    rows = await db.execute(select(model.id, model.base_url).where(model.is_active.is_(True)))
    connectors = rows.all()
    if not connectors:
        return {"status": "skipped", "reason": "no_active_connector"}

    results = await asyncio.gather(
        *[_check_http_endpoint(str(connector_id), base_url) for connector_id, base_url in connectors]
    )
    has_down = any(result["status"] == "down" for result in results)
    has_degraded = any(result["status"] == "degraded" for result in results)
    return {
        "status": "down" if has_down else "degraded" if has_degraded else "ok",
        "connectors": results,
    }


async def _check_http_endpoint(connector_id: str, base_url: str) -> DependencyStatus:
    url = base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
        try:
            response = await client.head(url)
            if response.status_code == 405:
                response = await client.get(url)
        except httpx.RequestError as exc:
            return {"id": connector_id, "status": "down", "error": str(exc)}

    # Auth-required and not-found responses still prove DNS/TLS/routing reachability.
    if response.status_code < 500:
        return {"id": connector_id, "status": "ok", "status_code": response.status_code}
    return {"id": connector_id, "status": "degraded", "status_code": response.status_code}
