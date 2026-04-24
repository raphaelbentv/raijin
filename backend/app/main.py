from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import engine, get_db
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestLoggingMiddleware
from app.core.observability import init_sentry
from app.core.rate_limit import limiter
from app.core.security_headers import SecurityHeadersMiddleware
from app.routers import audit as audit_router
from app.routers import auth as auth_router
from app.routers import exports as exports_router
from app.routers import integrations as integrations_router
from app.routers import invoices as invoices_router
from app.routers import me as me_router
from app.routers import metrics as metrics_router
from app.routers import notifications as notifications_router
from app.routers import portal as portal_router
from app.routers import reports as reports_router
from app.routers import search as search_router
from app.routers import security as security_router
from app.routers import suppliers as suppliers_router
from app.routers import users as users_router
from app.services.health import build_full_health


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_sentry("raijin-backend")
    logger = get_logger("raijin.api")
    logger.info("api.starting", environment=get_settings().environment)
    yield
    await engine.dispose()
    logger.info("api.stopped")


settings = get_settings()

app = FastAPI(
    title="Raijin API",
    version="0.1.0",
    description="Invoice automation layer — MVP",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-request-id"],
)

app.include_router(auth_router.router)
app.include_router(invoices_router.router)
app.include_router(suppliers_router.router)
app.include_router(search_router.router)
app.include_router(security_router.router)
app.include_router(exports_router.router)
app.include_router(metrics_router.router)
app.include_router(notifications_router.router)
app.include_router(portal_router.router)
app.include_router(reports_router.router)
app.include_router(integrations_router.router)
app.include_router(integrations_router.public_router)
app.include_router(audit_router.router)
app.include_router(users_router.router)
app.include_router(me_router.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "raijin-backend"}


@app.get("/health/db")
async def health_db() -> dict[str, str]:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok", "dependency": "postgres"}


@app.get("/health/worker")
async def health_worker() -> dict[str, object]:
    from app.core.celery_client import get_celery

    celery = get_celery()
    try:
        result = celery.send_task("health.ping", expires=5)
        value = result.get(timeout=5)
        return {"status": "ok", "dependency": "worker", "result": value}
    except Exception as exc:
        return {"status": "degraded", "dependency": "worker", "error": str(exc)}


@app.get("/health/full")
async def health_full(
    response: Response,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict[str, object]:
    report = await build_full_health(db)
    if report["status"] == "down":
        response.status_code = 503
    return report


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Raijin API — see /docs"}
