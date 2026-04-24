import ipaddress
import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from raijin_shared.models.sprint_6_10 import TenantIpRule
from raijin_shared.models.user import User, UserRole
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.services.security_management import authenticate_api_key

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(_oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> User:
    if x_api_key:
        api_user = await authenticate_api_key(db, x_api_key)
        if api_user:
            await _enforce_ip_rules(db, user=api_user, request=request)
            return api_user
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not_authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if token.startswith("rjn_"):
        api_user = await authenticate_api_key(db, token)
        if api_user:
            await _enforce_ip_rules(db, user=api_user, request=request)
            return api_user
    try:
        payload = decode_token(token, expected_type="access")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_or_expired_token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id = uuid.UUID(payload["sub"])
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user_not_found_or_inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    await db.refresh(user, attribute_names=["tenant"])
    await _enforce_ip_rules(db, user=user, request=request)
    return user


async def _enforce_ip_rules(db: AsyncSession, *, user: User, request: Request) -> None:
    rules = await db.scalars(
        select(TenantIpRule).where(
            TenantIpRule.tenant_id == user.tenant_id,
            TenantIpRule.is_active.is_(True),
        )
    )
    cidrs = [rule.cidr for rule in rules.all()]
    if not cidrs:
        return
    raw_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    raw_ip = raw_ip or (request.client.host if request.client else "")
    try:
        client_ip = ipaddress.ip_address(raw_ip)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="ip_not_allowed") from exc
    for cidr in cidrs:
        if client_ip in ipaddress.ip_network(cidr, strict=False):
            return
    raise HTTPException(status_code=403, detail="ip_not_allowed")


def require_role(*roles: UserRole):
    async def _dep(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="insufficient_permissions"
            )
        return user

    return _dep


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
