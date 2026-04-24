import uuid

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import CurrentUser, DbSession
from app.core.audit import log_action
from app.core.config import get_settings
from app.core.permissions import RequireAdmin
from app.schemas.user import UserCreate, UserCreated, UserOut, UserUpdate
from app.services.user_management import (
    EmailAlreadyUsedError,
    SelfDeactivationError,
    create_tenant_user,
    get_tenant_user,
    list_tenant_users,
    update_tenant_user,
)

router = APIRouter(prefix="/users", tags=["users"], dependencies=[RequireAdmin])


@router.get("", response_model=list[UserOut])
async def list_users(db: DbSession, user: CurrentUser) -> list[UserOut]:
    items = await list_tenant_users(db, tenant_id=user.tenant_id)
    return [UserOut.model_validate(u) for u in items]


@router.post("", response_model=UserCreated, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate, request: Request, db: DbSession, user: CurrentUser
) -> UserCreated:
    try:
        created, activation_link = await create_tenant_user(
            db,
            tenant_id=user.tenant_id,
            email=body.email,
            full_name=body.full_name,
            role=body.role,
        )
    except EmailAlreadyUsedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email_already_used"
        ) from exc

    await log_action(
        db,
        user=user,
        action="user.create",
        entity_type="user",
        entity_id=created.id,
        after={"email": created.email, "role": created.role.value},
        request=request,
    )
    settings = get_settings()
    return UserCreated(
        user=UserOut.model_validate(created),
        activation_link=activation_link if not settings.is_production else None,
    )


@router.patch("/{user_id}", response_model=UserOut)
async def patch_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    request: Request,
    db: DbSession,
    user: CurrentUser,
) -> UserOut:
    target = await get_tenant_user(db, tenant_id=user.tenant_id, user_id=user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="user_not_found")
    try:
        updated = await update_tenant_user(
            db,
            target=target,
            acting_user=user,
            full_name=body.full_name,
            role=body.role,
            is_active=body.is_active,
        )
    except SelfDeactivationError as exc:
        raise HTTPException(
            status_code=409, detail="cannot_deactivate_self"
        ) from exc
    await log_action(
        db,
        user=user,
        action="user.update",
        entity_type="user",
        entity_id=updated.id,
        after={
            "role": updated.role.value,
            "is_active": updated.is_active,
            "full_name": updated.full_name,
        },
        request=request,
    )
    return UserOut.model_validate(updated)


@router.delete("/{user_id}", status_code=204)
async def deactivate_user(
    user_id: uuid.UUID, request: Request, db: DbSession, user: CurrentUser
) -> None:
    target = await get_tenant_user(db, tenant_id=user.tenant_id, user_id=user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="user_not_found")
    try:
        await update_tenant_user(db, target=target, acting_user=user, is_active=False)
    except SelfDeactivationError as exc:
        raise HTTPException(status_code=409, detail="cannot_deactivate_self") from exc
    await log_action(
        db,
        user=user,
        action="user.deactivate",
        entity_type="user",
        entity_id=user_id,
        request=request,
    )
