import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from raijin_shared.models.mydata import MyDataConnectorKind, MyDataSubmissionStatus


class MyDataConnectorIn(BaseModel):
    kind: MyDataConnectorKind
    base_url: str = Field(min_length=5, max_length=512)
    credentials: dict[str, Any]
    issuer_vat_number: str | None = Field(default=None, max_length=32)
    auto_submit: bool = False
    is_active: bool = True


class MyDataConnectorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: MyDataConnectorKind
    base_url: str
    issuer_vat_number: str | None
    auto_submit: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MyDataSubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    status: MyDataSubmissionStatus
    external_id: str | None
    aade_mark: str | None
    uid: str | None
    error_message: str | None
    retry_count: int
    submitted_at: datetime | None
    acknowledged_at: datetime | None
    created_at: datetime
    updated_at: datetime
