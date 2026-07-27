import uuid
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import Status


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


T = TypeVar("T")


class Page(APIModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class OrganizationCreate(APIModel):
    name: str = Field(min_length=2, max_length=200)
    code: str = Field(pattern=r"^[A-Z0-9_-]{2,50}$")


class OrganizationUpdate(APIModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    status: Status | None = None


class OrganizationRead(OrganizationCreate):
    id: uuid.UUID
    status: Status
    created_at: datetime
    updated_at: datetime


class BranchCreate(APIModel):
    name: str = Field(min_length=2, max_length=200)
    code: str = Field(pattern=r"^[A-Z0-9_-]{2,50}$")
    address: str | None = Field(default=None, max_length=2000)
    time_zone: str = Field(default="UTC", max_length=64)


class BranchUpdate(APIModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    address: str | None = Field(default=None, max_length=2000)
    time_zone: str | None = Field(default=None, max_length=64)
    status: Status | None = None


class BranchRead(BranchCreate):
    id: uuid.UUID
    organization_id: uuid.UUID
    status: Status
    created_at: datetime
    updated_at: datetime


class DepartmentCreate(APIModel):
    branch_id: uuid.UUID | None = None
    name: str = Field(min_length=2, max_length=200)
    code: str = Field(pattern=r"^[A-Z0-9_-]{2,50}$")


class DepartmentUpdate(APIModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    status: Status | None = None


class DepartmentRead(DepartmentCreate):
    id: uuid.UUID
    organization_id: uuid.UUID
    status: Status
    created_at: datetime
    updated_at: datetime


class UserCreate(APIModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=200)
    auth_provider_id: str = Field(min_length=3, max_length=255)


class UserUpdate(APIModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=200)
    status: Status | None = None


class UserRead(UserCreate):
    id: uuid.UUID
    organization_id: uuid.UUID
    status: Status
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PermissionRead(APIModel):
    id: uuid.UUID
    code: str
    description: str


class RoleCreate(APIModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None
    permission_codes: list[str] = []


class RoleRead(APIModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    name: str
    description: str | None
    is_template: bool
    status: Status
    permissions: list[PermissionRead]


class AssignmentCreate(APIModel):
    user_id: uuid.UUID
    role_id: uuid.UUID
    branch_id: uuid.UUID | None = None
    effective_at: datetime | None = None
    expires_at: datetime | None = None
    assignment_reason: str = Field(min_length=3, max_length=1000)


class AssignmentRead(APIModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    user_id: uuid.UUID
    role_id: uuid.UUID
    effective_at: datetime
    expires_at: datetime | None
    assignment_reason: str
    active: bool


class AuditEventRead(APIModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    actor_type: str
    event_type: str
    entity_type: str
    entity_id: str | None
    action: str
    previous_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    correlation_id: str
    ip_address: str | None
    user_agent: str | None
    occurred_at: datetime
    additional_metadata: dict[str, Any] | None
