"""Matrice permissions Raijin.

Rôles (du plus faible au plus fort) : viewer < reviewer/user < admin.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from raijin_shared.models.user import User, UserRole

from app.api.deps import CurrentUser

# rank — plus élevé = plus de droits
_RANK: dict[UserRole, int] = {
    UserRole.VIEWER: 1,
    UserRole.USER: 2,  # legacy
    UserRole.REVIEWER: 2,
    UserRole.ADMIN: 3,
}


def rank(role: UserRole) -> int:
    return _RANK.get(role, 0)


def has_at_least(user: User, min_role: UserRole) -> bool:
    return rank(user.role) >= rank(min_role)


def require_role(min_role: UserRole):
    """FastAPI dep factory — vérifie que user.role ≥ min_role."""

    async def _dep(user: CurrentUser) -> User:
        if not has_at_least(user, min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "insufficient_permissions",
                    "required": min_role.value,
                    "actual": user.role.value,
                },
            )
        return user

    return Depends(_dep)


RequireAdmin = require_role(UserRole.ADMIN)
RequireReviewer = require_role(UserRole.REVIEWER)
RequireViewer = require_role(UserRole.VIEWER)
