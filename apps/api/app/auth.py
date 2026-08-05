import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Permission, RolePermission, User, UserRoleAssignment
from app.oidc import OidcNotConfiguredError, verify_oidc_id_token
from app.session_tokens import verify_session_token


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


def _load_context_for_user(db: Session, request: Request, user: User) -> AuthContext:
    current = datetime.now(UTC)
    rows = db.execute(
        select(UserRoleAssignment.id, UserRoleAssignment.branch_id, Permission.code)
        .outerjoin(RolePermission, RolePermission.role_id == UserRoleAssignment.role_id)
        .outerjoin(Permission, Permission.id == RolePermission.permission_id)
        .where(
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
    permissions = {permission_code for _, _, permission_code in rows if permission_code}
    request.state.auth = user
    return AuthContext(
        user_id=user.id,
        organization_id=user.organization_id,
        email=user.email,
        branch_ids=frozenset(branch_id for _, branch_id, _ in rows if branch_id),
        permissions=frozenset(permissions),
        is_organization_scoped=any(
            assignment_id is not None and branch_id is None
            for assignment_id, branch_id, _ in rows
        ),
    )


def _find_active_user(
    db: Session,
    *,
    email: str | None = None,
    auth_provider_id: str | None = None,
) -> User | None:
    if auth_provider_id:
        user = db.scalar(
            select(User).where(
                User.auth_provider_id == auth_provider_id,
                User.status == "active",
            )
        )
        if user:
            return user
    if email:
        return db.scalar(
            select(User).where(
                User.email == email.lower().strip(),
                User.status == "active",
            )
        )
    return None


def load_context_for_identity(
    db: Session,
    request: Request,
    *,
    email: str | None = None,
    auth_provider_id: str | None = None,
) -> AuthContext:
    user = _find_active_user(db, email=email, auth_provider_id=auth_provider_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Authenticated identity is not provisioned")
    return _load_context_for_user(db, request, user)


def _email_from_bearer(token: str) -> tuple[str, str | None]:
    """Return (email, auth_provider_id) from a LaboraIQ session or OIDC token."""
    try:
        claims = verify_session_token(token)
        if claims.get("typ") != "session":
            raise jwt.InvalidTokenError("Unexpected token type")
        return str(claims["email"]).lower().strip(), None
    except jwt.PyJWTError:
        pass
    try:
        claims = verify_oidc_id_token(token)
        provider_id = str(claims.get("sub") or "")
        return str(claims["email"]).lower().strip(), provider_id or None
    except (jwt.PyJWTError, OidcNotConfiguredError, ValueError) as error:
        raise HTTPException(status_code=401, detail="Invalid or expired bearer token") from error


def get_auth_context(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    x_dev_user_email: Annotated[str | None, Header()] = None,
) -> AuthContext:
    settings = get_settings()
    bearer: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization.split(" ", 1)[1].strip()

    if bearer:
        email, auth_provider_id = _email_from_bearer(bearer)
        return load_context_for_identity(
            db, request, email=email, auth_provider_id=auth_provider_id
        )

    if settings.dev_auth_enabled and (x_dev_user_email or settings.dev_auth_user_email):
        email = (x_dev_user_email or settings.dev_auth_user_email).lower().strip()
        return load_context_for_identity(db, request, email=email)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


Auth = Annotated[AuthContext, Depends(get_auth_context)]


def require_permission(code: str) -> Callable[[AuthContext], AuthContext]:
    def dependency(context: Auth) -> AuthContext:
        if code not in context.permissions:
            raise HTTPException(status_code=403, detail=f"Missing permission: {code}")
        return context

    return dependency
