from __future__ import annotations

import uuid

from app.celery_app import celery_app
from app.core.database import session_scope
from app.core.logging import get_logger
from app.services.mydata import MyDataPermanentError, MyDataTransientError
from app.services.mydata_submission import (
    ConnectorMissingError,
    mark_submission_failed,
    submit_invoice_mydata,
)

logger = get_logger("raijin.tasks.mydata")


@celery_app.task(
    name="mydata.submit_invoice",
    bind=True,
    autoretry_for=(MyDataTransientError,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
    acks_late=True,
)
def submit_invoice_task(self, invoice_id: str) -> dict:
    invoice_uuid = uuid.UUID(invoice_id)
    attempt = self.request.retries + 1
    logger.info("task.mydata.submit", invoice_id=invoice_id, attempt=attempt)

    try:
        with session_scope() as session:
            submission = submit_invoice_mydata(session, invoice_uuid)
            return {
                "status": submission.status.value,
                "aade_mark": submission.aade_mark,
                "external_id": submission.external_id,
            }
    except ConnectorMissingError:
        logger.info("task.mydata.no_connector", invoice_id=invoice_id)
        return {"status": "skipped", "reason": "no_connector"}
    except MyDataPermanentError as exc:
        with session_scope() as session:
            mark_submission_failed(session, invoice_uuid, f"permanent: {exc}")
        logger.error("task.mydata.permanent", invoice_id=invoice_id, error=str(exc))
        return {"status": "failed", "reason": str(exc)}
    except MyDataTransientError:
        raise
    except Exception as exc:
        logger.exception("task.mydata.unexpected", invoice_id=invoice_id)
        with session_scope() as session:
            mark_submission_failed(session, invoice_uuid, f"unexpected: {exc}")
        return {"status": "failed", "reason": f"unexpected: {exc}"}
