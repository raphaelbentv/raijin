import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr
from raijin_shared.models.email_source import EmailProvider


class EmailSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: EmailProvider
    account_email: EmailStr
    folder: str
    is_active: bool
    last_sync_at: datetime | None
    last_error: str | None
    created_at: datetime


class AuthorizeResponse(BaseModel):
    authorize_url: str


class SyncStartedResponse(BaseModel):
    source_id: uuid.UUID
    status: str = "queued"
