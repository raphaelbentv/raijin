from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.api.deps import CurrentUser, DbSession
from app.core.celery_client import get_celery
from app.core.config import get_settings
from app.core.permissions import RequireAdmin
from app.schemas.email_source import (
    AuthorizeResponse,
    EmailSourceOut,
    SyncStartedResponse,
)
from app.schemas.erp import ErpConnectorIn, ErpConnectorOut
from app.schemas.mydata import MyDataConnectorIn, MyDataConnectorOut
from app.services.email_source import (
    disconnect_source,
    get_source,
    list_sources,
    upsert_outlook_source,
)
from app.services.erp_config import (
    delete_connector as _erp_delete,
)
from app.services.erp_config import (
    get_connector as _erp_get,
)
from app.services.erp_config import (
    upsert_connector as _erp_upsert,
)
from app.services.mydata_config import (
    delete_connector as _mydata_delete,
)
from app.services.mydata_config import (
    get_connector as _mydata_get,
)
from app.services.mydata_config import (
    upsert_connector as _mydata_upsert,
)
from app.services.oauth_microsoft import (
    OAuthConfigurationError,
    OAuthExchangeError,
    OAuthStateError,
    build_authorization_url,
    decode_state,
    encode_state,
    exchange_code_for_tokens,
    extract_account_email,
)

router = APIRouter(prefix="/integrations", tags=["integrations"], dependencies=[RequireAdmin])
public_router = APIRouter(prefix="/integrations", tags=["integrations-public"])


@router.get("/email-sources", response_model=list[EmailSourceOut])
async def list_email_sources(db: DbSession, user: CurrentUser) -> list[EmailSourceOut]:
    items = await list_sources(db, tenant_id=user.tenant_id)
    return [EmailSourceOut.model_validate(i) for i in items]


@router.post("/outlook/authorize", response_model=AuthorizeResponse)
async def outlook_authorize(user: CurrentUser) -> AuthorizeResponse:
    try:
        state = encode_state(user_id=user.id, tenant_id=user.tenant_id)
        url = build_authorization_url(state)
    except OAuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AuthorizeResponse(authorize_url=url)


@public_router.get("/outlook/callback")
async def outlook_callback(
    db: DbSession,
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
    error_description: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    settings = get_settings()
    frontend = settings.frontend_url.rstrip("/")

    if error:
        return RedirectResponse(
            url=f"{frontend}/integrations?error={error}",
            status_code=302,
        )
    if not code or not state:
        return RedirectResponse(url=f"{frontend}/integrations?error=missing_params", status_code=302)

    try:
        payload = decode_state(state)
    except OAuthStateError:
        return RedirectResponse(url=f"{frontend}/integrations?error=invalid_state", status_code=302)

    try:
        result = exchange_code_for_tokens(code)
    except (OAuthConfigurationError, OAuthExchangeError) as exc:
        return RedirectResponse(
            url=f"{frontend}/integrations?error=exchange_failed&detail={exc}",
            status_code=302,
        )

    access_token = result.get("access_token")
    refresh_token = result.get("refresh_token")
    expires_in = result.get("expires_in")
    account_email = (
        extract_account_email(result.get("id_token_claims"))
        or "unknown@outlook"
    )

    if not access_token:
        return RedirectResponse(
            url=f"{frontend}/integrations?error=no_access_token",
            status_code=302,
        )

    await upsert_outlook_source(
        db,
        tenant_id=uuid.UUID(payload["tid"]),
        account_email=account_email,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )

    return RedirectResponse(url=f"{frontend}/integrations?connected=outlook", status_code=302)


# ─── Google (Gmail + Drive) ───────────────────────────────────────

from app.services import oauth_google as _google  # noqa: E402
from app.services.cloud_drive_source import (  # noqa: E402
    disconnect_gdrive_source,
    get_gdrive_source,
    list_gdrive_sources,
    upsert_gdrive_source,
)
from app.services.email_source import upsert_gmail_source  # noqa: E402


@router.post("/gmail/authorize", response_model=AuthorizeResponse)
async def gmail_authorize(user: CurrentUser) -> AuthorizeResponse:
    try:
        state = _google.encode_state(
            user_id=user.id, tenant_id=user.tenant_id, intent="gmail"
        )
        url = _google.build_authorization_url(state, intent="gmail")
    except _google.OAuthGoogleConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AuthorizeResponse(authorize_url=url)


@router.post("/gdrive/authorize", response_model=AuthorizeResponse)
async def gdrive_authorize(
    user: CurrentUser,
    folder_id: Annotated[str, Query(min_length=1, max_length=255)],
    folder_name: Annotated[str | None, Query()] = None,
) -> AuthorizeResponse:
    try:
        state_payload = _google.encode_state(
            user_id=user.id, tenant_id=user.tenant_id, intent=f"gdrive:{folder_id}"
        )
        url = _google.build_authorization_url(state_payload, intent="gdrive")
    except _google.OAuthGoogleConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AuthorizeResponse(authorize_url=url)


@public_router.get("/google/callback")
async def google_callback(
    db: DbSession,
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    settings = get_settings()
    frontend = settings.frontend_url.rstrip("/")

    if error:
        return RedirectResponse(
            url=f"{frontend}/integrations?error={error}", status_code=302
        )
    if not code or not state:
        return RedirectResponse(
            url=f"{frontend}/integrations?error=missing_params", status_code=302
        )

    try:
        payload = _google.decode_state(state)
    except _google.OAuthGoogleStateError:
        return RedirectResponse(
            url=f"{frontend}/integrations?error=invalid_state", status_code=302
        )

    try:
        tokens = _google.exchange_code_for_tokens(code)
    except (_google.OAuthGoogleConfigError, _google.OAuthGoogleExchangeError) as exc:
        return RedirectResponse(
            url=f"{frontend}/integrations?error=exchange_failed&detail={exc}",
            status_code=302,
        )

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    expires_in = tokens.get("expires_in")
    if not access_token:
        return RedirectResponse(
            url=f"{frontend}/integrations?error=no_access_token", status_code=302
        )

    userinfo = _google.fetch_userinfo(access_token)
    account_email = userinfo.get("email") or "unknown@google"
    tenant_id = uuid.UUID(payload["tid"])
    intent = str(payload.get("intent", "gmail"))

    if intent == "gmail":
        await upsert_gmail_source(
            db,
            tenant_id=tenant_id,
            account_email=account_email,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )
        return RedirectResponse(
            url=f"{frontend}/integrations?connected=gmail", status_code=302
        )

    if intent.startswith("gdrive:"):
        folder_id = intent.split(":", 1)[1]
        await upsert_gdrive_source(
            db,
            tenant_id=tenant_id,
            account_email=account_email,
            folder_id=folder_id,
            folder_name=None,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )
        return RedirectResponse(
            url=f"{frontend}/integrations?connected=gdrive", status_code=302
        )

    return RedirectResponse(
        url=f"{frontend}/integrations?error=unknown_intent", status_code=302
    )


@router.post("/email-sources/{source_id}/sync", response_model=SyncStartedResponse)
async def trigger_sync(
    source_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> SyncStartedResponse:
    source = await get_source(db, tenant_id=user.tenant_id, source_id=source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source_not_found")
    if source.provider.value == "gmail":
        get_celery().send_task("email.sync_gmail", args=[str(source.id)])
    else:
        get_celery().send_task("email.sync_outlook", args=[str(source.id)])
    return SyncStartedResponse(source_id=source.id)


@router.get("/gdrive-sources", response_model=list[dict])
async def list_gdrive(db: DbSession, user: CurrentUser) -> list[dict]:
    items = await list_gdrive_sources(db, tenant_id=user.tenant_id)
    return [
        {
            "id": str(s.id),
            "provider": s.provider.value,
            "folder_id": s.folder_id,
            "folder_name": s.folder_name,
            "account_email": s.account_email,
            "is_active": s.is_active,
            "last_sync_at": s.last_sync_at.isoformat() if s.last_sync_at else None,
            "last_error": s.last_error,
            "created_at": s.created_at.isoformat(),
        }
        for s in items
    ]


@router.post("/gdrive-sources/{source_id}/sync")
async def trigger_gdrive_sync(
    source_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> dict:
    source = await get_gdrive_source(db, tenant_id=user.tenant_id, source_id=source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source_not_found")
    get_celery().send_task("drive.sync_gdrive", args=[str(source.id)])
    return {"source_id": str(source.id), "status": "queued"}


@router.delete("/gdrive-sources/{source_id}", status_code=204)
async def delete_gdrive(
    source_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> None:
    source = await get_gdrive_source(db, tenant_id=user.tenant_id, source_id=source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source_not_found")
    await disconnect_gdrive_source(db, source=source)


@router.delete("/email-sources/{source_id}", status_code=204)
async def delete_email_source(
    source_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> None:
    source = await get_source(db, tenant_id=user.tenant_id, source_id=source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source_not_found")
    await disconnect_source(db, source=source)


# ─── myDATA ──────────────────────────────────────────────────────────


@router.get("/mydata", response_model=MyDataConnectorOut | None)
async def get_mydata(db: DbSession, user: CurrentUser) -> MyDataConnectorOut | None:
    connector = await _mydata_get(db, tenant_id=user.tenant_id)
    if connector is None:
        return None
    return MyDataConnectorOut.model_validate(connector)


@router.put("/mydata", response_model=MyDataConnectorOut)
async def put_mydata(
    body: MyDataConnectorIn, db: DbSession, user: CurrentUser
) -> MyDataConnectorOut:
    connector = await _mydata_upsert(
        db,
        tenant_id=user.tenant_id,
        kind=body.kind,
        base_url=body.base_url,
        credentials=body.credentials,
        issuer_vat_number=body.issuer_vat_number,
        auto_submit=body.auto_submit,
        is_active=body.is_active,
    )
    return MyDataConnectorOut.model_validate(connector)


@router.delete("/mydata", status_code=204)
async def delete_mydata(db: DbSession, user: CurrentUser) -> None:
    connector = await _mydata_get(db, tenant_id=user.tenant_id)
    if connector is None:
        return
    await _mydata_delete(db, connector=connector)


# ─── ERP ────────────────────────────────────────────────────────────


@router.get("/erp", response_model=ErpConnectorOut | None)
async def get_erp(db: DbSession, user: CurrentUser) -> ErpConnectorOut | None:
    connector = await _erp_get(db, tenant_id=user.tenant_id)
    if connector is None:
        return None
    return ErpConnectorOut.model_validate(connector)


@router.put("/erp", response_model=ErpConnectorOut)
async def put_erp(
    body: ErpConnectorIn, db: DbSession, user: CurrentUser
) -> ErpConnectorOut:
    connector = await _erp_upsert(
        db,
        tenant_id=user.tenant_id,
        kind=body.kind,
        base_url=body.base_url,
        credentials=body.credentials,
        config=body.config,
        auto_export=body.auto_export,
        is_active=body.is_active,
    )
    return ErpConnectorOut.model_validate(connector)


@router.delete("/erp", status_code=204)
async def delete_erp(db: DbSession, user: CurrentUser) -> None:
    connector = await _erp_get(db, tenant_id=user.tenant_id)
    if connector is None:
        return
    await _erp_delete(db, connector=connector)
