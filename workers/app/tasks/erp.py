from __future__ import annotations

import uuid

from app.celery_app import celery_app
from app.core.database import session_scope
from app.core.logging import get_logger
from app.services.erp import ErpPermanentError, ErpTransientError
from app.services.erp_export import (
    ConnectorMissingError,
    export_invoice_to_erp,
    mark_export_failed,
)

logger = get_logger("raijin.tasks.erp")


@celery_app.task(
    name="erp.export_invoice",
    bind=True,
    autoretry_for=(ErpTransientError,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
    acks_late=True,
)
def export_invoice_task(self, invoice_id: str) -> dict:
    invoice_uuid = uuid.UUID(invoice_id)
    logger.info(
        "task.erp.export", invoice_id=invoice_id, attempt=self.request.retries + 1
    )

    try:
        with session_scope() as session:
            export = export_invoice_to_erp(session, invoice_uuid)
            return {
                "status": export.status.value,
                "external_id": export.external_id,
            }
    except ConnectorMissingError:
        return {"status": "skipped", "reason": "no_connector"}
    except ErpPermanentError as exc:
        with session_scope() as session:
            mark_export_failed(session, invoice_uuid, f"permanent: {exc}")
        return {"status": "failed", "reason": str(exc)}
    except ErpTransientError:
        raise
    except Exception as exc:
        logger.exception("task.erp.unexpected", invoice_id=invoice_id)
        with session_scope() as session:
            mark_export_failed(session, invoice_uuid, f"unexpected: {exc}")
        return {"status": "failed", "reason": f"unexpected: {exc}"}
