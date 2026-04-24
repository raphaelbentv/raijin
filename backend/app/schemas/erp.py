import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from raijin_shared.models.erp import ErpConnectorKind, ErpExportStatus


class ErpConnectorIn(BaseModel):
    kind: ErpConnectorKind
    base_url: str = Field(min_length=5, max_length=512)
    credentials: dict[str, Any]
    config: dict[str, Any] | None = None
    auto_export: bool = False
    is_active: bool = True


class ErpConnectorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: ErpConnectorKind
    base_url: str
    auto_export: bool
    is_active: bool
    config: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class ErpExportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    status: ErpExportStatus
    external_id: str | None
    error_message: str | None
    retry_count: int
    submitted_at: datetime | None
    acknowledged_at: datetime | None
    created_at: datetime
    updated_at: datetime
