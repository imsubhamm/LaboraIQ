import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Permission, RolePermission, User, UserRoleAssignment


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
    current = datetime.now(UTC)
    rows = db.execute(
        select(User, UserRoleAssignment.id, UserRoleAssignment.branch_id, Permission.code)
        .outerjoin(
            UserRoleAssignment,
            and_(
                UserRoleAssignment.user_id == User.id,
                UserRoleAssignment.organization_id == User.organization_id,
                UserRoleAssignment.active.is_(True),
                UserRoleAssignment.effective_at <= current,
                or_(
                    UserRoleAssignment.expires_at.is_(None),
                    UserRoleAssignment.expires_at > current,
                ),
            ),
        )
        .outerjoin(RolePermission, RolePermission.role_id == UserRoleAssignment.role_id)
        .outerjoin(Permission, Permission.id == RolePermission.permission_id)
        .where(
            User.email == email,
            User.status == "active",
        )
    ).all()
    if not rows:
        raise HTTPException(status_code=401, detail="Authenticated identity is not provisioned")
    user = rows[0][0]
    permissions = {permission_code for _, _, _, permission_code in rows if permission_code}
    request.state.auth = user
    return AuthContext(
        user_id=user.id,
        organization_id=user.organization_id,
        email=user.email,
        branch_ids=frozenset(branch_id for _, _, branch_id, _ in rows if branch_id),
        permissions=frozenset(permissions),
        is_organization_scoped=any(
            assignment_id is not None and branch_id is None
            for _, assignment_id, branch_id, _ in rows
        ),
    )


Auth = Annotated[AuthContext, Depends(get_auth_context)]


def require_permission(code: str) -> Callable[[AuthContext], AuthContext]:
    def dependency(context: Auth) -> AuthContext:
        if code not in context.permissions:
            raise HTTPException(status_code=403, detail=f"Missing permission: {code}")
        return context

    return dependency
