from __future__ import annotations

import contextlib
import uuid

from celery import states
from celery.exceptions import MaxRetriesExceededError, Retry
from sqlalchemy.exc import SQLAlchemyError

from app.celery_app import celery_app
from app.core.config import get_settings
from app.core.database import session_scope
from app.core.logging import get_logger
from app.services.azure_di import AzureDiPermanentError, AzureDiTransientError
from app.services.invoice_processor import (
    InvoiceNotFoundError,
    InvoiceNotProcessableError,
    mark_invoice_failed,
    process_invoice_ocr,
)

logger = get_logger("raijin.tasks")


@celery_app.task(
    name="invoice.process_ocr",
    bind=True,
    autoretry_for=(AzureDiTransientError,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=None,
    acks_late=True,
)
def process_ocr_task(self, invoice_id: str) -> dict:
    settings = get_settings()
    invoice_uuid = uuid.UUID(invoice_id)

    with contextlib.suppress(Exception):
        self.max_retries = settings.ocr_max_retries  # type: ignore[attr-defined]

    logger.info(
        "task.invoice.process_ocr",
        invoice_id=invoice_id,
        attempt=self.request.retries + 1,
    )

    try:
        with session_scope() as session:
            invoice = process_invoice_ocr(session, invoice_uuid)
            return {
                "invoice_id": str(invoice.id),
                "status": invoice.status.value,
                "confidence": float(invoice.ocr_confidence) if invoice.ocr_confidence else None,
                "issues": len(invoice.validation_errors["issues"]) if invoice.validation_errors else 0,
            }
    except InvoiceNotFoundError as exc:
        logger.error("task.invoice_not_found", invoice_id=invoice_id)
        return {"status": states.FAILURE, "reason": f"invoice_not_found: {exc}"}
    except InvoiceNotProcessableError as exc:
        logger.warning("task.invoice_not_processable", invoice_id=invoice_id, reason=str(exc))
        return {"status": states.FAILURE, "reason": str(exc)}
    except AzureDiPermanentError as exc:
        with session_scope() as session:
            mark_invoice_failed(session, invoice_uuid, f"azure_di_permanent: {exc}")
        return {"status": states.FAILURE, "reason": f"azure_di_permanent: {exc}"}
    except AzureDiTransientError:
        raise
    except Retry:
        raise
    except MaxRetriesExceededError as exc:
        with session_scope() as session:
            mark_invoice_failed(session, invoice_uuid, f"max_retries_exceeded: {exc}")
        return {"status": states.FAILURE, "reason": f"max_retries_exceeded: {exc}"}
    except SQLAlchemyError as exc:
        logger.exception("task.db_error", invoice_id=invoice_id)
        raise self.retry(exc=exc, countdown=30, max_retries=3) from exc
    except Exception as exc:
        logger.exception("task.unexpected", invoice_id=invoice_id)
        with session_scope() as session:
            mark_invoice_failed(session, invoice_uuid, f"unexpected: {exc}")
        return {"status": states.FAILURE, "reason": f"unexpected: {exc}"}
