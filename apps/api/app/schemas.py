import uuid
from datetime import date, datetime
from decimal import Decimal
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


class TestCatalogRead(APIModel):
    id: uuid.UUID
    code: str
    name: str
    specimen_type: str
    container_type: str
    price: Decimal


class IntakeCreate(APIModel):
    patient_id: uuid.UUID | None = None
    full_name: str | None = Field(default=None, max_length=200)
    phone: str = Field(min_length=6, max_length=40)
    email: EmailStr
    date_of_birth: date | None = None
    age_years: int | None = Field(default=None, ge=0, le=130)
    sex: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=2000)
    blood_group: str = Field(min_length=1, max_length=10)
    country: str = Field(min_length=2, max_length=100)
    race: str | None = Field(default=None, max_length=100)
    nationality: str = Field(min_length=2, max_length=100)
    visit_type: str = Field(pattern=r"^(OP|IP)$")
    department: str = Field(min_length=2, max_length=120)
    ward: str | None = Field(default=None, max_length=120)
    doctor_name: str = Field(min_length=2, max_length=200)
    diagnosis: str | None = Field(default=None, max_length=2000)
    additional_patient_data: dict[str, str] = Field(default_factory=dict)
    prescription_filename: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=4000)
    test_ids: list[uuid.UUID] = Field(min_length=1)
    discount: Decimal = Field(default=Decimal("0"), ge=0)


class SpecimenRead(APIModel):
    barcode: str
    specimen_type: str
    container_type: str
    status: str


class IntakeRead(APIModel):
    patient_id: uuid.UUID
    patient_number: str
    order_id: uuid.UUID
    order_number: str
    invoice_number: str
    subtotal: Decimal
    discount: Decimal
    total: Decimal
    payment_status: str
    specimens: list[SpecimenRead]


class PatientLookupRead(APIModel):
    id: uuid.UUID
    patient_number: str
    full_name: str
    phone: str
    email: str | None
    date_of_birth: date | None
    age_years: int | None
    sex: str | None
    address: str | None
    blood_group: str | None
    country: str | None
    race: str | None
    nationality: str | None
    additional_patient_data: dict[str, str] | None
    visit_count: int
    last_visit_at: datetime | None


class PaymentSummary(APIModel):
    order_id: uuid.UUID
    order_number: str
    patient_number: str
    patient_name: str
    invoice_number: str
    total: Decimal
    payment_status: str


class PaymentCreate(APIModel):
    payment_method: str = Field(pattern=r"^(UPI|CARD|CASH)$")
    transaction_id: str | None = Field(default=None, max_length=120)


class PaymentRead(PaymentSummary):
    payment_method: str
    transaction_id: str | None
    paid_at: datetime
    specimens: list[SpecimenRead]
