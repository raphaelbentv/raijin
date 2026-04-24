from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from raijin_shared.models.invoice import Invoice
from raijin_shared.models.sprint_6_10 import (
    ApiKey,
    GdprDeletionRequest,
    SamlConfig,
    TenantIpRule,
    UserSession,
)
from raijin_shared.models.supplier import Supplier
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.permissions import RequireAdmin
from app.services.security_management import (
    backup_code,
    create_api_key,
    generate_totp_secret,
    hash_secret,
    totp_uri,
    verify_totp_code,
)

router = APIRouter(prefix="/security", tags=["security"])


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: list[str]
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] = Field(default_factory=lambda: ["invoices:read"])
    expires_at: datetime | None = None


class ApiKeyCreated(BaseModel):
    api_key: ApiKeyOut
    secret: str


class TotpSetupOut(BaseModel):
    secret: str
    otpauth_url: str
    backup_codes: list[str]


class TotpEnableIn(BaseModel):
    code: str = Field(min_length=6, max_length=16)


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ip_address: str | None
    user_agent: str | None
    last_seen_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class IpRuleIn(BaseModel):
    cidr: str


class IpRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cidr: str
    is_active: bool


class SamlConfigIn(BaseModel):
    entity_id: str | None = None
    sso_url: str | None = None
    certificate: str | None = None
    is_enabled: bool = False


class SamlConfigOut(SamlConfigIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class GdprDeletionRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requested_at: datetime
    scheduled_for: datetime
    status: str


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(db: DbSession, user: CurrentUser) -> list[ApiKeyOut]:
    keys = await db.scalars(
        select(ApiKey)
        .where(ApiKey.tenant_id == user.tenant_id, ApiKey.user_id == user.id)
        .order_by(ApiKey.created_at.desc())
    )
    return [ApiKeyOut.model_validate(key) for key in keys.all()]


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_key(body: ApiKeyCreate, db: DbSession, user: CurrentUser) -> ApiKeyCreated:
    key, secret = await create_api_key(
        db,
        user=user,
        name=body.name,
        scopes=body.scopes,
        expires_at=body.expires_at,
    )
    return ApiKeyCreated(api_key=ApiKeyOut.model_validate(key), secret=secret)


@router.post("/api-keys/{key_id}/revoke", status_code=204)
async def revoke_key(key_id: uuid.UUID, db: DbSession, user: CurrentUser) -> None:
    key = await db.scalar(
        select(ApiKey).where(
            ApiKey.tenant_id == user.tenant_id,
            ApiKey.user_id == user.id,
            ApiKey.id == key_id,
        )
    )
    if key is None:
        raise HTTPException(status_code=404, detail="api_key_not_found")
    key.revoked_at = datetime.now(UTC)
    await db.commit()


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(db: DbSession, user: CurrentUser) -> list[SessionOut]:
    sessions = await db.scalars(
        select(UserSession)
        .where(UserSession.tenant_id == user.tenant_id, UserSession.user_id == user.id)
        .order_by(UserSession.last_seen_at.desc().nullslast(), UserSession.created_at.desc())
        .limit(50)
    )
    return [SessionOut.model_validate(item) for item in sessions.all()]


@router.post("/sessions/{session_id}/revoke", status_code=204)
async def revoke_session(session_id: uuid.UUID, db: DbSession, user: CurrentUser) -> None:
    item = await db.scalar(
        select(UserSession).where(
            UserSession.tenant_id == user.tenant_id,
            UserSession.user_id == user.id,
            UserSession.id == session_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    item.revoked_at = datetime.now(UTC)
    await db.commit()


@router.post("/totp/setup", response_model=TotpSetupOut)
async def setup_totp(db: DbSession, user: CurrentUser) -> TotpSetupOut:
    secret = generate_totp_secret()
    codes = [backup_code() for _ in range(8)]
    user.totp_secret_encrypted = secret
    user.backup_codes = [hash_secret(code) for code in codes]
    user.totp_enabled = False
    await db.commit()
    return TotpSetupOut(
        secret=secret,
        otpauth_url=totp_uri(secret=secret, issuer="Raijin", account=user.email),
        backup_codes=codes,
    )


@router.post("/totp/enable", status_code=204)
async def enable_totp(body: TotpEnableIn, db: DbSession, user: CurrentUser) -> None:
    if not user.totp_secret_encrypted:
        raise HTTPException(status_code=400, detail="totp_not_setup")
    if not verify_totp_code(user.totp_secret_encrypted, body.code):
        raise HTTPException(status_code=400, detail="invalid_totp_code")
    user.totp_enabled = True
    await db.commit()


@router.post("/totp/disable", status_code=204)
async def disable_totp(db: DbSession, user: CurrentUser) -> None:
    user.totp_enabled = False
    user.totp_secret_encrypted = None
    user.backup_codes = None
    await db.commit()


@router.get("/ip-rules", response_model=list[IpRuleOut], dependencies=[RequireAdmin])
async def list_ip_rules(db: DbSession, user: CurrentUser) -> list[IpRuleOut]:
    rules = await db.scalars(
        select(TenantIpRule)
        .where(TenantIpRule.tenant_id == user.tenant_id)
        .order_by(TenantIpRule.created_at.desc())
    )
    return [IpRuleOut.model_validate(rule) for rule in rules.all()]


@router.post("/ip-rules", response_model=IpRuleOut, status_code=201, dependencies=[RequireAdmin])
async def create_ip_rule(body: IpRuleIn, db: DbSession, user: CurrentUser) -> IpRuleOut:
    rule = TenantIpRule(tenant_id=user.tenant_id, cidr=body.cidr)
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return IpRuleOut.model_validate(rule)


@router.get("/saml", response_model=SamlConfigOut | None, dependencies=[RequireAdmin])
async def get_saml_config(db: DbSession, user: CurrentUser):
    config = await db.scalar(select(SamlConfig).where(SamlConfig.tenant_id == user.tenant_id))
    return SamlConfigOut.model_validate(config) if config else None


@router.put("/saml", response_model=SamlConfigOut, dependencies=[RequireAdmin])
async def put_saml_config(body: SamlConfigIn, db: DbSession, user: CurrentUser) -> SamlConfigOut:
    config = await db.scalar(select(SamlConfig).where(SamlConfig.tenant_id == user.tenant_id))
    if config is None:
        config = SamlConfig(tenant_id=user.tenant_id)
        db.add(config)
    config.entity_id = body.entity_id
    config.sso_url = body.sso_url
    config.certificate = body.certificate
    config.is_enabled = body.is_enabled
    await db.commit()
    await db.refresh(config)
    return SamlConfigOut.model_validate(config)


@router.get("/gdpr/export")
async def gdpr_export(db: DbSession, user: CurrentUser) -> Response:
    invoices = await db.scalars(select(Invoice).where(Invoice.tenant_id == user.tenant_id))
    suppliers = await db.scalars(select(Supplier).where(Supplier.tenant_id == user.tenant_id))
    users = await db.scalars(select(UserSession).where(UserSession.tenant_id == user.tenant_id))

    payloads = {
        "profile.json": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "locale": user.locale,
        },
        "invoices.json": [
            {
                "id": str(invoice.id),
                "status": invoice.status.value,
                "invoice_number": invoice.invoice_number,
                "total_ttc": str(invoice.total_ttc) if invoice.total_ttc is not None else None,
                "created_at": invoice.created_at.isoformat(),
            }
            for invoice in invoices.all()
        ],
        "suppliers.json": [
            {
                "id": str(supplier.id),
                "name": supplier.name,
                "vat_number": supplier.vat_number,
                "country_code": supplier.country_code,
            }
            for supplier in suppliers.all()
        ],
        "sessions.json": [
            {
                "id": str(item.id),
                "ip_address": item.ip_address,
                "user_agent": item.user_agent,
                "last_seen_at": item.last_seen_at.isoformat() if item.last_seen_at else None,
            }
            for item in users.all()
        ],
    }
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for filename, payload in payloads.items():
            archive.writestr(filename, json.dumps(payload, ensure_ascii=False, indent=2))
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="raijin-gdpr-export.zip"'},
    )


@router.post(
    "/gdpr/delete-request",
    response_model=GdprDeletionRequestOut,
    status_code=status.HTTP_201_CREATED,
)
async def request_gdpr_deletion(db: DbSession, user: CurrentUser) -> GdprDeletionRequestOut:
    existing = await db.scalar(
        select(GdprDeletionRequest).where(
            GdprDeletionRequest.tenant_id == user.tenant_id,
            GdprDeletionRequest.user_id == user.id,
            GdprDeletionRequest.status == "pending",
        )
    )
    if existing is not None:
        return GdprDeletionRequestOut.model_validate(existing)
    now = datetime.now(UTC)
    item = GdprDeletionRequest(
        tenant_id=user.tenant_id,
        user_id=user.id,
        requested_at=now,
        scheduled_for=now + timedelta(days=30),
        status="pending",
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return GdprDeletionRequestOut.model_validate(item)
