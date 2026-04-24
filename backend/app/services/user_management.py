from __future__ import annotations

import secrets
import uuid

from raijin_shared.models.user import User, UserRole
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_password_reset_token, hash_password, verify_password
from app.services.email_delivery import send_transactional_email


class UserManagementError(Exception):
    pass


class EmailAlreadyUsedError(UserManagementError):
    pass


class SelfDeactivationError(UserManagementError):
    pass


class InvalidCurrentPasswordError(UserManagementError):
    pass


class WeakPasswordError(UserManagementError):
    pass


def generate_temp_password() -> str:
    return secrets.token_urlsafe(18)


async def list_tenant_users(
    session: AsyncSession, *, tenant_id: uuid.UUID
) -> list[User]:
    result = await session.scalars(
        select(User)
        .where(User.tenant_id == tenant_id)
        .order_by(User.created_at.asc())
    )
    return list(result.all())


async def create_tenant_user(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    email: str,
    full_name: str | None,
    role: UserRole,
) -> tuple[User, str]:
    existing = await session.scalar(
        select(User).where(User.tenant_id == tenant_id, User.email == email.lower())
    )
    if existing:
        raise EmailAlreadyUsedError()

    temp_password = generate_temp_password()
    user = User(
        tenant_id=tenant_id,
        email=email.lower(),
        password_hash=hash_password(temp_password),
        full_name=full_name,
        role=role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    settings = get_settings()
    token = create_password_reset_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        password_hash=user.password_hash,
    )
    activation_link = f"{settings.frontend_url.rstrip('/')}/reset-password?token={token}"
    display_name = full_name or email
    text = (
        f"Bonjour {display_name},\n\n"
        "Tu as été invité sur Raijin. Active ton compte avec ce lien valable 1 heure :\n"
        f"{activation_link}\n\n"
        "Si tu n'attendais pas cette invitation, ignore cet email."
    )
    html = (
        f"<p>Bonjour {display_name},</p>"
        "<p>Tu as été invité sur Raijin. Active ton compte avec ce lien valable 1 heure.</p>"
        f'<p><a href="{activation_link}">Activer mon compte</a></p>'
        "<p>Si tu n'attendais pas cette invitation, ignore cet email.</p>"
    )
    await send_transactional_email(
        to_email=user.email,
        subject="Invitation à rejoindre Raijin",
        text=text,
        html=html,
    )
    return user, activation_link


async def update_tenant_user(
    session: AsyncSession,
    *,
    target: User,
    acting_user: User,
    full_name: str | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> User:
    if full_name is not None:
        target.full_name = full_name or None
    if role is not None:
        target.role = role
    if is_active is not None:
        if target.id == acting_user.id and not is_active:
            raise SelfDeactivationError()
        target.is_active = is_active
    await session.commit()
    await session.refresh(target)
    return target


async def get_tenant_user(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> User | None:
    user = await session.get(User, user_id)
    if user is None or user.tenant_id != tenant_id:
        return None
    return user


async def update_self_profile(
    session: AsyncSession,
    *,
    user: User,
    full_name: str | None = None,
) -> User:
    if full_name is not None:
        user.full_name = full_name.strip() or None
    await session.commit()
    await session.refresh(user)
    return user


async def change_password(
    session: AsyncSession,
    *,
    user: User,
    current_password: str,
    new_password: str,
) -> None:
    if len(new_password) < 8:
        raise WeakPasswordError("password_too_short")
    if not verify_password(current_password, user.password_hash):
        raise InvalidCurrentPasswordError()
    user.password_hash = hash_password(new_password)
    await session.commit()
