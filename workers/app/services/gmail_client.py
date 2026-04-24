"""Minimal Gmail client pour ingérer les pièces jointes."""
from __future__ import annotations

import base64
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import requests
from raijin_shared.models.email_source import EmailSource
from raijin_shared.security import decrypt, encrypt

from app.core.config import get_settings

GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
TOKEN_URL = "https://oauth2.googleapis.com/token"

SUPPORTED_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}


class GmailError(RuntimeError):
    pass


class GmailAuthError(GmailError):
    pass


def _refresh_if_needed(source: EmailSource, session) -> str:
    now = datetime.now(UTC)
    if source.token_expires_at and source.token_expires_at > now + timedelta(minutes=1):
        return decrypt(source.access_token_encrypted)

    refresh = (
        decrypt(source.refresh_token_encrypted) if source.refresh_token_encrypted else None
    )
    if not refresh:
        raise GmailAuthError("no_refresh_token")

    s = get_settings()
    if not s.google_client_id or not s.google_client_secret:
        raise GmailAuthError("google_not_configured")

    try:
        resp = requests.post(
            TOKEN_URL,
            data={
                "refresh_token": refresh,
                "client_id": s.google_client_id,
                "client_secret": s.google_client_secret,
                "grant_type": "refresh_token",
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        raise GmailError(f"refresh_network: {exc}") from exc

    if resp.status_code >= 400:
        raise GmailAuthError(f"refresh {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    access = data["access_token"]
    expires_in = int(data.get("expires_in", 3600))

    source.access_token_encrypted = encrypt(access)
    source.token_expires_at = now + timedelta(seconds=expires_in - 60)
    session.add(source)
    session.flush()
    return access


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def list_messages_with_attachments(
    session, source: EmailSource, *, since: datetime | None
) -> Iterator[dict[str, Any]]:
    token = _refresh_if_needed(source, session)

    query = "has:attachment"
    if since:
        epoch = int(since.timestamp())
        query += f" after:{epoch}"

    url = f"{GMAIL_BASE}/messages"
    page_token: str | None = None
    while True:
        params: dict[str, str] = {"q": query, "maxResults": "50"}
        if page_token:
            params["pageToken"] = page_token
        resp = requests.get(url, headers=_headers(token), params=params, timeout=30)
        if resp.status_code in (401, 403):
            raise GmailAuthError(f"auth_failed: {resp.text[:200]}")
        if not resp.ok:
            raise GmailError(f"gmail_list[{resp.status_code}]: {resp.text[:200]}")
        data = resp.json()
        yield from data.get("messages", [])
        page_token = data.get("nextPageToken")
        if not page_token:
            break


def get_message(session, source: EmailSource, message_id: str) -> dict[str, Any]:
    token = _refresh_if_needed(source, session)
    url = f"{GMAIL_BASE}/messages/{message_id}"
    resp = requests.get(
        url, headers=_headers(token), params={"format": "full"}, timeout=30
    )
    if not resp.ok:
        raise GmailError(f"gmail_get[{resp.status_code}]: {resp.text[:200]}")
    return resp.json()


def iter_attachments(message: dict[str, Any]) -> Iterator[tuple[str, str, str]]:
    """Yield (part_id, filename, mime_type) pour chaque PJ supportée."""

    def walk(parts: list[dict[str, Any]]):
        for part in parts:
            filename = part.get("filename") or ""
            mime = (part.get("mimeType") or "").lower()
            body = part.get("body") or {}
            if filename and mime in SUPPORTED_MIME and body.get("attachmentId"):
                yield body["attachmentId"], filename, mime
            sub_parts = part.get("parts")
            if sub_parts:
                yield from walk(sub_parts)

    payload = message.get("payload") or {}
    parts = payload.get("parts") or []
    yield from walk(parts)


def download_attachment(
    session, source: EmailSource, message_id: str, attachment_id: str
) -> bytes:
    token = _refresh_if_needed(source, session)
    url = f"{GMAIL_BASE}/messages/{message_id}/attachments/{attachment_id}"
    resp = requests.get(url, headers=_headers(token), timeout=30)
    if not resp.ok:
        raise GmailError(f"attachment[{resp.status_code}]: {resp.text[:200]}")
    data = resp.json()
    raw = data.get("data")
    if not raw:
        raise GmailError("attachment_empty")
    # Gmail API returns URL-safe base64 without padding
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def extract_message_meta(message: dict[str, Any]) -> dict[str, str]:
    headers = {
        h["name"].lower(): h["value"]
        for h in (message.get("payload") or {}).get("headers", [])
        if isinstance(h, dict)
    }
    return {
        "from": headers.get("from", "")[:255],
        "subject": headers.get("subject", "")[:200],
        "date": headers.get("date", "")[:50],
    }
