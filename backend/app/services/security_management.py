from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import UTC, datetime

from raijin_shared.models.sprint_6_10 import ApiKey, UserSession
from raijin_shared.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def backup_code() -> str:
    return "-".join([secrets.token_hex(2), secrets.token_hex(2), secrets.token_hex(2)])


async def create_api_key(
    session: AsyncSession,
    *,
    user: User,
    name: str,
    scopes: list[str],
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    raw = f"rjn_{secrets.token_urlsafe(32)}"
    api_key = ApiKey(
        tenant_id=user.tenant_id,
        user_id=user.id,
        name=name,
        key_prefix=raw[:12],
        key_hash=hash_secret(raw),
        scopes=scopes,
        expires_at=expires_at,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    return api_key, raw


async def authenticate_api_key(session: AsyncSession, raw_key: str) -> User | None:
    key_hash = hash_secret(raw_key)
    api_key = await session.scalar(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
    )
    if not api_key:
        return None
    if api_key.expires_at and api_key.expires_at < datetime.now(UTC):
        return None
    user = await session.get(User, api_key.user_id)
    if not user or not user.is_active:
        return None
    api_key.last_used_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(user, attribute_names=["tenant"])
    return user


async def record_session(
    session: AsyncSession,
    *,
    user: User,
    refresh_token: str,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    item = UserSession(
        tenant_id=user.tenant_id,
        user_id=user.id,
        session_hash=hash_secret(refresh_token),
        ip_address=ip_address,
        user_agent=(user_agent[:500] if user_agent else None),
        last_seen_at=datetime.now(UTC),
    )
    session.add(item)
    await session.commit()


async def touch_session(session: AsyncSession, *, refresh_token: str) -> None:
    item = await session.scalar(
        select(UserSession).where(
            UserSession.session_hash == hash_secret(refresh_token),
            UserSession.revoked_at.is_(None),
        )
    )
    if item:
        item.last_seen_at = datetime.now(UTC)
        await session.commit()


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _totp_at(secret: str, counter: int, digits: int = 6) -> str:
    padding = "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(f"{secret}{padding}", casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10**digits)).zfill(digits)


def verify_totp_code(secret: str, code: str, *, period: int = 30, window: int = 1) -> bool:
    normalized = "".join(ch for ch in code if ch.isdigit())
    if len(normalized) != 6:
        return False
    counter = int(time.time() // period)
    return any(
        constant_time_match(_totp_at(secret, counter + skew), normalized)
        for skew in range(-window, window + 1)
    )


def verify_backup_code(stored_hashes: list[str] | None, code: str | None) -> list[str] | None:
    if not stored_hashes or not code:
        return None
    candidate = hash_secret(code.strip())
    for idx, stored in enumerate(stored_hashes):
        if constant_time_match(stored, candidate) or constant_time_match(stored, code.strip()):
            return [item for pos, item in enumerate(stored_hashes) if pos != idx]
    return None


def totp_uri(*, secret: str, issuer: str, account: str) -> str:
    return f"otpauth://totp/{issuer}:{account}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"


def constant_time_match(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)
