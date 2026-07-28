import uuid

import pytest
from app.auth import AuthContext, get_auth_context
from app.config import Settings
from app.main import app
from app.models import (
    AuditEvent,
    Branch,
    LabOrder,
    Organization,
    Patient,
    PatientHistory,
    Permission,
    Role,
    TestCatalogItem,
    User,
)
from fastapi.testclient import TestClient
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


def test_environment_origin_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://admin.example.com,http://localhost:3000")
    assert Settings().cors_origins == ["https://admin.example.com", "http://localhost:3000"]


def test_returning_patient_is_updated_and_history_is_appended(
    client: TestClient, db: Session, context: AuthContext
) -> None:
    branch = Branch(
        organization_id=context.organization_id, name="Central", code="CENTRAL"
    )
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
