from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

from jose import JWTError, jwt
from msal import ConfidentialClientApplication

from app.core.config import get_settings


class OAuthConfigurationError(RuntimeError):
    pass


class OAuthStateError(ValueError):
    pass


class OAuthExchangeError(RuntimeError):
    pass


@lru_cache
def _msal_app() -> ConfidentialClientApplication:
    settings = get_settings()
    if not settings.microsoft_client_id or not settings.microsoft_client_secret:
        raise OAuthConfigurationError("microsoft_not_configured")
    authority = f"https://login.microsoftonline.com/{settings.microsoft_tenant}"
    return ConfidentialClientApplication(
        client_id=settings.microsoft_client_id,
        client_credential=settings.microsoft_client_secret,
        authority=authority,
    )


def _scopes() -> list[str]:
    settings = get_settings()
    return [s for s in settings.microsoft_scopes.split() if s]


def encode_state(*, user_id: uuid.UUID, tenant_id: uuid.UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "uid": str(user_id),
        "tid": str(tenant_id),
        "nonce": secrets.token_urlsafe(16),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "kind": "oauth_state",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_state(state: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise OAuthStateError("invalid_state") from exc
    if payload.get("kind") != "oauth_state":
        raise OAuthStateError("wrong_state_kind")
    return payload


def build_authorization_url(state: str) -> str:
    settings = get_settings()
    return _msal_app().get_authorization_request_url(
        scopes=_scopes(),
        redirect_uri=settings.microsoft_redirect_uri,
        state=state,
        prompt="select_account",
    )


def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    settings = get_settings()
    result = _msal_app().acquire_token_by_authorization_code(
        code=code,
        scopes=_scopes(),
        redirect_uri=settings.microsoft_redirect_uri,
    )
    if "error" in result:
        raise OAuthExchangeError(
            f"{result.get('error')}: {result.get('error_description', 'unknown')}"
        )
    return result


def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    """Échange un refresh_token contre un nouveau access_token."""
    result = _msal_app().acquire_token_by_refresh_token(
        refresh_token=refresh_token,
        scopes=_scopes(),
    )
    if "error" in result:
        raise OAuthExchangeError(
            f"{result.get('error')}: {result.get('error_description', 'unknown')}"
        )
    return result


def extract_account_email(id_token_claims: dict[str, Any] | None) -> str | None:
    if not id_token_claims:
        return None
    return (
        id_token_claims.get("preferred_username")
        or id_token_claims.get("email")
        or id_token_claims.get("upn")
    )
