from functools import lru_cache

from celery import Celery

from app.core.config import get_settings


@lru_cache
def get_celery() -> Celery:
    settings = get_settings()
    return Celery(
        "raijin-api",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )


def enqueue_invoice_ocr(invoice_id: str) -> None:
    """Fire-and-forget : demande au worker d'exécuter le pipeline OCR."""
    get_celery().send_task("invoice.process_ocr", args=[invoice_id])
