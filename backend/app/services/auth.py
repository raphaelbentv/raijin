import re
import secrets
import unicodedata
import uuid

from raijin_shared.models.tenant import Tenant
from raijin_shared.models.user import User, UserRole
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    password_fingerprint_matches,
    verify_password,
)
from app.services.email_delivery import send_transactional_email


class AuthError(Exception):
    pass


class InvalidCredentialsError(AuthError):
    pass


class EmailAlreadyExistsError(AuthError):
    pass


class InactiveUserError(AuthError):
    pass


class InvalidResetTokenError(AuthError):
    pass


def _slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return normalized or "tenant"


async def _generate_unique_slug(session: AsyncSession, base: str) -> str:
    slug = _slugify(base)
    candidate = slug
    attempts = 0
    while True:
        exists = await session.scalar(select(Tenant.id).where(Tenant.slug == candidate))
        if not exists:
            return candidate
        attempts += 1
        candidate = f"{slug}-{secrets.token_hex(3)}"
        if attempts > 5:
            return f"{slug}-{uuid.uuid4().hex[:8]}"


async def register_tenant_and_admin(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str | None,
    tenant_name: str,
) -> User:
    existing = await session.scalar(select(User).where(User.email == email.lower()))
    if existing:
        raise EmailAlreadyExistsError()

    slug = await _generate_unique_slug(session, tenant_name)
    tenant = Tenant(name=tenant_name, slug=slug)
    session.add(tenant)
    await session.flush()

    user = User(
        tenant_id=tenant.id,
        email=email.lower(),
        password_hash=hash_password(password),
        full_name=full_name,
        role=UserRole.ADMIN,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user, attribute_names=["tenant"])
    return user


async def authenticate(session: AsyncSession, *, email: str, password: str) -> User:
    user = await session.scalar(
        select(User).where(User.email == email.lower())
    )
    if not user or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError()
    if not user.is_active:
        raise InactiveUserError()
    await session.refresh(user, attribute_names=["tenant"])
    return user


def issue_token_pair(user: User) -> tuple[str, str]:
    access = create_access_token(
        user_id=user.id, tenant_id=user.tenant_id, role=user.role.value
    )
    refresh = create_refresh_token(
        user_id=user.id, tenant_id=user.tenant_id, role=user.role.value
    )
    return access, refresh


async def refresh_access_token(session: AsyncSession, *, refresh_token: str) -> str:
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except ValueError as exc:
        raise InvalidCredentialsError() from exc

    user_id = uuid.UUID(payload["sub"])
    user = await session.get(User, user_id)
    if not user or not user.is_active:
        raise InvalidCredentialsError()

    return create_access_token(
        user_id=user.id, tenant_id=user.tenant_id, role=user.role.value
    )


async def request_password_reset(session: AsyncSession, *, email: str) -> str | None:
    user = await session.scalar(select(User).where(User.email == email.lower()))
    if not user or not user.is_active:
        return None

    settings = get_settings()
    token = create_password_reset_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        password_hash=user.password_hash,
    )
    reset_link = f"{settings.frontend_url.rstrip('/')}/reset-password?token={token}"
    text = (
        "Bonjour,\n\n"
        "Tu peux réinitialiser ton mot de passe Raijin avec ce lien valable 1 heure :\n"
        f"{reset_link}\n\n"
        "Si tu n'as rien demandé, ignore cet email."
    )
    html = (
        "<p>Bonjour,</p>"
        "<p>Tu peux réinitialiser ton mot de passe Raijin avec ce lien valable 1 heure.</p>"
        f'<p><a href="{reset_link}">Réinitialiser mon mot de passe</a></p>'
        "<p>Si tu n'as rien demandé, ignore cet email.</p>"
    )
    await send_transactional_email(
        to_email=user.email,
        subject="Réinitialisation de ton mot de passe Raijin",
        text=text,
        html=html,
    )
    return reset_link


async def reset_password_with_token(
    session: AsyncSession, *, token: str, new_password: str
) -> User:
    try:
        payload = decode_token(token, expected_type="password_reset")
    except ValueError as exc:
        raise InvalidResetTokenError() from exc

    user_id = uuid.UUID(payload["sub"])
    user = await session.get(User, user_id)
    if (
        not user
        or not user.is_active
        or str(user.tenant_id) != payload.get("tid")
        or not password_fingerprint_matches(user.password_hash, payload.get("pwd"))
    ):
        raise InvalidResetTokenError()

    user.password_hash = hash_password(new_password)
    await session.commit()
    await session.refresh(user, attribute_names=["tenant"])
    return user
