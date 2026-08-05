import ipaddress
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

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


class AnalyzerCreate(APIModel):
    branch_id: uuid.UUID
    code: str = Field(pattern=r"^[A-Z0-9_-]{2,40}$")
    vendor: str = Field(min_length=2, max_length=120)
    model: str = Field(min_length=1, max_length=120)
    protocol: str = Field(pattern=r"^(ASTM|HL7_LAW|PROPRIETARY)$")
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    connection_mode: str = Field(
        default="bidirectional", pattern=r"^(unidirectional|bidirectional)$"
    )
    connection_timeout_seconds: int = Field(default=3, ge=1, le=15)
    retry_limit: int = Field(default=2, ge=0, le=5)
    heartbeat_interval_seconds: int = Field(default=60, ge=15, le=3600)

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        try:
            ipaddress.ip_address(value)
        except ValueError as error:
            raise ValueError("host must be a valid IPv4 or IPv6 address") from error
        return value


class AnalyzerUpdate(APIModel):
    vendor: str | None = Field(default=None, min_length=2, max_length=120)
    model: str | None = Field(default=None, min_length=1, max_length=120)
    protocol: str | None = Field(default=None, pattern=r"^(ASTM|HL7_LAW|PROPRIETARY)$")
    host: str | None = Field(default=None, min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    connection_mode: str | None = Field(default=None, pattern=r"^(unidirectional|bidirectional)$")
    connection_timeout_seconds: int | None = Field(default=None, ge=1, le=15)
    retry_limit: int | None = Field(default=None, ge=0, le=5)
    heartbeat_interval_seconds: int | None = Field(default=None, ge=15, le=3600)
    status: Status | None = None

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                ipaddress.ip_address(value)
            except ValueError as error:
                raise ValueError("host must be a valid IPv4 or IPv6 address") from error
        return value


class AnalyzerRead(AnalyzerCreate):
    id: uuid.UUID
    organization_id: uuid.UUID
    status: Status
    connection_status: str
    last_connection_test_at: datetime | None
    last_connected_at: datetime | None
    last_connection_error: str | None
    created_at: datetime
    updated_at: datetime


class AnalyzerConnectionEventRead(APIModel):
    id: uuid.UUID
    analyzer_id: uuid.UUID
    event_type: str
    attempt: int
    success: bool
    latency_ms: int | None
    message: str
    correlation_id: str
    occurred_at: datetime


class AnalyzerConnectionTestRead(APIModel):
    analyzer_id: uuid.UUID
    connection_status: str
    attempts: int
    success: bool
    latency_ms: int | None
    message: str
    tested_at: datetime


class AnalyzerParameterMappingCreate(APIModel):
    parameter_id: uuid.UUID
    machine_parameter_code: str = Field(min_length=1, max_length=100)
    unit: str | None = Field(default=None, max_length=40)


class AnalyzerTestMappingCreate(APIModel):
    test_id: uuid.UUID
    machine_test_code: str = Field(min_length=1, max_length=100)
    parameters: list[AnalyzerParameterMappingCreate] = Field(default_factory=list)


class AnalyzerParameterMappingRead(AnalyzerParameterMappingCreate):
    id: uuid.UUID
    parameter_name: str
    lis_parameter_code: str


class AnalyzerTestMappingRead(APIModel):
    id: uuid.UUID
    analyzer_id: uuid.UUID
    test_id: uuid.UUID
    lis_test_code: str
    test_name: str
    machine_test_code: str
    status: Status
    parameters: list[AnalyzerParameterMappingRead]
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


class TestParameterRead(APIModel):
    id: uuid.UUID
    name: str
    external_code: str
    display_order: int


class TestMasterCreate(APIModel):
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{2,40}$")
    name: str = Field(min_length=2, max_length=200)
    service_type: str = Field(default="Pathology", min_length=2, max_length=80)
    department: str = Field(default="Laboratory", min_length=2, max_length=120)
    sub_department: str = Field(default="", max_length=120)
    specimen_type: str = Field(min_length=2, max_length=80)
    container_type: str = Field(default="Unspecified", min_length=2, max_length=100)
    price: Decimal = Field(default=Decimal("0"), ge=0)


class TestMasterRead(TestMasterCreate):
    id: uuid.UUID
    is_panel: bool
    validation_status: str
    status: Status
    parameters: list[TestParameterRead]
    created_at: datetime
    updated_at: datetime


class TestMasterImportRead(APIModel):
    rows_received: int
    tests_created: int
    tests_updated: int
    parameters_imported: int
    rows_rejected: int
    review_required: int
    errors: list[str]


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


class SpecimenWorkflowRead(SpecimenRead):
    id: uuid.UUID
    order_id: uuid.UUID
    order_number: str
    patient_number: str
    patient_name: str
    laboratory_department: str | None
    accession_number: str | None
    collection_location: str | None
    container_count: int
    collection_notes: str | None
    collected_at: datetime | None
    received_at: datetime | None
    reviewed_at: datetime | None
    rejection_reason: str | None
    rejection_notes: str | None


class SpecimenCollect(APIModel):
    collection_location: str = Field(min_length=2, max_length=200)
    container_count: int = Field(default=1, ge=1, le=20)
    collection_notes: str | None = Field(default=None, max_length=2000)


class SpecimenDecision(APIModel):
    decision: str = Field(pattern=r"^(accept|reject)$")
    rejection_reason: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)


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
