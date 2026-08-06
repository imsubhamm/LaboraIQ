import enum
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
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


class Analyzer(Base, TimestampMixin):
    __tablename__ = "analyzers"
    __table_args__ = (
        UniqueConstraint("organization_id", "branch_id", "code", name="uq_analyzer_scope_code"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    vendor: Mapped[str] = mapped_column(String(120))
    model: Mapped[str] = mapped_column(String(120))
    protocol: Mapped[str] = mapped_column(String(30))
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer)
    connection_mode: Mapped[str] = mapped_column(String(20), default="bidirectional")
    connection_status: Mapped[str] = mapped_column(String(30), default="never_tested")
    connection_timeout_seconds: Mapped[int] = mapped_column(Integer, default=3)
    retry_limit: Mapped[int] = mapped_column(Integer, default=2)
    heartbeat_interval_seconds: Mapped[int] = mapped_column(Integer, default=60)
    last_connection_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_connection_error: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.active)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class AnalyzerConnectionEvent(Base):
    __tablename__ = "analyzer_connection_events"
    __table_args__ = (Index("ix_analyzer_connection_events_recent", "analyzer_id", "occurred_at"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), index=True)
    analyzer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analyzers.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    attempt: Mapped[int] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(String(500))
    correlation_id: Mapped[str] = mapped_column(String(100), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AnalyzerTestMapping(Base, TimestampMixin):
    __tablename__ = "analyzer_test_mappings"
    __table_args__ = (
        UniqueConstraint("analyzer_id", "test_id", name="uq_analyzer_test_mapping"),
        UniqueConstraint("analyzer_id", "machine_test_code", name="uq_analyzer_machine_test_code"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    analyzer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analyzers.id", ondelete="CASCADE"), index=True
    )
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_catalog_items.id"), index=True)
    machine_test_code: Mapped[str] = mapped_column(String(100))
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.active)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    parameters: Mapped[list["AnalyzerParameterMapping"]] = relationship(
        back_populates="test_mapping", cascade="all, delete-orphan", lazy="selectin"
    )


class AnalyzerParameterMapping(Base, TimestampMixin):
    __tablename__ = "analyzer_parameter_mappings"
    __table_args__ = (
        UniqueConstraint("test_mapping_id", "parameter_id", name="uq_mapping_parameter"),
        UniqueConstraint(
            "test_mapping_id", "machine_parameter_code", name="uq_mapping_machine_parameter"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    test_mapping_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analyzer_test_mappings.id", ondelete="CASCADE"), index=True
    )
    parameter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_catalog_parameters.id"), index=True
    )
    machine_parameter_code: Mapped[str] = mapped_column(String(100))
    unit: Mapped[str | None] = mapped_column(String(40))
    test_mapping: Mapped[AnalyzerTestMapping] = relationship(back_populates="parameters")


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


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("organization_id", "patient_number", name="uq_patient_number"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    patient_number: Mapped[str] = mapped_column(String(40))
    full_name: Mapped[str] = mapped_column(String(200))
    date_of_birth: Mapped[date | None]
    age_years: Mapped[int | None] = mapped_column(Integer)
    sex: Mapped[str | None] = mapped_column(String(30))
    phone: Mapped[str] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(320))
    address: Mapped[str | None] = mapped_column(Text)
    blood_group: Mapped[str | None] = mapped_column(String(10))
    country: Mapped[str | None] = mapped_column(String(100))
    race: Mapped[str | None] = mapped_column(String(100))
    nationality: Mapped[str | None] = mapped_column(String(100))
    additional_patient_data: Mapped[dict[str, str] | None] = mapped_column(JSON)


class PatientHistory(Base):
    """Immutable demographic snapshot recorded for every patient visit."""

    __tablename__ = "patient_history"
    __table_args__ = (Index("ix_patient_history_patient_recorded", "patient_id", "recorded_at"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lab_orders.id"), index=True)
    demographics: Mapped[dict[str, Any]] = mapped_column(JSON)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TestCatalogItem(Base, TimestampMixin):
    __tablename__ = "test_catalog_items"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_test_catalog_code"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    service_type: Mapped[str] = mapped_column(String(80), default="Pathology")
    department: Mapped[str] = mapped_column(String(120), default="Laboratory")
    sub_department: Mapped[str] = mapped_column(String(120), default="")
    specimen_type: Mapped[str] = mapped_column(String(80))
    container_type: Mapped[str] = mapped_column(String(100))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    is_panel: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_status: Mapped[str] = mapped_column(String(30), default="validated")
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.active)
    parameters: Mapped[list["TestCatalogParameter"]] = relationship(
        back_populates="test", cascade="all, delete-orphan", lazy="selectin"
    )


class TestCatalogParameter(Base, TimestampMixin):
    __tablename__ = "test_catalog_parameters"
    __table_args__ = (
        UniqueConstraint("test_id", "external_code", name="uq_test_parameter_external_code"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    test_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_catalog_items.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    external_code: Mapped[str] = mapped_column(String(255))
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    unit: Mapped[str | None] = mapped_column(String(40))
    reference_low: Mapped[str | None] = mapped_column(String(40))
    reference_high: Mapped[str | None] = mapped_column(String(40))
    reference_text: Mapped[str | None] = mapped_column(String(200))
    critical_low: Mapped[str | None] = mapped_column(String(40))
    critical_high: Mapped[str | None] = mapped_column(String(40))
    reference_source: Mapped[str | None] = mapped_column(String(200))
    test: Mapped[TestCatalogItem] = relationship(back_populates="parameters")


class AnalyzerWorklistItem(Base, TimestampMixin):
    __tablename__ = "analyzer_worklist_items"
    __table_args__ = (
        UniqueConstraint(
            "specimen_id",
            "analyzer_id",
            "test_id",
            name="uq_worklist_specimen_analyzer_test",
        ),
        Index("ix_worklist_status_created", "organization_id", "status", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), index=True)
    specimen_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("specimens.id"), index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_orders.id"), index=True)
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_catalog_items.id"), index=True)
    analyzer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyzers.id"), index=True)
    mapping_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analyzer_test_mappings.id"), index=True
    )
    machine_test_code: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    correlation_id: Mapped[str] = mapped_column(String(100), index=True)
    cancelled_reason: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class AnalyzerMessage(Base):
    __tablename__ = "analyzer_messages"
    __table_args__ = (
        Index("ix_analyzer_messages_correlation", "organization_id", "correlation_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    analyzer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyzers.id"), index=True)
    worklist_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analyzer_worklist_items.id"), index=True
    )
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    direction: Mapped[str] = mapped_column(String(20))  # outbound | inbound
    content_type: Mapped[str] = mapped_column(String(80), default="text/plain")
    body: Mapped[str] = mapped_column(Text)
    payload_hash: Mapped[str] = mapped_column(String(64), index=True)
    correlation_id: Mapped[str] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AnalyzerOrderAttempt(Base, TimestampMixin):
    __tablename__ = "analyzer_order_attempts"
    __table_args__ = (
        Index("ix_order_attempts_queue", "organization_id", "state", "created_at"),
        UniqueConstraint("worklist_item_id", "attempt_no", name="uq_worklist_attempt_no"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), index=True)
    worklist_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analyzer_worklist_items.id"), index=True
    )
    analyzer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyzers.id"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    correlation_id: Mapped[str] = mapped_column(String(100), index=True)
    payload_hash: Mapped[str | None] = mapped_column(String(64))
    request_message_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("analyzer_messages.id"))
    response_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analyzer_messages.id")
    )
    error: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class LabResult(Base, TimestampMixin):
    """Normalized result set derived from an analyzer ORU (or equivalent)."""

    __tablename__ = "lab_results"
    __table_args__ = (
        UniqueConstraint("worklist_item_id", name="uq_lab_result_worklist_item"),
        Index("ix_lab_results_status_created", "organization_id", "status", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), index=True)
    worklist_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analyzer_worklist_items.id"), index=True
    )
    specimen_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("specimens.id"), index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_orders.id"), index=True)
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_catalog_items.id"), index=True)
    analyzer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyzers.id"), index=True)
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analyzer_messages.id"), index=True
    )
    correlation_id: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(40), default="pending_review", index=True)
    technical_reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    technical_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    technical_review_notes: Mapped[str | None] = mapped_column(String(500))
    pathologist_validated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    pathologist_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pathologist_notes: Mapped[str | None] = mapped_column(String(500))
    released_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    report_number: Mapped[str | None] = mapped_column(String(40), index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    observations: Mapped[list["LabResultObservation"]] = relationship(
        back_populates="result", cascade="all, delete-orphan", lazy="selectin"
    )


class LabResultObservation(Base, TimestampMixin):
    __tablename__ = "lab_result_observations"
    __table_args__ = (
        UniqueConstraint("result_id", "sequence_no", name="uq_result_observation_sequence"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lab_results.id", ondelete="CASCADE"), index=True
    )
    sequence_no: Mapped[int] = mapped_column(Integer)
    parameter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_catalog_parameters.id"), index=True
    )
    machine_parameter_code: Mapped[str] = mapped_column(String(100))
    parameter_name: Mapped[str] = mapped_column(String(200))
    value: Mapped[str] = mapped_column(String(200))
    unit: Mapped[str | None] = mapped_column(String(40))
    reference_low: Mapped[str | None] = mapped_column(String(40))
    reference_high: Mapped[str | None] = mapped_column(String(40))
    reference_text: Mapped[str | None] = mapped_column(String(200))
    flag: Mapped[str | None] = mapped_column(String(20))
    raw_obx: Mapped[str | None] = mapped_column(Text)
    result: Mapped[LabResult] = relationship(back_populates="observations")


class LabOrder(Base, TimestampMixin):
    __tablename__ = "lab_orders"
    __table_args__ = (UniqueConstraint("organization_id", "order_number", name="uq_order_number"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    order_number: Mapped[str] = mapped_column(String(40))
    visit_type: Mapped[str] = mapped_column(String(20))
    department: Mapped[str | None] = mapped_column(String(120))
    ward: Mapped[str | None] = mapped_column(String(120))
    doctor_name: Mapped[str] = mapped_column(String(200))
    diagnosis: Mapped[str | None] = mapped_column(Text)
    prescription_filename: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="registered")


class OrderTest(Base):
    __tablename__ = "order_tests"
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_orders.id"), primary_key=True)
    test_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_catalog_items.id"), primary_key=True
    )
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("organization_id", "invoice_number", name="uq_invoice_number"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_orders.id"), unique=True)
    invoice_number: Mapped[str] = mapped_column(String(40))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    payment_status: Mapped[str] = mapped_column(String(30), default="pending")
    payment_method: Mapped[str | None] = mapped_column(String(20))
    transaction_id: Mapped[str | None] = mapped_column(String(120))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Specimen(Base, TimestampMixin):
    __tablename__ = "specimens"
    __table_args__ = (UniqueConstraint("organization_id", "barcode", name="uq_specimen_barcode"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_orders.id"), index=True)
    barcode: Mapped[str] = mapped_column(String(60))
    specimen_type: Mapped[str] = mapped_column(String(80))
    container_type: Mapped[str] = mapped_column(String(100))
    laboratory_department: Mapped[str | None] = mapped_column(String(120), index=True)
    accession_number: Mapped[str | None] = mapped_column(String(60), index=True)
    collection_location: Mapped[str | None] = mapped_column(String(200))
    container_count: Mapped[int] = mapped_column(Integer, default=1)
    collection_notes: Mapped[str | None] = mapped_column(Text)
    collected_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(String(120))
    rejection_notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="awaiting_collection")
