"""Synthetic DEMO quality-audit seed for NABL and internal LAB dashboards."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditCapa,
    AuditChecklist,
    AuditChecklistItem,
    AuditCheckResult,
    AuditClause,
    AuditEvidence,
    AuditFinding,
    AuditStandard,
    Branch,
    Department,
    Organization,
    QualityAudit,
    User,
)


def seed_quality_audit_demo(
    db: Session, organization: Organization, branch: Branch, user: User
) -> bool:
    existing = db.scalar(
        select(QualityAudit).where(
            QualityAudit.organization_id == organization.id,
            QualityAudit.audit_number == "DEMO-NABL-001",
        )
    )
    if existing:
        return False

    now = datetime.now(UTC)
    department = db.scalar(
        select(Department).where(
            Department.organization_id == organization.id,
            Department.branch_id == branch.id,
        )
    )

    standard = AuditStandard(
        organization_id=organization.id,
        code="DEMO-STD",
        name="Synthetic accreditation placeholder (not real NABL clauses)",
        version="DEMO-1",
        effective_from=now - timedelta(days=365),
        status="active",
        is_demo=True,
    )
    db.add(standard)
    db.flush()

    clauses = [
        AuditClause(
            organization_id=organization.id,
            standard_id=standard.id,
            clause_code="DEMO-4.1",
            title="Demo management responsibility",
            description="Placeholder clause for UI demos only.",
            sequence=1,
            active=True,
            is_demo=True,
        ),
        AuditClause(
            organization_id=organization.id,
            standard_id=standard.id,
            clause_code="DEMO-5.3",
            title="Demo equipment control",
            description="Placeholder clause for UI demos only.",
            sequence=2,
            active=True,
            is_demo=True,
        ),
        AuditClause(
            organization_id=organization.id,
            standard_id=standard.id,
            clause_code="DEMO-5.6",
            title="Demo result reporting",
            description="Placeholder clause for UI demos only.",
            sequence=3,
            active=True,
            is_demo=True,
        ),
    ]
    db.add_all(clauses)
    db.flush()

    nabl_checklist = AuditChecklist(
        organization_id=organization.id,
        name="DEMO NABL checklist",
        audit_type="NABL",
        version="1",
        status="active",
        description="Synthetic checklist — not accreditation content.",
        is_demo=True,
    )
    lab_checklist = AuditChecklist(
        organization_id=organization.id,
        name="DEMO internal process checklist",
        audit_type="INTERNAL",
        version="1",
        status="active",
        description="Synthetic checklist for internal lab audits.",
        is_demo=True,
    )
    db.add_all([nabl_checklist, lab_checklist])
    db.flush()

    nabl_items = [
        AuditChecklistItem(
            organization_id=organization.id,
            checklist_id=nabl_checklist.id,
            sequence=1,
            section="Management",
            requirement="Demo: documented quality policy exists",
            question="Is a documented quality policy available?",
            expected_evidence="Policy document reference",
            severity_if_failed="MAJOR",
            clause_id=clauses[0].id,
            active=True,
        ),
        AuditChecklistItem(
            organization_id=organization.id,
            checklist_id=nabl_checklist.id,
            sequence=2,
            section="Equipment",
            requirement="Demo: analyzers have maintenance records",
            question="Are maintenance records current for critical analyzers?",
            expected_evidence="Maintenance log",
            severity_if_failed="CRITICAL",
            clause_id=clauses[1].id,
            active=True,
        ),
        AuditChecklistItem(
            organization_id=organization.id,
            checklist_id=nabl_checklist.id,
            sequence=3,
            section="Reporting",
            requirement="Demo: result release controls",
            question="Are result release controls followed?",
            expected_evidence="Release checklist",
            severity_if_failed="MINOR",
            clause_id=clauses[2].id,
            active=True,
        ),
    ]
    lab_items = [
        AuditChecklistItem(
            organization_id=organization.id,
            checklist_id=lab_checklist.id,
            sequence=1,
            section="Pre-analytical",
            requirement="Demo: specimen acceptance criteria",
            question="Are specimen acceptance criteria applied?",
            expected_evidence="Rejection log sample",
            severity_if_failed="MAJOR",
            active=True,
        ),
        AuditChecklistItem(
            organization_id=organization.id,
            checklist_id=lab_checklist.id,
            sequence=2,
            section="Analytical",
            requirement="Demo: QC review before release",
            question="Is QC reviewed before patient release?",
            expected_evidence="QC review sign-off",
            severity_if_failed="CRITICAL",
            active=True,
        ),
    ]
    db.add_all(nabl_items + lab_items)
    db.flush()

    nabl_audit = QualityAudit(
        organization_id=organization.id,
        branch_id=branch.id,
        department_id=department.id if department else None,
        checklist_id=nabl_checklist.id,
        standard_id=standard.id,
        audit_number="DEMO-NABL-001",
        audit_type="NABL",
        title="DEMO NABL surveillance engagement",
        scope="Synthetic demo scope — Haematology & Chemistry",
        process_name="Accreditation surveillance",
        auditor_user_id=user.id,
        audit_owner_user_id=user.id,
        planned_start_at=now - timedelta(days=20),
        started_at=now - timedelta(days=18),
        completed_at=now - timedelta(days=10),
        status="CAPA_PENDING",
        description="Synthetic DEMO audit for dashboard testing.",
        is_demo=True,
    )
    lab_audit = QualityAudit(
        organization_id=organization.id,
        branch_id=branch.id,
        department_id=department.id if department else None,
        checklist_id=lab_checklist.id,
        audit_number="DEMO-LAB-001",
        audit_type="INTERNAL",
        lab_audit_subtype="Analytical Audit",
        title="DEMO analytical process audit",
        scope="Synthetic demo — chemistry analytical process",
        process_name="Analytical testing",
        auditor_user_id=user.id,
        audit_owner_user_id=user.id,
        planned_start_at=now - timedelta(days=7),
        started_at=now - timedelta(days=6),
        status="IN_PROGRESS",
        description="Synthetic DEMO internal audit.",
        is_demo=True,
    )
    lab_audit_2 = QualityAudit(
        organization_id=organization.id,
        branch_id=branch.id,
        department_id=department.id if department else None,
        checklist_id=lab_checklist.id,
        audit_number="DEMO-LAB-002",
        audit_type="INTERNAL",
        lab_audit_subtype="Pre-Analytical Audit",
        title="DEMO pre-analytical audit",
        scope="Synthetic demo — specimen reception",
        process_name="Specimen reception",
        auditor_user_id=user.id,
        planned_start_at=now + timedelta(days=14),
        status="SCHEDULED",
        description="Synthetic DEMO scheduled audit.",
        is_demo=True,
    )
    db.add_all([nabl_audit, lab_audit, lab_audit_2])
    db.flush()

    nabl_results = [
        AuditCheckResult(
            organization_id=organization.id,
            audit_id=nabl_audit.id,
            checklist_item_id=nabl_items[0].id,
            result="COMPLIANT",
            score=100,
            evaluated_by=user.id,
            evaluated_at=now - timedelta(days=12),
        ),
        AuditCheckResult(
            organization_id=organization.id,
            audit_id=nabl_audit.id,
            checklist_item_id=nabl_items[1].id,
            result="NON_COMPLIANT",
            score=0,
            observation="Demo observation: maintenance evidence incomplete",
            evidence_required=True,
            evidence_provided=False,
            evaluated_by=user.id,
            evaluated_at=now - timedelta(days=12),
        ),
        AuditCheckResult(
            organization_id=organization.id,
            audit_id=nabl_audit.id,
            checklist_item_id=nabl_items[2].id,
            result="PARTIAL",
            score=50,
            evaluated_by=user.id,
            evaluated_at=now - timedelta(days=12),
        ),
    ]
    lab_results = [
        AuditCheckResult(
            organization_id=organization.id,
            audit_id=lab_audit.id,
            checklist_item_id=lab_items[0].id,
            result="COMPLIANT",
            score=100,
            evaluated_by=user.id,
            evaluated_at=now - timedelta(days=5),
        ),
        AuditCheckResult(
            organization_id=organization.id,
            audit_id=lab_audit.id,
            checklist_item_id=lab_items[1].id,
            result="NON_COMPLIANT",
            score=0,
            observation="Demo QC gap",
            evidence_required=True,
            evaluated_by=user.id,
            evaluated_at=now - timedelta(days=5),
        ),
    ]
    db.add_all(nabl_results + lab_results)
    db.flush()

    findings = [
        AuditFinding(
            organization_id=organization.id,
            branch_id=branch.id,
            audit_id=nabl_audit.id,
            checklist_result_id=nabl_results[1].id,
            department_id=department.id if department else None,
            standard_id=standard.id,
            clause_id=clauses[1].id,
            finding_number="DEMO-FND-001",
            finding_type="NONCONFORMITY",
            severity="CRITICAL",
            title="Demo equipment maintenance evidence gap",
            description="Synthetic finding for dashboard demos only.",
            requirement=nabl_items[1].requirement,
            corrective_action_required=True,
            owner_user_id=user.id,
            due_at=now - timedelta(days=2),
            status="CAPA_ASSIGNED",
            process_name="Equipment control",
            is_demo=True,
        ),
        AuditFinding(
            organization_id=organization.id,
            branch_id=branch.id,
            audit_id=nabl_audit.id,
            checklist_result_id=nabl_results[2].id,
            department_id=department.id if department else None,
            standard_id=standard.id,
            clause_id=clauses[2].id,
            finding_number="DEMO-FND-002",
            finding_type="OBSERVATION",
            severity="MINOR",
            title="Demo result-release documentation incomplete",
            description="Synthetic minor finding.",
            corrective_action_required=True,
            owner_user_id=user.id,
            due_at=now + timedelta(days=10),
            status="OPEN",
            process_name="Result reporting",
            is_demo=True,
        ),
        AuditFinding(
            organization_id=organization.id,
            branch_id=branch.id,
            audit_id=lab_audit.id,
            checklist_result_id=lab_results[1].id,
            department_id=department.id if department else None,
            finding_number="DEMO-FND-003",
            finding_type="NONCONFORMITY",
            severity="MAJOR",
            title="Demo QC review not evidenced",
            description="Synthetic internal finding.",
            corrective_action_required=True,
            owner_user_id=user.id,
            due_at=now + timedelta(days=5),
            status="OPEN",
            process_name="Analytical testing",
            is_demo=True,
        ),
    ]
    db.add_all(findings)
    db.flush()

    capa = AuditCapa(
        organization_id=organization.id,
        finding_id=findings[0].id,
        capa_number="DEMO-CAPA-001",
        root_cause="Synthetic root cause for demo",
        immediate_correction="Demo interim control",
        corrective_action="Demo corrective action plan",
        preventive_action="Demo preventive action",
        owner_user_id=user.id,
        priority="HIGH",
        due_at=now - timedelta(days=1),
        status="ACTION_IN_PROGRESS",
        effectiveness_check_required=True,
        is_demo=True,
    )
    db.add(capa)
    db.flush()

    db.add(
        AuditEvidence(
            organization_id=organization.id,
            audit_id=nabl_audit.id,
            finding_id=findings[0].id,
            document_reference="demo://evidence/maintenance-gap.pdf",
            description="Synthetic evidence reference (no file stored).",
            uploaded_by=user.id,
            uploaded_at=now - timedelta(days=9),
            version="1",
            verification_status="PENDING",
            is_demo=True,
        )
    )
    return True


def seed_quality_if_ready(db: Session) -> None:
    organization = db.scalar(select(Organization).where(Organization.code == "DEVLAB"))
    if organization is None:
        return
    branch = db.scalar(
        select(Branch).where(Branch.organization_id == organization.id).order_by(Branch.code)
    )
    user = db.scalar(
        select(User).where(User.organization_id == organization.id).order_by(User.email)
    )
    if branch is None or user is None:
        return
    seed_quality_audit_demo(db, organization, branch, user)
