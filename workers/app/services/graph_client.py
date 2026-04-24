"""Minimal Microsoft Graph client for Mail API.

Handles token refresh transparently and returns plain dict payloads.
"""
from __future__ import annotations

import base64
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import requests
from msal import ConfidentialClientApplication
from raijin_shared.models.email_source import EmailSource
from raijin_shared.security import decrypt, encrypt

from app.core.config import get_settings

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SUPPORTED_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}


class GraphError(RuntimeError):
    pass


class GraphAuthError(GraphError):
    pass


def _msal_app() -> ConfidentialClientApplication:
    settings = get_settings()
    if not settings.microsoft_client_id or not settings.microsoft_client_secret:
        raise GraphAuthError("microsoft_not_configured")
    authority = f"https://login.microsoftonline.com/{settings.microsoft_tenant}"
    return ConfidentialClientApplication(
        client_id=settings.microsoft_client_id,
        client_credential=settings.microsoft_client_secret,
        authority=authority,
    )


def _scopes() -> list[str]:
    settings = get_settings()
    return [s for s in settings.microsoft_scopes.split() if s and s != "offline_access"]


def _refresh_if_needed(source: EmailSource, session) -> str:
    """Renouvelle le token d'accès si expiré. Persiste le nouveau sur source."""
    now = datetime.now(UTC)
    expires = source.token_expires_at
    if expires and expires > now + timedelta(minutes=1):
        return decrypt(source.access_token_encrypted)

    refresh = (
        decrypt(source.refresh_token_encrypted) if source.refresh_token_encrypted else None
    )
    if not refresh:
        raise GraphAuthError("no_refresh_token")

    result = _msal_app().acquire_token_by_refresh_token(refresh, scopes=_scopes())
    if "error" in result:
        raise GraphAuthError(
            f"{result.get('error')}: {result.get('error_description', '?')}"
        )

    access = result["access_token"]
    new_refresh = result.get("refresh_token")
    expires_in = int(result.get("expires_in", 3600))

    source.access_token_encrypted = encrypt(access)
    if new_refresh:
        source.refresh_token_encrypted = encrypt(new_refresh)
    source.token_expires_at = now + timedelta(seconds=expires_in - 60)
    session.add(source)
    session.flush()
    return access


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def list_messages_with_attachments(
    session, source: EmailSource, *, since: datetime | None
) -> Iterator[dict[str, Any]]:
    """Itère les messages ayant des pièces jointes, plus récents que ``since``."""
    token = _refresh_if_needed(source, session)

    params: dict[str, str] = {
        "$filter": "hasAttachments eq true",
        "$orderby": "receivedDateTime asc",
        "$top": "50",
        "$select": "id,subject,from,receivedDateTime,hasAttachments",
    }
    if since:
        params["$filter"] += f" and receivedDateTime gt {since.isoformat().replace('+00:00', 'Z')}"

    folder = source.folder or "Inbox"
    url = f"{GRAPH_BASE}/me/mailFolders/{folder}/messages"

    while url:
        resp = requests.get(url, headers=_auth_header(token), params=params, timeout=30)
        if resp.status_code in (401, 403):
            raise GraphAuthError(f"auth_failed: {resp.text[:200]}")
        if not resp.ok:
            raise GraphError(f"graph_error[{resp.status_code}]: {resp.text[:200]}")
        data = resp.json()
        yield from data.get("value", [])
        url = data.get("@odata.nextLink")
        params = {}  # déjà encodés dans next link


def list_message_attachments(
    session, source: EmailSource, message_id: str
) -> list[dict[str, Any]]:
    token = _refresh_if_needed(source, session)
    url = f"{GRAPH_BASE}/me/messages/{message_id}/attachments"
    resp = requests.get(url, headers=_auth_header(token), timeout=30)
    if not resp.ok:
        raise GraphError(f"attachments_list[{resp.status_code}]: {resp.text[:200]}")
    return resp.json().get("value", [])


def download_attachment_bytes(attachment: dict[str, Any]) -> bytes:
    content_b64 = attachment.get("contentBytes")
    if not content_b64:
        raise GraphError("attachment_missing_contentBytes")
    return base64.b64decode(content_b64)


def is_supported_attachment(attachment: dict[str, Any]) -> bool:
    if attachment.get("@odata.type") != "#microsoft.graph.fileAttachment":
        return False
    mime = (attachment.get("contentType") or "").lower().split(";")[0].strip()
    return mime in SUPPORTED_MIME


def attachment_mime(attachment: dict[str, Any]) -> str:
    mime = (attachment.get("contentType") or "").lower().split(";")[0].strip()
    return mime or "application/octet-stream"
