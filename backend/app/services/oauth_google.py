"""OAuth Google (Gmail + Drive, scopes combinés possibles)."""
from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from jose import JWTError, jwt

from app.core.config import get_settings


class OAuthGoogleError(RuntimeError):
    pass


class OAuthGoogleConfigError(OAuthGoogleError):
    pass


class OAuthGoogleStateError(ValueError):
    pass


class OAuthGoogleExchangeError(OAuthGoogleError):
    pass


AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def _settings():
    s = get_settings()
    if not s.google_client_id or not s.google_client_secret:
        raise OAuthGoogleConfigError("google_not_configured")
    return s


def encode_state(
    *, user_id: uuid.UUID, tenant_id: uuid.UUID, intent: str = "gmail"
) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "uid": str(user_id),
        "tid": str(tenant_id),
        "intent": intent,
        "nonce": secrets.token_urlsafe(16),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "kind": "oauth_google_state",
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_state(state: str) -> dict[str, Any]:
    s = get_settings()
    try:
        payload = jwt.decode(state, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except JWTError as exc:
        raise OAuthGoogleStateError("invalid_state") from exc
    if payload.get("kind") != "oauth_google_state":
        raise OAuthGoogleStateError("wrong_state_kind")
    return payload


def _scopes(intent: str) -> str:
    s = get_settings()
    if intent == "gmail":
        return "https://www.googleapis.com/auth/gmail.readonly openid email"
    if intent == "gdrive":
        return "https://www.googleapis.com/auth/drive.readonly openid email"
    if intent == "all":
        return s.google_scopes
    return "openid email"


def build_authorization_url(state: str, intent: str = "gmail") -> str:
    s = _settings()
    from urllib.parse import urlencode

    params = {
        "client_id": s.google_client_id,
        "redirect_uri": s.google_redirect_uri,
        "response_type": "code",
        "scope": _scopes(intent),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    s = _settings()
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": s.google_client_id,
                "client_secret": s.google_client_secret,
                "redirect_uri": s.google_redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
    if resp.status_code >= 400:
        raise OAuthGoogleExchangeError(f"{resp.status_code}: {resp.text[:400]}")
    return resp.json()


def fetch_userinfo(access_token: str) -> dict[str, Any]:
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(
            USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
    if resp.status_code >= 400:
        raise OAuthGoogleExchangeError(f"userinfo {resp.status_code}: {resp.text[:400]}")
    return resp.json()


def granted_scopes(token_payload: dict[str, Any]) -> set[str]:
    raw = token_payload.get("scope", "")
    return {s for s in raw.split() if s}
