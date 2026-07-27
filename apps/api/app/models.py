import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def uuid4() -> uuid.UUID:
    return uuid.uuid4()


def now() -> datetime:
    return datetime.now(UTC)


class Status(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.active)
    created_by: Mapped[uuid.UUID | None]
    updated_by: Mapped[uuid.UUID | None]


class Branch(Base, TimestampMixin):
    __tablename__ = "branches"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_branch_org_code"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(Text)
    time_zone: Mapped[str] = mapped_column(String(64), default="UTC")
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.active)
    created_by: Mapped[uuid.UUID | None]
    updated_by: Mapped[uuid.UUID | None]


class Department(Base, TimestampMixin):
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("organization_id", "branch_id", "code", name="uq_department_scope_code"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(50))
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.active)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("organization_id", "email", name="uq_user_org_email"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = mapped_column(String(320))
    display_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.active)
    auth_provider_id: Mapped[str] = mapped_column(String(255), unique=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Role(Base, TimestampMixin):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_role_org_name"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.active)
    permissions: Mapped[list["Permission"]] = relationship(
        secondary="role_permissions", lazy="selectin"
    )


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(255))


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"), primary_key=True)
    permission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("permissions.id"), primary_key=True)


class UserRoleAssignment(Base, TimestampMixin):
    __tablename__ = "user_role_assignments"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"), index=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    assignment_reason: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[Role] = relationship(lazy="selectin")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_org_timestamp", "organization_id", "occurred_at"),
        Index("ix_audit_entity", "entity_type", "entity_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id"), index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    actor_type: Mapped[str] = mapped_column(String(50))
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    previous_value: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    correlation_id: Mapped[str] = mapped_column(String(100), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    additional_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
