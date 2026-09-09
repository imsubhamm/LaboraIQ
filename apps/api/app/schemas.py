import ipaddress
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer, field_validator

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
    # Dev identities use reserved TLDs like .local; EmailStr rejects those on read.
    email: str
    id: uuid.UUID
    organization_id: uuid.UUID
    status: Status
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OidcMetadataRead(APIModel):
    enabled: bool
    issuer: str | None = None
    client_id: str | None = None
    authorization_endpoint: str | None = None
    audience: str | None = None


class OidcSessionCreate(APIModel):
    id_token: str = Field(min_length=20)


class SessionTokenRead(APIModel):
    access_token: str
    token_type: str = "Bearer"
    expires_at: datetime
    email: str
    user_id: uuid.UUID
    organization_id: uuid.UUID
    permissions: list[str]


class AuthMeRead(APIModel):
    user_id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    display_name: str | None = None
    permissions: list[str]
    branch_ids: list[uuid.UUID]
    is_organization_scoped: bool


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
    unit: str | None = None
    reference_low: str | None = None
    reference_high: str | None = None
    reference_text: str | None = None
    critical_low: str | None = None
    critical_high: str | None = None
    reference_source: str | None = None


class TestParameterCreate(APIModel):
    name: str = Field(min_length=1, max_length=200)
    external_code: str = Field(min_length=1, max_length=255)
    display_order: int = Field(default=0, ge=0)
    unit: str | None = Field(default=None, max_length=40)
    reference_low: str | None = Field(default=None, max_length=40)
    reference_high: str | None = Field(default=None, max_length=40)
    reference_text: str | None = Field(default=None, max_length=200)
    critical_low: str | None = Field(default=None, max_length=40)
    critical_high: str | None = Field(default=None, max_length=40)
    reference_source: str | None = Field(default=None, max_length=200)


class TestParameterUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    external_code: str | None = Field(default=None, min_length=1, max_length=255)
    display_order: int | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=40)
    reference_low: str | None = Field(default=None, max_length=40)
    reference_high: str | None = Field(default=None, max_length=40)
    reference_text: str | None = Field(default=None, max_length=200)
    critical_low: str | None = Field(default=None, max_length=40)
    critical_high: str | None = Field(default=None, max_length=40)
    reference_source: str | None = Field(default=None, max_length=200)


class AnalyzerWorklistRead(APIModel):
    id: uuid.UUID
    specimen_id: uuid.UUID
    specimen_barcode: str
    accession_number: str | None
    order_id: uuid.UUID
    order_number: str
    test_id: uuid.UUID
    lis_test_code: str
    test_name: str
    analyzer_id: uuid.UUID
    analyzer_code: str
    analyzer_name: str
    mapping_id: uuid.UUID
    machine_test_code: str
    status: str
    correlation_id: str
    cancelled_reason: str | None
    latest_attempt_no: int | None = None
    latest_attempt_state: str | None = None
    created_at: datetime
    updated_at: datetime


class AnalyzerWorklistCancel(APIModel):
    reason: str | None = Field(default=None, max_length=200)


class AnalyzerMessageRead(APIModel):
    id: uuid.UUID
    analyzer_id: uuid.UUID
    worklist_item_id: uuid.UUID | None
    attempt_id: uuid.UUID | None
    direction: str
    content_type: str
    body: str
    payload_hash: str
    correlation_id: str
    created_at: datetime


class LisIntegrationMessageRead(APIModel):
    id: uuid.UUID
    specimen_id: uuid.UUID
    order_id: uuid.UUID
    event_category: str
    message_type: str
    content_type: str
    body: str
    payload_hash: str
    correlation_id: str
    delivery_state: str
    delivered_at: datetime | None
    delivery_error: str | None
    created_at: datetime


class LisStatusDispatch(APIModel):
    module_id: str = Field(min_length=1, max_length=40, default="90")
    status_code: str = Field(min_length=1, max_length=10, default="I")
    event_code: str = Field(min_length=1, max_length=40, default="ARRIV")
    event_value: str = Field(min_length=1, max_length=40, default="1")


class LisStorageDispatch(APIModel):
    module_id: str = Field(min_length=1, max_length=40, default="90")
    rack_id: str = Field(min_length=1, max_length=60)
    position: str = Field(min_length=1, max_length=20)
    carrier_type: str = Field(min_length=1, max_length=80, default="ESFlex80pos")


class LisRoutingCodeRead(APIModel):
    code: str
    category: str


class LisRoutingPlanRead(APIModel):
    specimen_barcode: str
    accession_number: str | None
    order_number: str
    fluid: str
    routing_codes: list[LisRoutingCodeRead]
    message_preview: str


class LisDispatchProcessRead(APIModel):
    processed: int
    sent: int
    failed: int
    message_ids: list[uuid.UUID]


class LisMessageQueueSummaryRead(APIModel):
    pending: int
    failed: int
    sent: int
    oldest_pending_age_seconds: int | None
    oldest_failed_age_seconds: int | None


class AnalyzerOrderAttemptRead(APIModel):
    id: uuid.UUID
    worklist_item_id: uuid.UUID
    analyzer_id: uuid.UUID
    attempt_no: int
    state: str
    correlation_id: str
    payload_hash: str | None
    request_message_id: uuid.UUID | None
    response_message_id: uuid.UUID | None
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AnalyzerOrderProcessRead(APIModel):
    processed: int
    attempts: list[AnalyzerOrderAttemptRead]


class LabResultObservationRead(APIModel):
    id: uuid.UUID
    sequence_no: int
    parameter_id: uuid.UUID | None
    machine_parameter_code: str
    parameter_name: str
    value: str
    unit: str | None
    reference_low: str | None
    reference_high: str | None
    reference_text: str | None
    flag: str | None


class LabResultRead(APIModel):
    id: uuid.UUID
    worklist_item_id: uuid.UUID
    specimen_id: uuid.UUID
    specimen_barcode: str
    accession_number: str | None
    order_id: uuid.UUID
    order_number: str
    patient_number: str
    patient_name: str
    test_id: uuid.UUID
    lis_test_code: str
    test_name: str
    analyzer_id: uuid.UUID
    analyzer_code: str
    status: str
    correlation_id: str
    report_number: str | None
    technical_reviewed_at: datetime | None
    technical_review_notes: str | None
    pathologist_validated_at: datetime | None
    pathologist_notes: str | None
    released_at: datetime | None
    observations: list[LabResultObservationRead]
    created_at: datetime
    updated_at: datetime


class LabResultNotes(APIModel):
    notes: str | None = Field(default=None, max_length=500)


class AnalyzerMappingStatusUpdate(APIModel):
    status: Status


class TestMasterCreate(APIModel):
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{2,40}$")
    name: str = Field(min_length=2, max_length=200)
    service_type: str = Field(default="Pathology", min_length=2, max_length=80)
    department: str = Field(default="Laboratory", min_length=2, max_length=120)
    sub_department: str = Field(default="", max_length=120)
    specimen_type: str = Field(min_length=2, max_length=80)
    container_type: str = Field(default="Unspecified", min_length=2, max_length=100)
    price: Decimal = Field(default=Decimal("0"), ge=0)

    @field_serializer("price")
    def serialize_price(self, value: Decimal) -> Decimal:
        # Ensure stable 2-decimal formatting for UI + import tests.
        return value.quantize(Decimal("0.01"))


class TestMasterUpdate(APIModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    service_type: str | None = Field(default=None, min_length=2, max_length=80)
    department: str | None = Field(default=None, min_length=2, max_length=120)
    sub_department: str | None = Field(default=None, max_length=120)
    specimen_type: str | None = Field(default=None, min_length=2, max_length=80)
    container_type: str | None = Field(default=None, min_length=2, max_length=100)
    price: Decimal | None = Field(default=None, ge=0)


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


class AnalyzerHealthScoreRead(APIModel):
    score: float
    status: str
    reasons: list[str]


class AnalyzerDashboardSummaryRead(APIModel):
    total_analyzers: int
    online: int
    degraded: int
    offline: int
    overall_uptime_percent: float | None
    order_success_percent: float | None
    result_success_percent: float | None
    open_alerts: int


class AnalyzerDashboardRowRead(APIModel):
    analyzer_id: uuid.UUID
    code: str
    vendor: str
    model: str
    branch_id: uuid.UUID
    branch_code: str
    branch_name: str
    time_zone: str
    configuration_status: str
    connectivity: str
    health: AnalyzerHealthScoreRead
    uptime_percent: float | None
    orders: int
    order_success_percent: float | None
    result_success_percent: float | None
    avg_latency_ms: float | None
    p50_latency_ms: float | None
    p95_latency_ms: float | None
    queue_depth: int
    last_seen_at: datetime | None
    last_successful_connection_at: datetime | None
    failed_orders: int
    retry_rate: float | None
    current_error: str | None
    timeout_rate: float | None
    avg_order_duration_seconds: float | None
    avg_result_turnaround_seconds: float | None
    work_items: int
    completed_items: int
    pending_items: int
    failed_items: int
    cancelled_items: int
    results_received: int
    technically_reviewed: int
    validated: int
    released: int
    tests_per_hour: float | None
    inbound_messages: int
    outbound_messages: int


class AnalyzerTrendPointRead(APIModel):
    bucket: datetime
    label: str
    availability_percent: float | None
    failure_rate: float | None
    avg_latency_ms: float | None
    throughput: float | None
    queue_depth: float | None


class AnalyzerAlertRead(APIModel):
    analyzer_id: uuid.UUID
    analyzer_code: str
    type: str
    severity: str
    message: str


class AnalyzerHealthEventRead(APIModel):
    occurred_at: datetime
    event_type: str
    success: bool
    latency_ms: int | None
    message: str


class AnalyzerHealthAttemptRead(APIModel):
    created_at: datetime
    attempt_no: int
    state: str
    error: str | None


class AnalyzerDashboardDetailRead(APIModel):
    analyzer_id: uuid.UUID
    connectivity: str
    health: AnalyzerHealthScoreRead
    last_heartbeat_at: datetime | None
    last_successful_connection_at: datetime | None
    current_latency_ms: int | None
    queue_depth: int
    current_error: str | None
    uptime_seconds: float
    downtime_seconds: float
    connection_failures: int
    failed_orders: int
    retry_rate: float | None
    timeout_rate: float | None
    avg_latency_ms: float | None
    p50_latency_ms: float | None
    p95_latency_ms: float | None
    avg_order_duration_seconds: float | None
    avg_result_turnaround_seconds: float | None
    orders_received: int
    completed_orders: int
    results_received: int
    tests_processed: int
    tests_per_hour: float | None
    inbound_messages: int
    outbound_messages: int
    ack_messages: int
    connection_events: list[AnalyzerHealthEventRead]
    failed_attempts: list[AnalyzerHealthAttemptRead]
    hourly_trends: list[AnalyzerTrendPointRead]


class AnalyzerDashboardRead(APIModel):
    window_start: datetime
    window_end: datetime
    summary: AnalyzerDashboardSummaryRead
    analyzers: list[AnalyzerDashboardRowRead]
    trends: list[AnalyzerTrendPointRead]
    alerts: list[AnalyzerAlertRead]
    detail: AnalyzerDashboardDetailRead | None = None
    query_batches: int


# --- Quality audit (NABL + INTERNAL) ---


class QualityAuditCreate(APIModel):
    branch_id: uuid.UUID
    audit_type: str = Field(pattern="^(NABL|INTERNAL)$")
    title: str = Field(min_length=2, max_length=200)
    audit_number: str | None = Field(default=None, max_length=40)
    lab_audit_subtype: str | None = Field(default=None, max_length=60)
    scope: str | None = None
    process_name: str | None = Field(default=None, max_length=120)
    department_id: uuid.UUID | None = None
    checklist_id: uuid.UUID | None = None
    standard_id: uuid.UUID | None = None
    auditor_user_id: uuid.UUID | None = None
    audit_owner_user_id: uuid.UUID | None = None
    planned_start_at: datetime | None = None
    description: str | None = None
    status: str = "DRAFT"


class QualityAuditUpdate(APIModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    lab_audit_subtype: str | None = Field(default=None, max_length=60)
    scope: str | None = None
    process_name: str | None = Field(default=None, max_length=120)
    department_id: uuid.UUID | None = None
    checklist_id: uuid.UUID | None = None
    standard_id: uuid.UUID | None = None
    auditor_user_id: uuid.UUID | None = None
    audit_owner_user_id: uuid.UUID | None = None
    planned_start_at: datetime | None = None
    description: str | None = None
    status: str | None = None


class QualityAuditRead(APIModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID
    department_id: uuid.UUID | None
    checklist_id: uuid.UUID | None
    standard_id: uuid.UUID | None
    audit_number: str
    audit_type: str
    lab_audit_subtype: str | None
    title: str
    scope: str | None
    process_name: str | None
    auditor_user_id: uuid.UUID | None
    audit_owner_user_id: uuid.UUID | None
    planned_start_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    closed_at: datetime | None
    status: str
    description: str | None
    compliance_percent: float | None = None
    is_demo: bool
    created_at: datetime
    updated_at: datetime


class AuditCheckResultCreate(APIModel):
    checklist_item_id: uuid.UUID
    result: str = Field(pattern="^(COMPLIANT|PARTIAL|NON_COMPLIANT|NOT_APPLICABLE)$")
    score: int | None = Field(default=None, ge=0, le=100)
    observation: str | None = None
    evidence_required: bool = False
    evidence_provided: bool = False


class AuditCheckResultRead(APIModel):
    id: uuid.UUID
    audit_id: uuid.UUID
    checklist_item_id: uuid.UUID
    result: str
    score: int | None
    observation: str | None
    evidence_required: bool
    evidence_provided: bool
    evaluated_by: uuid.UUID | None
    evaluated_at: datetime | None
    created_at: datetime


class AuditFindingCreate(APIModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=2)
    finding_type: str = Field(min_length=2, max_length=40)
    severity: str = Field(pattern="^(CRITICAL|MAJOR|MINOR|OBSERVATION)$")
    finding_number: str | None = Field(default=None, max_length=40)
    checklist_result_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    standard_id: uuid.UUID | None = None
    clause_id: uuid.UUID | None = None
    analyzer_id: uuid.UUID | None = None
    specimen_id: uuid.UUID | None = None
    lab_result_id: uuid.UUID | None = None
    worklist_item_id: uuid.UUID | None = None
    referenced_entity_type: str | None = Field(default=None, max_length=80)
    referenced_entity_id: str | None = Field(default=None, max_length=100)
    requirement: str | None = None
    root_cause: str | None = None
    correction: str | None = None
    corrective_action_required: bool = True
    preventive_action_required: bool = False
    owner_user_id: uuid.UUID | None = None
    due_at: datetime | None = None
    process_name: str | None = Field(default=None, max_length=120)
    status: str = "OPEN"


class AuditFindingUpdate(APIModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    finding_type: str | None = Field(default=None, max_length=40)
    severity: str | None = Field(default=None, pattern="^(CRITICAL|MAJOR|MINOR|OBSERVATION)$")
    root_cause: str | None = None
    correction: str | None = None
    owner_user_id: uuid.UUID | None = None
    due_at: datetime | None = None
    status: str | None = None
    process_name: str | None = Field(default=None, max_length=120)


class AuditFindingRead(APIModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID
    audit_id: uuid.UUID
    checklist_result_id: uuid.UUID | None
    department_id: uuid.UUID | None
    standard_id: uuid.UUID | None
    clause_id: uuid.UUID | None
    analyzer_id: uuid.UUID | None
    specimen_id: uuid.UUID | None
    lab_result_id: uuid.UUID | None
    worklist_item_id: uuid.UUID | None
    referenced_entity_type: str | None
    referenced_entity_id: str | None
    finding_number: str
    finding_type: str
    severity: str
    title: str
    description: str
    requirement: str | None
    root_cause: str | None
    correction: str | None
    corrective_action_required: bool
    preventive_action_required: bool
    owner_user_id: uuid.UUID | None
    due_at: datetime | None
    status: str
    closed_at: datetime | None
    verified_at: datetime | None
    process_name: str | None
    is_demo: bool
    created_at: datetime
    updated_at: datetime


class AuditCapaCreate(APIModel):
    capa_number: str | None = Field(default=None, max_length=40)
    root_cause: str | None = None
    immediate_correction: str | None = None
    corrective_action: str | None = None
    preventive_action: str | None = None
    owner_user_id: uuid.UUID | None = None
    priority: str = Field(default="MEDIUM", pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    due_at: datetime | None = None
    effectiveness_check_required: bool = True
    status: str = "OPEN"


class AuditCapaUpdate(APIModel):
    root_cause: str | None = None
    immediate_correction: str | None = None
    corrective_action: str | None = None
    preventive_action: str | None = None
    owner_user_id: uuid.UUID | None = None
    priority: str | None = Field(default=None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    due_at: datetime | None = None
    status: str | None = None
    effectiveness_verified: bool | None = None
    effectiveness_notes: str | None = None


class AuditCapaRead(APIModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    finding_id: uuid.UUID
    capa_number: str
    root_cause: str | None
    immediate_correction: str | None
    corrective_action: str | None
    preventive_action: str | None
    owner_user_id: uuid.UUID | None
    priority: str
    due_at: datetime | None
    status: str
    effectiveness_check_required: bool
    effectiveness_verified: bool
    effectiveness_notes: str | None
    verified_by: uuid.UUID | None
    verified_at: datetime | None
    closed_at: datetime | None
    is_demo: bool
    created_at: datetime
    updated_at: datetime


class AuditEvidenceCreate(APIModel):
    document_reference: str = Field(min_length=1, max_length=500)
    description: str | None = None
    finding_id: uuid.UUID | None = None
    capa_id: uuid.UUID | None = None
    version: str = "1"
    verification_status: str = Field(default="PENDING", pattern="^(PENDING|VERIFIED|REJECTED)$")


class AuditEvidenceRead(APIModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    audit_id: uuid.UUID | None
    finding_id: uuid.UUID | None
    capa_id: uuid.UUID | None
    document_reference: str
    description: str | None
    uploaded_by: uuid.UUID | None
    uploaded_at: datetime
    version: str
    verification_status: str
    verified_by: uuid.UUID | None
    verified_at: datetime | None
    is_demo: bool
    created_at: datetime


class AuditChecklistItemRead(APIModel):
    id: uuid.UUID
    checklist_id: uuid.UUID
    sequence: int
    section: str | None
    requirement: str
    question: str
    expected_evidence: str | None
    severity_if_failed: str
    applicable_department: str | None
    clause_id: uuid.UUID | None
    active: bool


class AuditChecklistRead(APIModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    audit_type: str
    version: str
    status: str
    description: str | None
    is_demo: bool
    items: list[AuditChecklistItemRead] = []


class AuditStandardRead(APIModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    code: str
    name: str
    version: str
    status: str
    is_demo: bool


class AuditClauseRead(APIModel):
    id: uuid.UUID
    standard_id: uuid.UUID
    parent_clause_id: uuid.UUID | None
    clause_code: str
    title: str
    description: str | None
    sequence: int
    active: bool
    is_demo: bool


class AuditNamedCountRead(APIModel):
    key: str
    label: str
    count: int
    value: float | None = None


class AuditTrendPointRead(APIModel):
    label: str
    audits: int
    findings: int
    compliance_percent: float | None = None


class AuditDashboardSummaryRead(APIModel):
    total_audits: int
    audits_this_month: int
    scheduled: int
    in_progress: int
    completed: int
    compliance_percent: float | None
    open_findings: int
    critical_findings: int
    major_findings: int
    minor_findings: int
    high_risk_findings: int
    overdue_capa: int
    evidence_pending: int
    closure_percent: float | None
    average_closure_days: float | None


class AuditDashboardAuditRowRead(APIModel):
    id: uuid.UUID
    audit_number: str
    audit_type: str
    lab_audit_subtype: str | None
    title: str
    scope: str | None
    process_name: str | None
    department_name: str | None
    audit_date: datetime | None
    auditor_name: str | None
    status: str
    findings: int
    open_findings: int
    compliance_percent: float | None
    capa_status: str
    is_demo: bool


class AuditAlertRead(APIModel):
    code: str
    severity: str
    message: str
    entity_type: str
    entity_id: str | None = None


class AuditDashboardRead(APIModel):
    audit_type: str
    window_start: datetime
    window_end: datetime
    summary: AuditDashboardSummaryRead
    trends: list[AuditTrendPointRead]
    findings_by_clause: list[AuditNamedCountRead]
    findings_by_department: list[AuditNamedCountRead]
    findings_by_severity: list[AuditNamedCountRead]
    findings_open_vs_closed: list[AuditNamedCountRead]
    compliance_by_department: list[AuditNamedCountRead]
    compliance_by_process: list[AuditNamedCountRead]
    capa_aging: list[AuditNamedCountRead]
    audits: list[AuditDashboardAuditRowRead]
    alerts: list[AuditAlertRead]
    query_batches: int
