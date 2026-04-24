"""SAML 2.0 SP-initiated SSO — wrapper autour de python3-saml."""
from __future__ import annotations

import secrets
from typing import Any
from urllib.parse import urlparse

from fastapi import Request
from onelogin.saml2.auth import OneLogin_Saml2_Auth  # type: ignore[import-untyped]
from onelogin.saml2.settings import OneLogin_Saml2_Settings  # type: ignore[import-untyped]
from raijin_shared.models.sprint_6_10 import SamlConfig
from raijin_shared.models.tenant import Tenant
from raijin_shared.models.user import User, UserRole
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password


class SamlNotConfiguredError(Exception):
    pass


class SamlValidationError(Exception):
    pass


def _strip_cert(cert: str) -> str:
    """Clean x509 cert : retire les headers/footers + whitespace, OneLogin veut juste le base64."""
    lines = [ln.strip() for ln in cert.splitlines() if ln.strip()]
    body = [ln for ln in lines if "CERTIFICATE" not in ln]
    return "".join(body)


def build_saml_settings(config: SamlConfig, tenant: Tenant) -> dict[str, Any]:
    settings = get_settings()
    sp_base = settings.backend_public_url.rstrip("/")
    if not config.sso_url or not config.entity_id or not config.certificate:
        raise SamlNotConfiguredError("saml_config_incomplete")
    return {
        "strict": True,
        "debug": not settings.is_production,
        "sp": {
            "entityId": f"{sp_base}/auth/saml/metadata/{tenant.slug}",
            "assertionConsumerService": {
                "url": f"{sp_base}/auth/saml/acs/{tenant.slug}",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            "x509cert": "",
            "privateKey": "",
        },
        "idp": {
            "entityId": config.entity_id,
            "singleSignOnService": {
                "url": config.sso_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": _strip_cert(config.certificate),
        },
        "security": {
            "authnRequestsSigned": False,
            "wantAssertionsSigned": True,
            "wantMessagesSigned": False,
            "signatureAlgorithm": "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
            "digestAlgorithm": "http://www.w3.org/2001/04/xmlenc#sha256",
        },
    }


async def prepare_request_data(request: Request) -> dict[str, Any]:
    parsed = urlparse(str(request.url))
    form = await request.form() if request.method == "POST" else None
    return {
        "https": "on" if parsed.scheme == "https" else "off",
        "http_host": request.headers.get("host", parsed.netloc),
        "server_port": str(parsed.port or (443 if parsed.scheme == "https" else 80)),
        "script_name": parsed.path,
        "get_data": dict(request.query_params),
        "post_data": dict(form) if form else {},
    }


async def init_saml_auth(
    request: Request, config: SamlConfig, tenant: Tenant
) -> OneLogin_Saml2_Auth:
    req_data = await prepare_request_data(request)
    settings_dict = build_saml_settings(config, tenant)
    return OneLogin_Saml2_Auth(req_data, settings_dict)


def generate_sp_metadata(config: SamlConfig, tenant: Tenant) -> tuple[str, list[str]]:
    settings_dict = build_saml_settings(config, tenant)
    saml_settings = OneLogin_Saml2_Settings(settings_dict, sp_validation_only=True)
    metadata = saml_settings.get_sp_metadata()
    errors = saml_settings.validate_metadata(metadata)
    return metadata, errors


async def get_saml_config_by_slug(
    session: AsyncSession, tenant_slug: str
) -> tuple[Tenant, SamlConfig]:
    tenant = await session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
    if tenant is None:
        raise SamlNotConfiguredError("tenant_not_found")
    config = await session.scalar(
        select(SamlConfig).where(SamlConfig.tenant_id == tenant.id)
    )
    if config is None or not config.is_enabled:
        raise SamlNotConfiguredError("saml_not_enabled_for_tenant")
    return tenant, config


async def provision_saml_user(
    session: AsyncSession, *, tenant: Tenant, email: str, full_name: str | None
) -> User:
    """JIT provisioning : retourne l'user existant ou le crée avec un mdp aléatoire."""
    normalized = email.strip().lower()
    existing = await session.scalar(
        select(User).where(User.tenant_id == tenant.id, User.email == normalized)
    )
    if existing is not None:
        return existing
    random_password = secrets.token_urlsafe(48)
    user = User(
        tenant_id=tenant.id,
        email=normalized,
        password_hash=hash_password(random_password),
        full_name=full_name,
        role=UserRole.USER,
        locale=tenant.default_locale,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def extract_saml_identity(auth: OneLogin_Saml2_Auth) -> tuple[str, str | None]:
    """Retourne (email, full_name) depuis les attributs SAML."""
    attrs = auth.get_attributes()
    name_id = auth.get_nameid()

    def first(*keys: str) -> str | None:
        for key in keys:
            values = attrs.get(key)
            if values:
                return values[0] if isinstance(values, list) else str(values)
        return None

    email = first(
        "email",
        "emailAddress",
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
        "urn:oid:0.9.2342.19200300.100.1.3",
    ) or name_id

    if not email:
        raise SamlValidationError("saml_assertion_missing_email")

    full_name = first(
        "displayName",
        "name",
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
        "urn:oid:2.16.840.1.113730.3.1.241",
    )
    if full_name is None:
        given = first(
            "givenName",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname",
        )
        surname = first(
            "sn",
            "surname",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname",
        )
        if given or surname:
            full_name = " ".join(part for part in (given, surname) if part)

    return email, full_name
