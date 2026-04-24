"""Minimal Google Drive client pour poller un dossier partagé."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import requests
from raijin_shared.models.cloud_drive import CloudDriveSource
from raijin_shared.security import decrypt, encrypt

from app.core.config import get_settings

DRIVE_BASE = "https://www.googleapis.com/drive/v3"
TOKEN_URL = "https://oauth2.googleapis.com/token"

SUPPORTED_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}


class DriveError(RuntimeError):
    pass


class DriveAuthError(DriveError):
    pass


def _refresh_if_needed(source: CloudDriveSource, session) -> str:
    now = datetime.now(UTC)
    if source.token_expires_at and source.token_expires_at > now + timedelta(minutes=1):
        return decrypt(source.access_token_encrypted)

    refresh = (
        decrypt(source.refresh_token_encrypted) if source.refresh_token_encrypted else None
    )
    if not refresh:
        raise DriveAuthError("no_refresh_token")

    s = get_settings()
    if not s.google_client_id or not s.google_client_secret:
        raise DriveAuthError("google_not_configured")

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
        raise DriveError(f"refresh_network: {exc}") from exc

    if resp.status_code >= 400:
        raise DriveAuthError(f"refresh {resp.status_code}: {resp.text[:200]}")

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


def list_files_in_folder(
    session, source: CloudDriveSource, *, since: datetime | None
) -> Iterator[dict[str, Any]]:
    token = _refresh_if_needed(source, session)
    url = f"{DRIVE_BASE}/files"

    q_parts = [f"'{source.folder_id}' in parents", "trashed = false"]
    mime_list = ",".join(f"'{m}'" for m in SUPPORTED_MIME)
    q_parts.append(f"mimeType in ({mime_list})")
    if since:
        iso = since.isoformat()
        if iso.endswith("+00:00"):
            iso = iso[:-6] + "Z"
        q_parts.append(f"modifiedTime > '{iso}'")

    params: dict[str, str] = {
        "q": " and ".join(q_parts),
        "fields": "nextPageToken, files(id, name, mimeType, size, modifiedTime)",
        "orderBy": "modifiedTime asc",
        "pageSize": "100",
    }
    page_token: str | None = None

    while True:
        if page_token:
            params["pageToken"] = page_token
        resp = requests.get(url, headers=_headers(token), params=params, timeout=30)
        if resp.status_code in (401, 403):
            raise DriveAuthError(f"auth_failed: {resp.text[:200]}")
        if not resp.ok:
            raise DriveError(f"drive_list[{resp.status_code}]: {resp.text[:200]}")
        data = resp.json()
        yield from data.get("files", [])
        page_token = data.get("nextPageToken")
        if not page_token:
            break
        params.pop("pageToken", None)


def download_file(session, source: CloudDriveSource, file_id: str) -> bytes:
    token = _refresh_if_needed(source, session)
    url = f"{DRIVE_BASE}/files/{file_id}"
    resp = requests.get(
        url,
        headers=_headers(token),
        params={"alt": "media"},
        timeout=60,
    )
    if not resp.ok:
        raise DriveError(f"drive_download[{resp.status_code}]: {resp.text[:200]}")
    return resp.content
