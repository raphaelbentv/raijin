"""Endpoints pour l'utilisateur courant : profil + mot de passe."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import UserOut
from app.services.user_management import (
    InvalidCurrentPasswordError,
    WeakPasswordError,
    change_password,
    update_self_profile,
)

router = APIRouter(prefix="/me", tags=["me"])


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    locale: str | None = Field(default=None, max_length=10)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class NotificationPreferencesUpdate(BaseModel):
    preferences: dict


@router.patch("/profile", response_model=UserOut)
async def patch_profile(body: ProfileUpdate, db: DbSession, user: CurrentUser) -> UserOut:
    updated = await update_self_profile(db, user=user, full_name=body.full_name)
    if body.locale:
        updated.locale = body.locale
        await db.commit()
        await db.refresh(updated, attribute_names=["tenant"])
    return UserOut.model_validate(updated)


@router.post("/password", status_code=204)
async def post_password(body: PasswordChange, db: DbSession, user: CurrentUser) -> None:
    try:
        await change_password(
            db,
            user=user,
            current_password=body.current_password,
            new_password=body.new_password,
        )
    except InvalidCurrentPasswordError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_current_password",
        ) from exc
    except WeakPasswordError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.get("/notification-preferences")
async def get_notification_preferences(user: CurrentUser) -> dict:
    return user.notification_preferences or {}


@router.put("/notification-preferences")
async def put_notification_preferences(
    body: NotificationPreferencesUpdate, db: DbSession, user: CurrentUser
) -> dict:
    user.notification_preferences = body.preferences
    await db.commit()
    return user.notification_preferences or {}
