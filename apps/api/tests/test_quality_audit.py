"""Quality audit domain: compliance, workflows, dashboard, org isolation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.auth import AuthContext
from app.models import (
    AuditCapa,
    AuditCheckResult,
    AuditFinding,
    Branch,
    Organization,
    QualityAudit,
    User,
)
from app.quality_audit import (
    apply_audit_status,
    apply_capa_status,
    apply_finding_status,
    compliance_percent,
    get_audit_dashboard,
)
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def _context(org_id, branch_ids, user_id) -> AuthContext:
    return AuthContext(
        user_id=user_id,
        organization_id=org_id,
        email="admin@dev.labora.local",
        branch_ids=frozenset(branch_ids),
        permissions=frozenset({"quality_audit.read", "quality_audit.manage"}),
        is_organization_scoped=True,
    )


def test_compliance_percent_excludes_not_applicable() -> None:
    results = [
        AuditCheckResult(result="COMPLIANT"),
        AuditCheckResult(result="NON_COMPLIANT"),
        AuditCheckResult(result="NOT_APPLICABLE"),
    ]
    assert compliance_percent(results) == 50.0
    assert compliance_percent([]) is None


def test_audit_and_capa_transitions() -> None:
    audit = QualityAudit(status="DRAFT")
    apply_audit_status(audit, "SCHEDULED")
    apply_audit_status(audit, "IN_PROGRESS")
    assert audit.started_at is not None
    apply_audit_status(audit, "COMPLETED")
    apply_audit_status(audit, "CLOSED")
    assert audit.closed_at is not None

    finding = AuditFinding(status="OPEN")
    apply_finding_status(finding, "CAPA_ASSIGNED")
    apply_finding_status(finding, "CLOSED")
    assert finding.closed_at is not None

    capa = AuditCapa(status="OPEN", effectiveness_check_required=True)
    context = _context(uuid4(), [], uuid4())
    apply_capa_status(capa, "ACTION_IN_PROGRESS", context)
    apply_capa_status(capa, "CLOSED", context)
    assert capa.status == "CLOSED"
    assert capa.effectiveness_verified is True


def test_invalid_audit_transition_rejected() -> None:
    audit = QualityAudit(status="CLOSED")
    try:
        apply_audit_status(audit, "DRAFT")
        raise AssertionError("expected HTTPException")
    except HTTPException as error:
        assert error.status_code == 400


def test_dashboard_nabl_and_internal_separation(
    db: Session, client: TestClient, context: AuthContext
) -> None:
    org = db.get(Organization, context.organization_id)
    assert org is not None
    branch = Branch(
        organization_id=org.id,
        code="QA1",
        name="Quality Branch",
        time_zone="Asia/Kolkata",
    )
    db.add(branch)
    db.flush()
    user = db.get(User, context.user_id)
    assert user is not None
    now = datetime.now(UTC)
    nabl = QualityAudit(
        organization_id=org.id,
        branch_id=branch.id,
        audit_number=f"T-NABL-{uuid4().hex[:6]}",
        audit_type="NABL",
        title="Test NABL",
        planned_start_at=now - timedelta(days=1),
        status="IN_PROGRESS",
        is_demo=True,
        auditor_user_id=user.id,
    )
    internal = QualityAudit(
        organization_id=org.id,
        branch_id=branch.id,
        audit_number=f"T-LAB-{uuid4().hex[:6]}",
        audit_type="INTERNAL",
        title="Test LAB",
        planned_start_at=now - timedelta(days=1),
        status="SCHEDULED",
        is_demo=True,
        auditor_user_id=user.id,
    )
    db.add_all([nabl, internal])
    db.commit()

    auth = _context(org.id, [branch.id], user.id)
    nabl_dash = get_audit_dashboard(db, auth, audit_type="NABL")
    lab_dash = get_audit_dashboard(db, auth, audit_type="INTERNAL")
    assert any(row.audit_number == nabl.audit_number for row in nabl_dash.audits)
    assert all(row.audit_type == "NABL" for row in nabl_dash.audits)
    assert any(row.audit_number == internal.audit_number for row in lab_dash.audits)
    assert all(row.audit_type == "INTERNAL" for row in lab_dash.audits)

    response = client.get("/api/v1/audit-dashboard?audit_type=NABL")
    assert response.status_code == 200
    body = response.json()
    assert "summary" in body
    assert "audits" in body
    assert "alerts" in body
    assert body["audit_type"] == "NABL"


def test_create_audit_finding_capa_api(
    client: TestClient, db: Session, context: AuthContext
) -> None:
    branch = Branch(
        organization_id=context.organization_id,
        code="QA2",
        name="API Branch",
        time_zone="Asia/Kolkata",
    )
    db.add(branch)
    db.commit()
    create = client.post(
        "/api/v1/audits",
        json={
            "branch_id": str(branch.id),
            "audit_type": "INTERNAL",
            "title": "API created internal audit",
            "lab_audit_subtype": "Document Audit",
            "status": "DRAFT",
        },
    )
    assert create.status_code == 201, create.text
    audit_id = create.json()["id"]
    finding = client.post(
        f"/api/v1/audits/{audit_id}/findings",
        json={
            "title": "API finding",
            "description": "Created by test",
            "finding_type": "NONCONFORMITY",
            "severity": "MAJOR",
        },
    )
    assert finding.status_code == 201, finding.text
    finding_id = finding.json()["id"]
    capa = client.post(
        f"/api/v1/findings/{finding_id}/capa",
        json={"corrective_action": "Fix it", "priority": "HIGH"},
    )
    assert capa.status_code == 201, capa.text
    evidence = client.post(
        f"/api/v1/audits/{audit_id}/evidence",
        json={"document_reference": "demo://test-evidence"},
    )
    assert evidence.status_code == 201, evidence.text

    patched = client.patch(
        f"/api/v1/audits/{audit_id}",
        json={"status": "SCHEDULED"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "SCHEDULED"
