import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User, UserRoleAssignment


@dataclass(frozen=True)
class AuthContext:
    user_id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    branch_ids: frozenset[uuid.UUID]
    permissions: frozenset[str]
    is_organization_scoped: bool

    def can_access_branch(self, branch_id: uuid.UUID | None) -> bool:
        return branch_id is None or self.is_organization_scoped or branch_id in self.branch_ids


def get_auth_context(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    x_dev_user_email: Annotated[str | None, Header()] = None,
) -> AuthContext:
    settings = get_settings()
    if not authorization and not (settings.dev_auth_enabled and x_dev_user_email):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not settings.dev_auth_enabled:
        raise HTTPException(status_code=401, detail="OIDC provider is not configured")

    email = x_dev_user_email or settings.dev_auth_user_email
    user = db.scalar(select(User).where(User.email == email, User.status == "active"))
    if user is None:
        raise HTTPException(status_code=401, detail="Authenticated identity is not provisioned")

    current = datetime.now(UTC)
    assignments = db.scalars(
        select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user.id,
            UserRoleAssignment.organization_id == user.organization_id,
            UserRoleAssignment.active.is_(True),
            UserRoleAssignment.effective_at <= current,
            or_(
                UserRoleAssignment.expires_at.is_(None),
                UserRoleAssignment.expires_at > current,
            ),
        )
    ).all()
    permissions = {
        permission.code for assignment in assignments for permission in assignment.role.permissions
    }
    request.state.auth = user
    return AuthContext(
        user_id=user.id,
        organization_id=user.organization_id,
        email=user.email,
        branch_ids=frozenset(
            assignment.branch_id for assignment in assignments if assignment.branch_id
        ),
        permissions=frozenset(permissions),
        is_organization_scoped=any(assignment.branch_id is None for assignment in assignments),
    )


Auth = Annotated[AuthContext, Depends(get_auth_context)]


def require_permission(code: str) -> Callable[[AuthContext], AuthContext]:
    def dependency(context: Auth) -> AuthContext:
        if code not in context.permissions:
            raise HTTPException(status_code=403, detail=f"Missing permission: {code}")
        return context

    return dependency
