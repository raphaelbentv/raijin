"""SAML 2.0 SP-initiated SSO endpoints."""
from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from app.api.deps import DbSession
from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token
from app.services.saml import (
    SamlNotConfiguredError,
    SamlValidationError,
    extract_saml_identity,
    generate_sp_metadata,
    get_saml_config_by_slug,
    init_saml_auth,
    provision_saml_user,
)

router = APIRouter(prefix="/auth/saml", tags=["auth-saml"])


@router.get("/login/{tenant_slug}")
async def saml_login(tenant_slug: str, request: Request, db: DbSession) -> RedirectResponse:
    try:
        tenant, config = await get_saml_config_by_slug(db, tenant_slug)
    except SamlNotConfiguredError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    auth = await init_saml_auth(request, config, tenant)
    sso_url = auth.login(return_to=None, stay=True)
    return RedirectResponse(url=sso_url, status_code=302)


@router.get("/metadata/{tenant_slug}")
async def saml_metadata(tenant_slug: str, db: DbSession) -> Response:
    try:
        tenant, config = await get_saml_config_by_slug(db, tenant_slug)
    except SamlNotConfiguredError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    metadata, errors = generate_sp_metadata(config, tenant)
    if errors:
        raise HTTPException(status_code=500, detail={"metadata_invalid": errors})
    return Response(content=metadata, media_type="application/xml")


@router.post("/acs/{tenant_slug}")
async def saml_acs(tenant_slug: str, request: Request, db: DbSession) -> RedirectResponse:
    try:
        tenant, config = await get_saml_config_by_slug(db, tenant_slug)
    except SamlNotConfiguredError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    auth = await init_saml_auth(request, config, tenant)
    auth.process_response()
    errors = auth.get_errors()
    if errors:
        reason = auth.get_last_error_reason() or ",".join(errors)
        raise HTTPException(status_code=400, detail=f"saml_error:{reason}")
    if not auth.is_authenticated():
        raise HTTPException(status_code=401, detail="saml_not_authenticated")

    try:
        email, full_name = extract_saml_identity(auth)
    except SamlValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = await provision_saml_user(
        db, tenant=tenant, email=email, full_name=full_name
    )

    access = create_access_token(
        user_id=user.id, tenant_id=user.tenant_id, role=user.role.value
    )
    refresh = create_refresh_token(
        user_id=user.id, tenant_id=user.tenant_id, role=user.role.value
    )

    settings = get_settings()
    query = urlencode({"access_token": access, "refresh_token": refresh})
    redirect_url = f"{settings.frontend_url.rstrip('/')}/auth/saml/complete?{query}"
    return RedirectResponse(url=redirect_url, status_code=302)
