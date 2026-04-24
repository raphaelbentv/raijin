import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TokenType = Literal["access", "refresh", "password_reset"]

_BCRYPT_MAX_BYTES = 72


def _truncate_for_bcrypt(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) <= _BCRYPT_MAX_BYTES:
        return password
    return encoded[:_BCRYPT_MAX_BYTES].decode("utf-8", errors="ignore")


def hash_password(password: str) -> str:
    return _pwd_context.hash(_truncate_for_bcrypt(password))


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(_truncate_for_bcrypt(plain), hashed)


def _create_token(
    *,
    subject: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
    token_type: TokenType,
    ttl: timedelta,
    extra: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "tid": str(tenant_id),
        "role": role,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(*, user_id: uuid.UUID, tenant_id: uuid.UUID, role: str) -> str:
    settings = get_settings()
    return _create_token(
        subject=user_id,
        tenant_id=tenant_id,
        role=role,
        token_type="access",
        ttl=timedelta(minutes=settings.jwt_access_ttl_minutes),
    )


def create_refresh_token(*, user_id: uuid.UUID, tenant_id: uuid.UUID, role: str) -> str:
    settings = get_settings()
    return _create_token(
        subject=user_id,
        tenant_id=tenant_id,
        role=role,
        token_type="refresh",
        ttl=timedelta(days=settings.jwt_refresh_ttl_days),
    )


def _password_fingerprint(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:24]


def create_password_reset_token(*, user_id: uuid.UUID, tenant_id: uuid.UUID, password_hash: str) -> str:
    return _create_token(
        subject=user_id,
        tenant_id=tenant_id,
        role="reset",
        token_type="password_reset",
        ttl=timedelta(hours=1),
        extra={"pwd": _password_fingerprint(password_hash)},
    )


def decode_token(token: str, *, expected_type: TokenType) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("invalid_token") from exc

    if payload.get("type") != expected_type:
        raise ValueError("wrong_token_type")
    return payload


def password_fingerprint_matches(password_hash: str, fingerprint: str | None) -> bool:
    return bool(fingerprint) and _password_fingerprint(password_hash) == fingerprint
