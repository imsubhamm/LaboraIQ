import uuid
from io import BytesIO

import app.api as api_module
import pytest
from app.auth import AuthContext, get_auth_context
from app.config import Settings
from app.main import app
from app.models import (
    AnalyzerConnectionEvent,
    AnalyzerWorklistItem,
    AuditEvent,
    Branch,
    LabOrder,
    Organization,
    Patient,
    PatientHistory,
    Permission,
    Role,
    Specimen,
    TestCatalogItem,
    TestCatalogParameter,
    User,
)
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session


def test_health_and_ready(client: TestClient) -> None:
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    assert client.get("/api/v1/ready").status_code == 200


def test_organization_read_and_update_are_audited(
    client: TestClient, db: Session, context: AuthContext
) -> None:
    response = client.get(f"/api/v1/organizations/{context.organization_id}")
    assert response.status_code == 200
    response = client.patch(
        f"/api/v1/organizations/{context.organization_id}", json={"name": "Alpha Labs Updated"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Alpha Labs Updated"
    event = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "organization.updated"))
    assert event is not None
    assert event.previous_value == {"name": "Alpha Labs", "status": "active"}


def test_branch_and_department_crud(client: TestClient, db: Session) -> None:
    branch = client.post(
        "/api/v1/branches",
        json={"name": "Central", "code": "CENTRAL", "time_zone": "Asia/Kolkata"},
    )
    assert branch.status_code == 201
    branch_id = branch.json()["id"]
    assert (
        client.patch(f"/api/v1/branches/{branch_id}", json={"name": "Central Lab"}).status_code
        == 200
    )
    department = client.post(
        "/api/v1/departments",
        json={"name": "Synthetic Department", "code": "SYN", "branch_id": branch_id},
    )
    assert department.status_code == 201
    assert client.get(f"/api/v1/departments/{department.json()['id']}").status_code == 200


def test_duplicate_branch_code_is_rejected(client: TestClient) -> None:
    payload = {"name": "Central", "code": "CENTRAL", "time_zone": "UTC"}
    assert client.post("/api/v1/branches", json=payload).status_code == 201
    assert client.post("/api/v1/branches", json=payload).status_code == 409


def test_user_crud_has_no_password_field(client: TestClient) -> None:
    response = client.post(
        "/api/v1/users",
        json={
            "email": "tech@alpha.example.com",
            "display_name": "Synthetic Technician",
            "auth_provider_id": "test:tech",
        },
    )
    assert response.status_code == 201
    assert "password" not in response.json()
    assert (
        client.patch(
            f"/api/v1/users/{response.json()['id']}", json={"status": "inactive"}
        ).status_code
        == 200
    )


def test_rbac_forbidden(client: TestClient, context: AuthContext) -> None:
    denied = AuthContext(
        user_id=context.user_id,
        organization_id=context.organization_id,
        email=context.email,
        branch_ids=frozenset(),
        permissions=frozenset({"branch.read"}),
        is_organization_scoped=True,
    )
    app.dependency_overrides[get_auth_context] = lambda: denied
    assert (
        client.post(
            "/api/v1/branches", json={"name": "Blocked", "code": "BLOCKED", "time_zone": "UTC"}
        ).status_code
        == 403
    )


def test_unauthorized_without_override(db: Session) -> None:
    app.dependency_overrides.pop(get_auth_context, None)
    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        assert client.get("/api/v1/branches").status_code == 401
    app.dependency_overrides.clear()


def test_tenant_isolation_returns_not_found(
    client: TestClient, db: Session, context: AuthContext
) -> None:
    other = Organization(name="Other Labs", code="OTHER")
    db.add(other)
    db.flush()
    branch = Branch(organization_id=other.id, name="Other Branch", code="OTHER")
    db.add(branch)
    db.commit()
    assert client.get(f"/api/v1/branches/{branch.id}").status_code == 404


def test_branch_isolation(client: TestClient, db: Session, context: AuthContext) -> None:
    branch = Branch(organization_id=context.organization_id, name="Restricted", code="RESTRICTED")
    db.add(branch)
    db.commit()
    scoped = AuthContext(
        user_id=context.user_id,
        organization_id=context.organization_id,
        email=context.email,
        branch_ids=frozenset(),
        permissions=frozenset({"branch.read"}),
        is_organization_scoped=False,
    )
    app.dependency_overrides[get_auth_context] = lambda: scoped
    assert client.get(f"/api/v1/branches/{branch.id}").status_code == 403


def test_role_assignment_and_deactivation(
    client: TestClient, db: Session, context: AuthContext
) -> None:
    permission = Permission(code="branch.read", description="Read branches")
    db.add(permission)
    role = Role(
        name="Synthetic Role", organization_id=context.organization_id, permissions=[permission]
    )
    user = User(
        organization_id=context.organization_id,
        email="assigned@alpha.test",
        display_name="Assigned User",
        auth_provider_id="test:assigned",
    )
    db.add_all([role, user])
    db.commit()
    response = client.post(
        "/api/v1/user-role-assignments",
        json={
            "user_id": str(user.id),
            "role_id": str(role.id),
            "assignment_reason": "Synthetic authorization test",
        },
    )
    assert response.status_code == 201
    assert (
        client.delete(f"/api/v1/user-role-assignments/{response.json()['id']}").status_code == 204
    )


def test_audit_event_is_immutable(client: TestClient, db: Session, context: AuthContext) -> None:
    client.patch(f"/api/v1/organizations/{context.organization_id}", json={"name": "Changed"})
    event = db.scalar(select(AuditEvent))
    assert event is not None
    event.action = "tampered"
    with pytest.raises(ValueError, match="immutable"):
        db.commit()
    db.rollback()
    assert client.put(f"/api/v1/audit-events/{event.id}", json={}).status_code == 405


def test_validation_error(client: TestClient) -> None:
    assert client.post("/api/v1/branches", json={"name": "x", "code": "bad"}).status_code == 422


def test_test_master_import_groups_panel_parameters_and_flags_placeholder_specimen(
    client: TestClient, db: Session
) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(
        [
            "Service Type",
            "Department",
            "Sub Department",
            "Service Code",
            "Service Name",
            "SPECIMEN",
            "PARAMETER CODE",
            "PARAMETER DESCRIPTION",
        ]
    )
    sheet.append(
        [
            "Pathology",
            "Laboratory",
            "Biochemistry",
            "BIO0077",
            "LIPID PROFILE",
            "Serum",
            "HDL",
            "hdl_external",
        ]
    )
    sheet.append(
        [
            "Pathology",
            "Laboratory",
            "Biochemistry",
            "BIO0077",
            "LIPID PROFILE",
            "Serum",
            "LDL",
            "ldl_external",
        ]
    )
    sheet.append(
        ["Pathology", "Laboratory", "Microbiology", "MIC001", "CULTURE", "specimen", "", ""]
    )
    sheet.append(["Pathology", "Laboratory", "Biochemistry", "", "MISSING CODE", "Serum", "", ""])
    content = BytesIO()
    workbook.save(content)

    response = client.post(
        "/api/v1/test-master/import",
        files={
            "file": (
                "test-master.xlsx",
                content.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200
    assert len(response.json()["errors"]) == 1
    assert response.json()["tests_created"] == 2
    assert response.json()["parameters_imported"] == 2
    assert response.json()["rows_rejected"] == 1
    assert response.json()["review_required"] == 1

    listing = client.get("/api/v1/test-master", params={"search": "BIO0077"})
    assert listing.status_code == 200
    item = listing.json()["items"][0]
    assert item["is_panel"] is True
    assert [parameter["name"] for parameter in item["parameters"]] == ["HDL", "LDL"]
    review = client.get("/api/v1/test-master", params={"review_only": "true"}).json()
    assert review["total"] == 1
    assert review["items"][0]["code"] == "MIC001"


def test_environment_origin_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://admin.example.com,http://localhost:3000")
    assert Settings().cors_origins == ["https://admin.example.com", "http://localhost:3000"]


def test_returning_patient_is_updated_and_history_is_appended(
    client: TestClient, db: Session, context: AuthContext
) -> None:
    branch = Branch(organization_id=context.organization_id, name="Central", code="CENTRAL")
    test = TestCatalogItem(
        organization_id=context.organization_id,
        code="CBC",
        name="Complete Blood Count",
        specimen_type="Whole blood",
        container_type="EDTA tube",
        price="450.00",
    )
    db.add_all([branch, test])
    db.commit()
    payload = {
        "full_name": "Returning Patient",
        "phone": "+919876543210",
        "email": "returning@example.com",
        "age_years": 35,
        "sex": "Female",
        "blood_group": "O+",
        "country": "India",
        "race": "Asian",
        "nationality": "Indian",
        "visit_type": "OP",
        "department": "Medicine",
        "ward": "OP Clinic",
        "doctor_name": "Dr Example",
        "diagnosis": "Z00.0 General examination",
        "additional_patient_data": {"MRN": "MRN-1001", "VIP Indicator": ""},
        "test_ids": [str(test.id)],
    }
    first = client.post("/api/v1/intake-workflows", json=payload)
    assert first.status_code == 201
    patient_id = first.json()["patient_id"]

    lookup = client.get("/api/v1/patients/lookup", params={"query": "+919876543210"})
    assert lookup.status_code == 200
    assert lookup.json()["id"] == patient_id
    assert lookup.json()["visit_count"] == 1
    assert lookup.json()["additional_patient_data"] == {"MRN": "MRN-1001"}

    name_lookup = client.get("/api/v1/patients/lookup", params={"query": "returning patient"})
    assert name_lookup.status_code == 200
    assert name_lookup.json()["id"] == patient_id

    partial_lookup = client.get("/api/v1/patients/lookup", params={"query": "returning"})
    assert partial_lookup.status_code == 200
    assert partial_lookup.json()["id"] == patient_id

    payload.update(
        {
            "patient_id": patient_id,
            "full_name": "Returning Patient Corrected",
            "diagnosis": "E11 Type 2 diabetes",
        }
    )
    second = client.post("/api/v1/intake-workflows", json=payload)
    assert second.status_code == 201
    assert second.json()["patient_id"] == patient_id
    assert db.query(Patient).count() == 1
    assert db.query(LabOrder).count() == 2
    assert db.query(PatientHistory).count() == 2
    assert db.get(Patient, uuid.UUID(patient_id)).full_name == "Returning Patient Corrected"

    directory = client.get("/api/v1/patients")
    assert directory.status_code == 200
    assert directory.json()["total"] == 1
    assert directory.json()["items"][0]["patient_number"].startswith("PT-")
    assert directory.json()["items"][0]["visit_count"] == 2

    payment = client.post(
        f"/api/v1/orders/{second.json()['order_id']}/payment",
        json={"payment_method": "CASH"},
    )
    assert payment.status_code == 200
    barcode = payment.json()["specimens"][0]["barcode"]
    worklist = client.get("/api/v1/specimens")
    assert worklist.status_code == 200
    assert worklist.json()["items"][0]["status"] == "awaiting_collection"

    collected = client.post(
        f"/api/v1/specimens/{barcode}/collect",
        json={"collection_location": "OP Collection", "container_count": 1},
    )
    assert collected.status_code == 200
    assert collected.json()["status"] == "collected"
    received = client.post(f"/api/v1/specimens/{barcode}/receive")
    assert received.status_code == 200
    assert received.json()["status"] == "received"
    assert received.json()["accession_number"].startswith("ACC-")
    accepted = client.post(f"/api/v1/specimens/{barcode}/decision", json={"decision": "accept"})
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    assert db.scalar(select(Specimen).where(Specimen.barcode == barcode)).reviewed_at is not None


def test_analyzer_configuration_is_branch_scoped_validated_and_audited(
    client: TestClient, db: Session, context: AuthContext
) -> None:
    branch = Branch(organization_id=context.organization_id, name="Central", code="CENTRAL")
    db.add(branch)
    db.commit()
    payload = {
        "branch_id": str(branch.id),
        "code": "HEM-01",
        "vendor": "Sysmex",
        "model": "XN-1000",
        "protocol": "ASTM",
        "host": "192.168.10.50",
        "port": 5000,
        "connection_mode": "bidirectional",
    }
    created = client.post("/api/v1/analyzers", json=payload)
    assert created.status_code == 201
    assert created.json()["host"] == "192.168.10.50"
    listing = client.get("/api/v1/analyzers")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    analyzer_id = created.json()["id"]
    updated = client.patch(f"/api/v1/analyzers/{analyzer_id}", json={"port": 5001})
    assert updated.status_code == 200
    assert updated.json()["port"] == 5001
    assert db.scalar(select(AuditEvent).where(AuditEvent.event_type == "analyzer.created"))
    invalid = {**payload, "code": "HEM-02", "host": "not-an-ip"}
    assert client.post("/api/v1/analyzers", json=invalid).status_code == 422


def test_analyzer_test_and_parameter_mapping_can_be_created_and_updated(
    client: TestClient, db: Session, context: AuthContext
) -> None:
    branch = Branch(organization_id=context.organization_id, name="Central", code="CENTRAL")
    test = TestCatalogItem(
        organization_id=context.organization_id,
        code="CBC",
        name="Complete Blood Count",
        specimen_type="Whole blood",
        container_type="EDTA",
        price="450.00",
    )
    db.add_all([branch, test])
    db.flush()
    parameter = TestCatalogParameter(
        test_id=test.id, name="Haemoglobin", external_code="HGB", display_order=1
    )
    db.add(parameter)
    db.commit()
    analyzer = client.post(
        "/api/v1/analyzers",
        json={
            "branch_id": str(branch.id),
            "code": "HEM-01",
            "vendor": "Sysmex",
            "model": "XN-1000",
            "protocol": "ASTM",
            "host": "192.168.10.50",
            "port": 5000,
            "connection_mode": "bidirectional",
        },
    ).json()
    payload = {
        "test_id": str(test.id),
        "machine_test_code": "cbc_order",
        "parameters": [
            {
                "parameter_id": str(parameter.id),
                "machine_parameter_code": "hgb_result",
                "unit": "g/dL",
            }
        ],
    }
    created = client.post(f"/api/v1/analyzers/{analyzer['id']}/mappings", json=payload)
    assert created.status_code == 201
    assert created.json()["machine_test_code"] == "CBC_ORDER"
    assert created.json()["parameters"][0]["machine_parameter_code"] == "HGB_RESULT"
    assert created.json()["parameters"][0]["unit"] == "g/dL"
    payload["machine_test_code"] = "CBC"
    updated = client.post(f"/api/v1/analyzers/{analyzer['id']}/mappings", json=payload)
    assert updated.status_code == 200
    listing = client.get(f"/api/v1/analyzers/{analyzer['id']}/mappings")
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["machine_test_code"] == "CBC"
    assert db.scalar(select(AuditEvent).where(AuditEvent.event_type == "analyzer.mapping_updated"))


def test_analyzer_connection_test_retries_updates_status_and_logs_events(
    client: TestClient,
    db: Session,
    context: AuthContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    branch = Branch(organization_id=context.organization_id, name="Central", code="CENTRAL")
    db.add(branch)
    db.commit()
    analyzer = client.post(
        "/api/v1/analyzers",
        json={
            "branch_id": str(branch.id),
            "code": "HEM-01",
            "vendor": "Sysmex",
            "model": "XN-1000",
            "protocol": "ASTM",
            "host": "192.168.10.50",
            "port": 5000,
            "connection_mode": "bidirectional",
            "connection_timeout_seconds": 2,
            "retry_limit": 1,
            "heartbeat_interval_seconds": 60,
        },
    ).json()
    calls = 0

    def fail_connection(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise ConnectionRefusedError("connection refused")

    monkeypatch.setattr(api_module.socket, "create_connection", fail_connection)
    failed = client.post(f"/api/v1/analyzers/{analyzer['id']}/connection-test")
    assert failed.status_code == 200
    assert failed.json()["success"] is False
    assert failed.json()["attempts"] == 2
    assert calls == 2
    assert db.query(AnalyzerConnectionEvent).count() == 2

    class ConnectedSocket:
        def __enter__(self) -> "ConnectedSocket":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(
        api_module.socket, "create_connection", lambda *args, **kwargs: ConnectedSocket()
    )
    connected = client.post(f"/api/v1/analyzers/{analyzer['id']}/heartbeat")
    assert connected.status_code == 200
    assert connected.json()["connection_status"] == "connected"
    events = client.get(f"/api/v1/analyzers/{analyzer['id']}/connection-events")
    assert events.status_code == 200
    assert events.json()[0]["event_type"] == "heartbeat"


def test_analyzer_connection_test_rejects_non_private_target(
    client: TestClient, db: Session, context: AuthContext
) -> None:
    branch = Branch(organization_id=context.organization_id, name="Central", code="CENTRAL")
    db.add(branch)
    db.commit()
    analyzer = client.post(
        "/api/v1/analyzers",
        json={
            "branch_id": str(branch.id),
            "code": "PUBLIC-01",
            "vendor": "Example",
            "model": "Public endpoint",
            "protocol": "PROPRIETARY",
            "host": "8.8.8.8",
            "port": 53,
            "connection_mode": "unidirectional",
        },
    ).json()
    response = client.post(f"/api/v1/analyzers/{analyzer['id']}/connection-test")
    assert response.status_code == 422


def test_analyzer_connection_test_allows_tailscale_target(
    client: TestClient,
    db: Session,
    context: AuthContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    branch = Branch(organization_id=context.organization_id, name="Central", code="CENTRAL")
    db.add(branch)
    db.commit()
    analyzer = client.post(
        "/api/v1/analyzers",
        json={
            "branch_id": str(branch.id),
            "code": "TAILSCALE-01",
            "vendor": "LaboraIQ",
            "model": "Mac Simulator",
            "protocol": "PROPRIETARY",
            "host": "100.122.201.68",
            "port": 55001,
            "connection_mode": "bidirectional",
            "retry_limit": 0,
        },
    ).json()

    class ConnectedSocket:
        def __enter__(self) -> "ConnectedSocket":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(
        api_module.socket, "create_connection", lambda *args, **kwargs: ConnectedSocket()
    )
    response = client.post(f"/api/v1/analyzers/{analyzer['id']}/connection-test")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_analyzer_mapping_can_be_deactivated_and_deleted(
    client: TestClient, db: Session, context: AuthContext
) -> None:
    branch = Branch(organization_id=context.organization_id, name="Central", code="CENTRAL")
    test = TestCatalogItem(
        organization_id=context.organization_id,
        code="BIO0231",
        name="Androstenedione Test",
        specimen_type="Serum",
        container_type="SST",
        price="900.00",
    )
    db.add_all([branch, test])
    db.commit()
    analyzer = client.post(
        "/api/v1/analyzers",
        json={
            "branch_id": str(branch.id),
            "code": "HEM-01",
            "vendor": "Sysmex",
            "model": "XN-1000",
            "protocol": "ASTM",
            "host": "192.168.10.50",
            "port": 5000,
            "connection_mode": "bidirectional",
        },
    ).json()
    created = client.post(
        f"/api/v1/analyzers/{analyzer['id']}/mappings",
        json={"test_id": str(test.id), "machine_test_code": "A4", "parameters": []},
    )
    assert created.status_code == 201
    mapping_id = created.json()["id"]
    deactivated = client.patch(
        f"/api/v1/analyzers/{analyzer['id']}/mappings/{mapping_id}",
        json={"status": "inactive"},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["status"] == "inactive"
    deleted = client.delete(f"/api/v1/analyzers/{analyzer['id']}/mappings/{mapping_id}")
    assert deleted.status_code == 204
    listing = client.get(f"/api/v1/analyzers/{analyzer['id']}/mappings")
    assert listing.status_code == 200
    assert listing.json() == []


def test_test_parameter_can_be_created_and_updated(
    client: TestClient, db: Session, context: AuthContext
) -> None:
    test = TestCatalogItem(
        organization_id=context.organization_id,
        code="BIO0231",
        name="Androstenedione Test",
        specimen_type="Serum",
        container_type="SST",
        price="900.00",
    )
    db.add(test)
    db.commit()
    created = client.post(
        f"/api/v1/test-master/{test.id}/parameters",
        json={
            "name": "Androstenedione",
            "external_code": "andro",
            "display_order": 1,
            "unit": "ng/mL",
            "reference_text": "Reference range pending clinical approval",
        },
    )
    assert created.status_code == 201
    assert created.json()["external_code"] == "ANDRO"
    assert created.json()["unit"] == "ng/mL"
    parameter_id = created.json()["id"]
    updated = client.patch(
        f"/api/v1/test-master/{test.id}/parameters/{parameter_id}",
        json={"reference_low": "0.3", "reference_high": "3.5"},
    )
    assert updated.status_code == 200
    assert updated.json()["reference_low"] == "0.3"
    assert updated.json()["reference_high"] == "3.5"


def test_accepting_specimen_creates_analyzer_worklist_item(
    client: TestClient, db: Session, context: AuthContext
) -> None:
    branch = Branch(organization_id=context.organization_id, name="Central", code="CENTRAL")
    test = TestCatalogItem(
        organization_id=context.organization_id,
        code="BIO0231",
        name="Androstenedione Test",
        specimen_type="Serum",
        container_type="SST",
        price="900.00",
    )
    db.add_all([branch, test])
    db.commit()
    analyzer = client.post(
        "/api/v1/analyzers",
        json={
            "branch_id": str(branch.id),
            "code": "MAC-UAT-01",
            "vendor": "LaboraIQ",
            "model": "Mac Simulator",
            "protocol": "HL7_LAW",
            "host": "192.168.10.80",
            "port": 55001,
            "connection_mode": "bidirectional",
        },
    ).json()
    mapped = client.post(
        f"/api/v1/analyzers/{analyzer['id']}/mappings",
        json={"test_id": str(test.id), "machine_test_code": "A4", "parameters": []},
    )
    assert mapped.status_code == 201

    intake = client.post(
        "/api/v1/intake-workflows",
        json={
            "full_name": "Worklist Patient",
            "phone": "+919811122233",
            "email": "worklist@example.com",
            "age_years": 30,
            "sex": "Female",
            "blood_group": "A+",
            "country": "India",
            "race": "Asian",
            "nationality": "Indian",
            "visit_type": "OP",
            "department": "Medicine",
            "ward": "OP Clinic",
            "doctor_name": "Dr Example",
            "diagnosis": "Z00.0",
            "test_ids": [str(test.id)],
        },
    )
    assert intake.status_code == 201
    payment = client.post(
        f"/api/v1/orders/{intake.json()['order_id']}/payment",
        json={"payment_method": "CASH"},
    )
    assert payment.status_code == 200
    barcode = payment.json()["specimens"][0]["barcode"]
    collected = client.post(
        f"/api/v1/specimens/{barcode}/collect",
        json={"collection_location": "OP", "container_count": 1},
    )
    assert collected.status_code == 200
    assert client.post(f"/api/v1/specimens/{barcode}/receive").status_code == 200
    accepted = client.post(
        f"/api/v1/specimens/{barcode}/decision",
        json={"decision": "accept"},
    )
    assert accepted.status_code == 200
    assert db.query(AnalyzerWorklistItem).count() == 1
    worklist = client.get("/api/v1/analyzer-worklist", params={"status": "pending"})
    assert worklist.status_code == 200
    assert worklist.json()["total"] == 1
    item = worklist.json()["items"][0]
    assert item["lis_test_code"] == "BIO0231"
    assert item["machine_test_code"] == "A4"
    assert item["analyzer_code"] == "MAC-UAT-01"
    enqueued = client.post(f"/api/v1/analyzer-worklist/{item['id']}/enqueue")
    assert enqueued.status_code == 200
    assert enqueued.json()["status"] == "queued"
    cancelled = client.post(
        f"/api/v1/analyzer-worklist/{item['id']}/cancel",
        json={"reason": "UAT stop"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_order_queue_sends_stub_payload_retries_then_fails(
    client: TestClient,
    db: Session,
    context: AuthContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    branch = Branch(organization_id=context.organization_id, name="Central", code="CENTRAL")
    test = TestCatalogItem(
        organization_id=context.organization_id,
        code="BIO0231",
        name="Androstenedione Test",
        specimen_type="Serum",
        container_type="SST",
        price="900.00",
    )
    db.add_all([branch, test])
    db.commit()
    analyzer = client.post(
        "/api/v1/analyzers",
        json={
            "branch_id": str(branch.id),
            "code": "MAC-UAT-01",
            "vendor": "LaboraIQ",
            "model": "Mac Simulator",
            "protocol": "HL7_LAW",
            "host": "192.168.10.80",
            "port": 55001,
            "connection_mode": "bidirectional",
            "retry_limit": 1,
        },
    ).json()
    assert (
        client.post(
            f"/api/v1/analyzers/{analyzer['id']}/mappings",
            json={"test_id": str(test.id), "machine_test_code": "A4", "parameters": []},
        ).status_code
        == 201
    )
    intake = client.post(
        "/api/v1/intake-workflows",
        json={
            "full_name": "Queue Patient",
            "phone": "+919811122244",
            "email": "queue@example.com",
            "age_years": 30,
            "sex": "Female",
            "blood_group": "A+",
            "country": "India",
            "race": "Asian",
            "nationality": "Indian",
            "visit_type": "OP",
            "department": "Medicine",
            "ward": "OP Clinic",
            "doctor_name": "Dr Example",
            "diagnosis": "Z00.0",
            "test_ids": [str(test.id)],
        },
    )
    assert intake.status_code == 201
    payment = client.post(
        f"/api/v1/orders/{intake.json()['order_id']}/payment",
        json={"payment_method": "CASH"},
    )
    barcode = payment.json()["specimens"][0]["barcode"]
    assert (
        client.post(
            f"/api/v1/specimens/{barcode}/collect",
            json={"collection_location": "OP", "container_count": 1},
        ).status_code
        == 200
    )
    assert client.post(f"/api/v1/specimens/{barcode}/receive").status_code == 200
    assert (
        client.post(
            f"/api/v1/specimens/{barcode}/decision", json={"decision": "accept"}
        ).status_code
        == 200
    )
    worklist = client.get("/api/v1/analyzer-worklist", params={"status": "pending"}).json()
    item_id = worklist["items"][0]["id"]
    assert client.post(f"/api/v1/analyzer-worklist/{item_id}/enqueue").status_code == 200

    calls = {"n": 0}

    def fail_send(analyzer_obj, payload: str, **kwargs):
        calls["n"] += 1
        return False, "connection refused", []

    import app.analyzer_orders as orders

    monkeypatch.setattr(orders, "send_order_over_tcp", fail_send)
    first = client.post("/api/v1/analyzer-orders/process?limit=5")
    assert first.status_code == 200
    assert first.json()["processed"] == 1
    assert first.json()["attempts"][0]["state"] == "failed"
    # retry was auto-queued
    second = client.post("/api/v1/analyzer-orders/process?limit=5")
    assert second.status_code == 200
    assert second.json()["processed"] == 1
    assert second.json()["attempts"][0]["state"] == "failed"
    assert calls["n"] == 2
    failed_item = client.get("/api/v1/analyzer-worklist").json()["items"][0]
    assert failed_item["status"] == "failed"
    attempts = client.get("/api/v1/analyzer-orders/attempts", params={"worklist_item_id": item_id})
    assert attempts.status_code == 200
    assert attempts.json()["total"] == 2


def test_order_queue_marks_acknowledged_on_tcp_success(
    client: TestClient,
    db: Session,
    context: AuthContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    branch = Branch(organization_id=context.organization_id, name="Central", code="CENTRAL")
    test = TestCatalogItem(
        organization_id=context.organization_id,
        code="BIO0231",
        name="Androstenedione Test",
        specimen_type="Serum",
        container_type="SST",
        price="900.00",
    )
    db.add_all([branch, test])
    db.commit()
    analyzer = client.post(
        "/api/v1/analyzers",
        json={
            "branch_id": str(branch.id),
            "code": "MAC-STUB-01",
            "vendor": "LaboraIQ",
            "model": "Stub Simulator",
            "protocol": "PROPRIETARY",
            "host": "192.168.10.80",
            "port": 55001,
            "connection_mode": "bidirectional",
            "retry_limit": 0,
        },
    ).json()
    assert (
        client.post(
            f"/api/v1/analyzers/{analyzer['id']}/mappings",
            json={"test_id": str(test.id), "machine_test_code": "A4", "parameters": []},
        ).status_code
        == 201
    )
    intake = client.post(
        "/api/v1/intake-workflows",
        json={
            "full_name": "Ack Patient",
            "phone": "+919811122255",
            "email": "ack@example.com",
            "age_years": 30,
            "sex": "Male",
            "blood_group": "B+",
            "country": "India",
            "race": "Asian",
            "nationality": "Indian",
            "visit_type": "OP",
            "department": "Medicine",
            "ward": "OP Clinic",
            "doctor_name": "Dr Example",
            "diagnosis": "Z00.0",
            "test_ids": [str(test.id)],
        },
    ).json()
    barcode = client.post(
        f"/api/v1/orders/{intake['order_id']}/payment", json={"payment_method": "CASH"}
    ).json()["specimens"][0]["barcode"]
    client.post(
        f"/api/v1/specimens/{barcode}/collect",
        json={"collection_location": "OP", "container_count": 1},
    )
    client.post(f"/api/v1/specimens/{barcode}/receive")
    client.post(f"/api/v1/specimens/{barcode}/decision", json={"decision": "accept"})
    item_id = client.get("/api/v1/analyzer-worklist", params={"status": "pending"}).json()["items"][
        0
    ]["id"]
    client.post(f"/api/v1/analyzer-worklist/{item_id}/enqueue")

    import app.analyzer_orders as orders

    monkeypatch.setattr(
        orders,
        "send_order_over_tcp",
        lambda analyzer_obj, payload, **kwargs: (True, "TCP order payload delivered", []),
    )
    processed = client.post("/api/v1/analyzer-orders/process")
    assert processed.status_code == 200
    assert processed.json()["attempts"][0]["state"] == "acknowledged"
    assert processed.json()["attempts"][0]["payload_hash"]
    item = client.get("/api/v1/analyzer-worklist").json()["items"][0]
    assert item["status"] == "completed"
    assert item["latest_attempt_state"] == "acknowledged"


def test_hl7_law_order_requires_ack_and_stores_oru(
    client: TestClient,
    db: Session,
    context: AuthContext,
) -> None:
    import importlib.util
    import socket
    import threading
    import uuid as uuid_mod
    from pathlib import Path

    from app.models import AnalyzerMessage
    from sqlalchemy import select

    simulator_path = Path(__file__).resolve().parents[3] / "tools" / "analyzer_tcp_simulator.py"
    spec = importlib.util.spec_from_file_location("analyzer_tcp_simulator", simulator_path)
    assert spec and spec.loader
    simulator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(simulator)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    port = server.getsockname()[1]
    server.listen()
    stop = threading.Event()

    def serve() -> None:
        server.settimeout(0.5)
        while not stop.is_set():
            try:
                connection, _ = server.accept()
            except TimeoutError:
                continue
            simulator.handle_connection(
                connection,
                peer="127.0.0.1:test",
                analyzer_code="MAC-UAT-01",
                expected_barcode=None,
                expected_test_code="A4",
                send_result=True,
                result_value="1.8",
                result_unit="ng/mL",
                observation_code="ANDRO",
                timeout=2.0,
            )

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        branch = Branch(organization_id=context.organization_id, name="Central", code="CENTRAL")
        test = TestCatalogItem(
            organization_id=context.organization_id,
            code="BIO0231",
            name="Androstenedione Test",
            specimen_type="Serum",
            container_type="SST",
            price="900.00",
        )
        db.add_all([branch, test])
        db.commit()
        analyzer = client.post(
            "/api/v1/analyzers",
            json={
                "branch_id": str(branch.id),
                "code": "MAC-UAT-01",
                "vendor": "LaboraIQ",
                "model": "Mac Simulator",
                "protocol": "HL7_LAW",
                "host": "127.0.0.1",
                "port": port,
                "connection_mode": "bidirectional",
                "connection_timeout_seconds": 3,
                "retry_limit": 0,
            },
        ).json()
        assert (
            client.post(
                f"/api/v1/analyzers/{analyzer['id']}/mappings",
                json={"test_id": str(test.id), "machine_test_code": "A4", "parameters": []},
            ).status_code
            == 201
        )
        intake = client.post(
            "/api/v1/intake-workflows",
            json={
                "full_name": "HL7 Patient",
                "phone": "+919811122266",
                "email": "hl7@example.com",
                "age_years": 30,
                "sex": "Female",
                "blood_group": "O+",
                "country": "India",
                "race": "Asian",
                "nationality": "Indian",
                "visit_type": "OP",
                "department": "Medicine",
                "ward": "OP Clinic",
                "doctor_name": "Dr Example",
                "diagnosis": "Z00.0",
                "test_ids": [str(test.id)],
            },
        ).json()
        barcode = client.post(
            f"/api/v1/orders/{intake['order_id']}/payment", json={"payment_method": "CASH"}
        ).json()["specimens"][0]["barcode"]
        client.post(
            f"/api/v1/specimens/{barcode}/collect",
            json={"collection_location": "OP", "container_count": 1},
        )
        client.post(f"/api/v1/specimens/{barcode}/receive")
        client.post(f"/api/v1/specimens/{barcode}/decision", json={"decision": "accept"})
        item_id = client.get("/api/v1/analyzer-worklist", params={"status": "pending"}).json()[
            "items"
        ][0]["id"]
        assert client.post(f"/api/v1/analyzer-worklist/{item_id}/enqueue").status_code == 200
        processed = client.post("/api/v1/analyzer-orders/process")
        assert processed.status_code == 200
        attempt = processed.json()["attempts"][0]
        assert attempt["state"] == "acknowledged"
        assert attempt["error"] is None
        item = client.get("/api/v1/analyzer-worklist").json()["items"][0]
        assert item["status"] == "normalized"
        rows = list(
            db.scalars(
                select(AnalyzerMessage).where(
                    AnalyzerMessage.worklist_item_id == uuid_mod.UUID(item_id)
                )
            ).all()
        )
        assert any("OML^O33" in row.body for row in rows if row.direction == "outbound")
        assert any("MSA|AA|" in row.body for row in rows if row.direction == "inbound")
        assert any("ORU^R01" in row.body for row in rows if row.direction == "inbound")
        results = client.get("/api/v1/results", params={"status": "pending_review"})
        assert results.status_code == 200
        assert results.json()["total"] >= 1
        result = results.json()["items"][0]
        assert result["observations"]
        assert result["observations"][0]["machine_parameter_code"] == "ANDRO"
        assert result["observations"][0]["value"] == "1.8"
        reviewed = client.post(
            f"/api/v1/results/{result['id']}/technical-review",
            json={"notes": "Looks consistent"},
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["status"] == "technically_reviewed"
        validated = client.post(
            f"/api/v1/results/{result['id']}/pathologist-validate",
            json={"notes": "Approved"},
        )
        assert validated.status_code == 200
        released = client.post(f"/api/v1/results/{result['id']}/release")
        assert released.status_code == 200
        assert released.json()["status"] == "released"
        assert released.json()["report_number"]
        pdf = client.get(f"/api/v1/results/{result['id']}/pdf")
        assert pdf.status_code == 200
        assert pdf.headers["content-type"].startswith("application/pdf")
        assert pdf.content[:4] == b"%PDF"
    finally:
        stop.set()
        server.close()
        thread.join(timeout=2)


def test_hl7_law_nak_fails_attempt(
    client: TestClient,
    db: Session,
    context: AuthContext,
) -> None:
    import importlib.util
    import socket
    import threading
    from pathlib import Path

    simulator_path = Path(__file__).resolve().parents[3] / "tools" / "analyzer_tcp_simulator.py"
    spec = importlib.util.spec_from_file_location("analyzer_tcp_simulator", simulator_path)
    assert spec and spec.loader
    simulator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(simulator)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    port = server.getsockname()[1]
    server.listen()
    stop = threading.Event()

    def serve() -> None:
        server.settimeout(0.5)
        while not stop.is_set():
            try:
                connection, _ = server.accept()
            except TimeoutError:
                continue
            simulator.handle_connection(
                connection,
                peer="127.0.0.1:test",
                analyzer_code="MAC-UAT-01",
                expected_barcode=None,
                expected_test_code="WRONG",
                send_result=False,
                result_value="1.8",
                result_unit="ng/mL",
                observation_code="ANDRO",
                timeout=2.0,
            )

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        branch = Branch(organization_id=context.organization_id, name="Central", code="CENTRAL")
        test = TestCatalogItem(
            organization_id=context.organization_id,
            code="BIO0231",
            name="Androstenedione Test",
            specimen_type="Serum",
            container_type="SST",
            price="900.00",
        )
        db.add_all([branch, test])
        db.commit()
        analyzer = client.post(
            "/api/v1/analyzers",
            json={
                "branch_id": str(branch.id),
                "code": "MAC-NAK-01",
                "vendor": "LaboraIQ",
                "model": "Mac Simulator",
                "protocol": "HL7_LAW",
                "host": "127.0.0.1",
                "port": port,
                "connection_mode": "bidirectional",
                "connection_timeout_seconds": 3,
                "retry_limit": 0,
            },
        ).json()
        client.post(
            f"/api/v1/analyzers/{analyzer['id']}/mappings",
            json={"test_id": str(test.id), "machine_test_code": "A4", "parameters": []},
        )
        intake = client.post(
            "/api/v1/intake-workflows",
            json={
                "full_name": "NAK Patient",
                "phone": "+919811122277",
                "email": "nak@example.com",
                "age_years": 30,
                "sex": "Male",
                "blood_group": "A+",
                "country": "India",
                "race": "Asian",
                "nationality": "Indian",
                "visit_type": "OP",
                "department": "Medicine",
                "ward": "OP Clinic",
                "doctor_name": "Dr Example",
                "diagnosis": "Z00.0",
                "test_ids": [str(test.id)],
            },
        ).json()
        barcode = client.post(
            f"/api/v1/orders/{intake['order_id']}/payment", json={"payment_method": "CASH"}
        ).json()["specimens"][0]["barcode"]
        client.post(
            f"/api/v1/specimens/{barcode}/collect",
            json={"collection_location": "OP", "container_count": 1},
        )
        client.post(f"/api/v1/specimens/{barcode}/receive")
        client.post(f"/api/v1/specimens/{barcode}/decision", json={"decision": "accept"})
        item_id = client.get("/api/v1/analyzer-worklist", params={"status": "pending"}).json()[
            "items"
        ][0]["id"]
        client.post(f"/api/v1/analyzer-worklist/{item_id}/enqueue")
        processed = client.post("/api/v1/analyzer-orders/process")
        assert processed.status_code == 200
        attempt = processed.json()["attempts"][0]
        assert attempt["state"] == "failed"
        assert attempt["error"] and "HL7 NAK AE" in attempt["error"]
        item = client.get("/api/v1/analyzer-worklist").json()["items"][0]
        assert item["status"] == "failed"
    finally:
        stop.set()
        server.close()
        thread.join(timeout=2)
