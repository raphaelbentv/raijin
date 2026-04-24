"""Smoke-test des connecteurs externes.

Usage en staging / prod avant GoLive :
    docker compose exec backend python -m app.scripts.smoke_connectors

Le script ne modifie rien. Il ping chaque service configuré et reporte :
    ✅ ok · ⚠️ skipped (non configuré) · ❌ fail (avec erreur)

Sortie code 0 si pas d'erreur, 1 sinon (pour CI / prod-ready gate).
"""
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

import httpx
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from raijin_shared.models.erp import ErpConnector
from raijin_shared.models.mydata import MyDataConnector
from sqlalchemy import select, text

from app.core.celery_client import get_celery
from app.core.config import get_settings
from app.core.database import SessionLocal, engine


@dataclass
class Check:
    name: str
    status: str  # "ok" | "skipped" | "fail"
    detail: str = ""

    def render(self) -> str:
        icon = {"ok": "✅", "skipped": "⚠️", "fail": "❌"}[self.status]
        suffix = f" · {self.detail}" if self.detail else ""
        return f"  {icon}  {self.name:<28} {self.status}{suffix}"


def check_settings() -> Check:
    try:
        s = get_settings()
        return Check("config", "ok", f"env={s.environment}")
    except Exception as exc:
        return Check("config", "fail", str(exc)[:100])


async def check_postgres() -> Check:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return Check("postgres", "ok")
    except Exception as exc:
        return Check("postgres", "fail", str(exc)[:100])


def check_redis_celery() -> Check:
    try:
        result = get_celery().send_task("health.ping", expires=3)
        value = result.get(timeout=5)
        return Check("redis + celery worker", "ok", f"pong={value}")
    except Exception as exc:
        return Check("redis + celery worker", "fail", str(exc)[:100])


async def check_s3() -> Check:
    s = get_settings()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # HEAD sur l'endpoint suffit pour valider réseau+DNS
            resp = await client.head(s.s3_endpoint_url, follow_redirects=True)
        return Check(
            "s3 / minio",
            "ok",
            f"{s.s3_endpoint_url} → {resp.status_code}",
        )
    except Exception as exc:
        return Check("s3 / minio", "fail", str(exc)[:100])


def check_azure_di() -> Check:
    s = get_settings()
    if not s.azure_di_endpoint or not s.azure_di_key:
        return Check("azure document intelligence", "skipped", "non configuré")
    try:
        client = DocumentIntelligenceClient(
            endpoint=s.azure_di_endpoint, credential=AzureKeyCredential(s.azure_di_key)
        )
        # liste les modèles — requête légère qui confirme les creds
        models = list(client.list_models())[:1]
        return Check(
            "azure document intelligence",
            "ok",
            f"endpoint reachable, {len(models)}+ model(s)",
        )
    except Exception as exc:
        return Check("azure document intelligence", "fail", str(exc)[:100])


async def check_microsoft_oauth() -> Check:
    s = get_settings()
    if not s.microsoft_client_id or not s.microsoft_client_secret:
        return Check("microsoft graph oauth", "skipped", "non configuré")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"https://login.microsoftonline.com/{s.microsoft_tenant}/v2.0/.well-known/openid-configuration"
            )
        if resp.status_code == 200:
            return Check("microsoft graph oauth", "ok", f"tenant={s.microsoft_tenant}")
        return Check("microsoft graph oauth", "fail", f"status={resp.status_code}")
    except Exception as exc:
        return Check("microsoft graph oauth", "fail", str(exc)[:100])


async def check_google_oauth() -> Check:
    s = get_settings()
    if not s.google_client_id or not s.google_client_secret:
        return Check("google oauth", "skipped", "non configuré")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://accounts.google.com/.well-known/openid-configuration"
            )
        return Check("google oauth", "ok" if resp.status_code == 200 else "fail")
    except Exception as exc:
        return Check("google oauth", "fail", str(exc)[:100])


async def check_mydata_connectors() -> list[Check]:
    async with SessionLocal() as session:
        rows = (
            await session.scalars(
                select(MyDataConnector).where(MyDataConnector.is_active.is_(True))
            )
        ).all()
    if not rows:
        return [Check("mydata connectors", "skipped", "aucun configuré")]

    checks: list[Check] = []
    for row in rows:
        name = f"mydata · {row.kind.value}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.head(row.base_url, follow_redirects=True)
            ok = 200 <= resp.status_code < 500
            checks.append(
                Check(
                    name,
                    "ok" if ok else "fail",
                    f"{row.base_url} → {resp.status_code}",
                )
            )
        except Exception as exc:
            checks.append(Check(name, "fail", str(exc)[:100]))
    return checks


async def check_erp_connectors() -> list[Check]:
    async with SessionLocal() as session:
        rows = (
            await session.scalars(
                select(ErpConnector).where(ErpConnector.is_active.is_(True))
            )
        ).all()
    if not rows:
        return [Check("erp connectors", "skipped", "aucun configuré")]

    checks: list[Check] = []
    for row in rows:
        name = f"erp · {row.kind.value}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.head(row.base_url, follow_redirects=True)
            ok = 200 <= resp.status_code < 500
            checks.append(
                Check(
                    name,
                    "ok" if ok else "fail",
                    f"{row.base_url} → {resp.status_code}",
                )
            )
        except Exception as exc:
            checks.append(Check(name, "fail", str(exc)[:100]))
    return checks


async def main() -> int:
    print("🔌 Raijin — smoke test connecteurs\n")

    results: list[Check] = []
    results.append(check_settings())
    results.append(await check_postgres())
    results.append(check_redis_celery())
    results.append(await check_s3())
    results.append(check_azure_di())
    results.append(await check_microsoft_oauth())
    results.append(await check_google_oauth())
    results.extend(await check_mydata_connectors())
    results.extend(await check_erp_connectors())

    print("\n".join(c.render() for c in results))

    failures = [c for c in results if c.status == "fail"]
    print()
    if failures:
        print(f"❌ {len(failures)} échec(s) sur {len(results)} checks")
        return 1
    print(f"✅ tous les checks configurés passent ({len(results)} total)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
