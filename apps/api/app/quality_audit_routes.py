"""HTTP routes for the reusable quality-audit domain (NABL + INTERNAL)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import Db, commit, flush, get_tenant_record
from app.audit import record_event
from app.auth import AuthContext, require_permission
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
    QualityAudit,
)
from app.quality_audit import (
    AUDIT_TYPES,
    CHECK_RESULTS,
    apply_audit_status,
    apply_capa_status,
    apply_finding_status,
    compliance_percent,
    get_audit_dashboard,
    get_capa,
    get_finding,
    get_quality_audit,
    next_number,
    scoped_audits,
)
from app.schemas import (
    AuditCapaCreate,
    AuditCapaRead,
    AuditCapaUpdate,
    AuditChecklistItemRead,
    AuditChecklistRead,
    AuditCheckResultCreate,
    AuditCheckResultRead,
    AuditClauseRead,
    AuditDashboardRead,
    AuditEvidenceCreate,
    AuditEvidenceRead,
    AuditFindingCreate,
    AuditFindingRead,
    AuditFindingUpdate,
    AuditStandardRead,
    Page,
    QualityAuditCreate,
    QualityAuditRead,
    QualityAuditUpdate,
)

router = APIRouter(tags=["quality-audit"])


def _audit_read(db: Session, audit: QualityAudit) -> QualityAuditRead:
    results = list(
        db.scalars(select(AuditCheckResult).where(AuditCheckResult.audit_id == audit.id)).all()
    )
    payload = QualityAuditRead.model_validate(audit)
    payload.compliance_percent = compliance_percent(results)
    return payload


@router.get("/audit-dashboard", response_model=AuditDashboardRead)
def audit_dashboard(
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("quality_audit.read"))],
    audit_type: Annotated[str, Query(pattern="^(NABL|INTERNAL)$")],
    branch_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    status: str | None = None,
    severity: str | None = None,
    auditor_user_id: uuid.UUID | None = None,
    standard_id: uuid.UUID | None = None,
    clause_id: uuid.UUID | None = None,
    process_name: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> AuditDashboardRead:
    return get_audit_dashboard(
        db,
        context,
        audit_type=audit_type,
        branch_id=branch_id,
        department_id=department_id,
        status=status,
        severity=severity,
        auditor_user_id=auditor_user_id,
        standard_id=standard_id,
        clause_id=clause_id,
        process_name=process_name,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/audits", response_model=Page[QualityAuditRead])
def list_audits(
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("quality_audit.read"))],
    audit_type: Annotated[str | None, Query(pattern="^(NABL|INTERNAL)$")] = None,
    branch_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[QualityAuditRead]:
    statement = scoped_audits(context)
    if audit_type:
        statement = statement.where(QualityAudit.audit_type == audit_type)
    if branch_id:
        if not context.can_access_branch(branch_id):
            raise HTTPException(status_code=403, detail="Branch access denied")
        statement = statement.where(QualityAudit.branch_id == branch_id)
    if status:
        statement = statement.where(QualityAudit.status == status)
    statement = statement.order_by(QualityAudit.created_at.desc(), QualityAudit.id.desc())
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = list(db.scalars(statement.limit(limit).offset(offset)).all())
    return Page[QualityAuditRead](
        items=[_audit_read(db, item) for item in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/audits", response_model=QualityAuditRead, status_code=201)
def create_audit(
    payload: QualityAuditCreate,
    request: Request,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("quality_audit.manage"))],
) -> QualityAuditRead:
    if payload.audit_type not in AUDIT_TYPES:
        raise HTTPException(status_code=400, detail="Invalid audit_type")
    get_tenant_record(db, Branch, payload.branch_id, context)
    if not context.can_access_branch(payload.branch_id):
        raise HTTPException(status_code=403, detail="Branch access denied")
    number = payload.audit_number or next_number(
        db, context.organization_id, "AUD", QualityAudit, QualityAudit.audit_number
    )
    audit = QualityAudit(
        organization_id=context.organization_id,
        branch_id=payload.branch_id,
        department_id=payload.department_id,
        checklist_id=payload.checklist_id,
        standard_id=payload.standard_id,
        audit_number=number,
        audit_type=payload.audit_type,
        lab_audit_subtype=payload.lab_audit_subtype,
        title=payload.title,
        scope=payload.scope,
        process_name=payload.process_name,
        auditor_user_id=payload.auditor_user_id or context.user_id,
        audit_owner_user_id=payload.audit_owner_user_id,
        planned_start_at=payload.planned_start_at,
        status=payload.status or "DRAFT",
        description=payload.description,
        is_demo=False,
    )
    db.add(audit)
    flush(db)
    record_event(
        db,
        request,
        context,
        event_type="quality_audit.created",
        entity_type="audit",
        entity_id=audit.id,
        action="create",
        branch_id=audit.branch_id,
        new={
            "audit_number": audit.audit_number,
            "audit_type": audit.audit_type,
            "status": audit.status,
        },
    )
    commit(db)
    db.refresh(audit)
    return _audit_read(db, audit)


@router.get("/audits/{audit_id}", response_model=QualityAuditRead)
def read_audit(
    audit_id: uuid.UUID,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("quality_audit.read"))],
) -> QualityAuditRead:
    return _audit_read(db, get_quality_audit(db, audit_id, context))


@router.patch("/audits/{audit_id}", response_model=QualityAuditRead)
def update_audit(
    audit_id: uuid.UUID,
    payload: QualityAuditUpdate,
    request: Request,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("quality_audit.manage"))],
) -> QualityAuditRead:
    audit = get_quality_audit(db, audit_id, context)
    previous = {"status": audit.status, "title": audit.title}
    data = payload.model_dump(exclude_unset=True)
    new_status = data.pop("status", None)
    for key, value in data.items():
        setattr(audit, key, value)
    if new_status is not None:
        apply_audit_status(audit, new_status)
    record_event(
        db,
        request,
        context,
        event_type="quality_audit.updated",
        entity_type="audit",
        entity_id=audit.id,
        action="update",
        branch_id=audit.branch_id,
        previous=previous,
        new={"status": audit.status, "title": audit.title},
    )
    commit(db)
    db.refresh(audit)
    return _audit_read(db, audit)


@router.get("/audits/{audit_id}/checks", response_model=list[AuditCheckResultRead])
def list_checks(
    audit_id: uuid.UUID,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("quality_audit.read"))],
) -> list[AuditCheckResult]:
    get_quality_audit(db, audit_id, context)
    return list(
        db.scalars(
            select(AuditCheckResult)
            .where(
                AuditCheckResult.organization_id == context.organization_id,
                AuditCheckResult.audit_id == audit_id,
            )
            .order_by(AuditCheckResult.created_at)
        ).all()
    )


@router.post("/audits/{audit_id}/checks", response_model=AuditCheckResultRead, status_code=201)
def upsert_check(
    audit_id: uuid.UUID,
    payload: AuditCheckResultCreate,
    request: Request,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("quality_audit.manage"))],
) -> AuditCheckResult:
    audit = get_quality_audit(db, audit_id, context)
    if payload.result not in CHECK_RESULTS:
        raise HTTPException(status_code=400, detail="Invalid check result")
    item = db.scalar(
        select(AuditChecklistItem).where(
            AuditChecklistItem.id == payload.checklist_item_id,
            AuditChecklistItem.organization_id == context.organization_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    existing = db.scalar(
        select(AuditCheckResult).where(
            AuditCheckResult.audit_id == audit.id,
            AuditCheckResult.checklist_item_id == payload.checklist_item_id,
        )
    )
    now = datetime.now(UTC)
    if existing:
        existing.result = payload.result
        existing.score = payload.score
        existing.observation = payload.observation
        existing.evidence_required = payload.evidence_required
        existing.evidence_provided = payload.evidence_provided
        existing.evaluated_by = context.user_id
        existing.evaluated_at = now
        row = existing
        action = "update"
    else:
        row = AuditCheckResult(
            organization_id=context.organization_id,
            audit_id=audit.id,
            checklist_item_id=payload.checklist_item_id,
            result=payload.result,
            score=payload.score,
            observation=payload.observation,
            evidence_required=payload.evidence_required,
            evidence_provided=payload.evidence_provided,
            evaluated_by=context.user_id,
            evaluated_at=now,
        )
        db.add(row)
        action = "create"
    flush(db)
    record_event(
        db,
        request,
        context,
        event_type="quality_audit.check_evaluated",
        entity_type="audit_check_result",
        entity_id=row.id,
        action=action,
        branch_id=audit.branch_id,
        new={"result": row.result, "audit_id": str(audit.id)},
    )
    commit(db)
    db.refresh(row)
    return row


@router.get("/audits/{audit_id}/findings", response_model=list[AuditFindingRead])
def list_findings(
    audit_id: uuid.UUID,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("quality_audit.read"))],
) -> list[AuditFinding]:
    get_quality_audit(db, audit_id, context)
    return list(
        db.scalars(
            select(AuditFinding)
            .where(
                AuditFinding.organization_id == context.organization_id,
                AuditFinding.audit_id == audit_id,
            )
            .order_by(AuditFinding.created_at.desc())
        ).all()
    )


@router.post("/audits/{audit_id}/findings", response_model=AuditFindingRead, status_code=201)
def create_finding(
    audit_id: uuid.UUID,
    payload: AuditFindingCreate,
    request: Request,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("quality_audit.manage"))],
) -> AuditFinding:
    audit = get_quality_audit(db, audit_id, context)
    number = payload.finding_number or next_number(
        db, context.organization_id, "FND", AuditFinding, AuditFinding.finding_number
    )
    finding = AuditFinding(
        organization_id=context.organization_id,
        branch_id=audit.branch_id,
        audit_id=audit.id,
        checklist_result_id=payload.checklist_result_id,
        department_id=payload.department_id or audit.department_id,
        standard_id=payload.standard_id or audit.standard_id,
        clause_id=payload.clause_id,
        analyzer_id=payload.analyzer_id,
        specimen_id=payload.specimen_id,
        lab_result_id=payload.lab_result_id,
        worklist_item_id=payload.worklist_item_id,
        referenced_entity_type=payload.referenced_entity_type,
        referenced_entity_id=payload.referenced_entity_id,
        finding_number=number,
        finding_type=payload.finding_type,
        severity=payload.severity,
        title=payload.title,
        description=payload.description,
        requirement=payload.requirement,
        root_cause=payload.root_cause,
        correction=payload.correction,
        corrective_action_required=payload.corrective_action_required,
        preventive_action_required=payload.preventive_action_required,
        owner_user_id=payload.owner_user_id,
        due_at=payload.due_at,
        status=payload.status or "OPEN",
        process_name=payload.process_name or audit.process_name,
        is_demo=False,
    )
    db.add(finding)
    flush(db)
    record_event(
        db,
        request,
        context,
        event_type="quality_audit.finding_created",
        entity_type="audit_finding",
        entity_id=finding.id,
        action="create",
        branch_id=audit.branch_id,
        new={
            "finding_number": finding.finding_number,
            "severity": finding.severity,
            "finding_type": finding.finding_type,
        },
    )
    commit(db)
    db.refresh(finding)
    return finding


@router.get("/findings/{finding_id}", response_model=AuditFindingRead)
def read_finding(
    finding_id: uuid.UUID,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("quality_audit.read"))],
) -> AuditFinding:
    return get_finding(db, finding_id, context)


@router.patch("/findings/{finding_id}", response_model=AuditFindingRead)
def update_finding(
    finding_id: uuid.UUID,
    payload: AuditFindingUpdate,
    request: Request,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("quality_audit.manage"))],
) -> AuditFinding:
    finding = get_finding(db, finding_id, context)
    previous = {"status": finding.status, "severity": finding.severity}
    data = payload.model_dump(exclude_unset=True)
    new_status = data.pop("status", None)
    for key, value in data.items():
        setattr(finding, key, value)
    if new_status is not None:
        apply_finding_status(finding, new_status)
    record_event(
        db,
        request,
        context,
        event_type="quality_audit.finding_updated",
        entity_type="audit_finding",
        entity_id=finding.id,
        action="update",
        branch_id=finding.branch_id,
        previous=previous,
        new={"status": finding.status, "severity": finding.severity},
    )
    commit(db)
    db.refresh(finding)
    return finding


@router.get("/findings/{finding_id}/capa", response_model=list[AuditCapaRead])
def list_capa(
    finding_id: uuid.UUID,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("quality_audit.read"))],
) -> list[AuditCapa]:
    get_finding(db, finding_id, context)
    return list(
        db.scalars(
            select(AuditCapa).where(
                AuditCapa.organization_id == context.organization_id,
                AuditCapa.finding_id == finding_id,
            )
        ).all()
    )


@router.post("/findings/{finding_id}/capa", response_model=AuditCapaRead, status_code=201)
def create_capa(
    finding_id: uuid.UUID,
    payload: AuditCapaCreate,
    request: Request,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("quality_audit.manage"))],
) -> AuditCapa:
    finding = get_finding(db, finding_id, context)
    number = payload.capa_number or next_number(
        db, context.organization_id, "CAPA", AuditCapa, AuditCapa.capa_number
    )
    capa = AuditCapa(
        organization_id=context.organization_id,
        finding_id=finding.id,
        capa_number=number,
        root_cause=payload.root_cause or finding.root_cause,
        immediate_correction=payload.immediate_correction,
        corrective_action=payload.corrective_action,
        preventive_action=payload.preventive_action,
        owner_user_id=payload.owner_user_id or finding.owner_user_id,
        priority=payload.priority,
        due_at=payload.due_at or finding.due_at,
        status=payload.status or "OPEN",
        effectiveness_check_required=payload.effectiveness_check_required,
        is_demo=False,
    )
    db.add(capa)
    if finding.status == "OPEN":
        apply_finding_status(finding, "CAPA_ASSIGNED")
    flush(db)
    record_event(
        db,
        request,
        context,
        event_type="quality_audit.capa_assigned",
        entity_type="audit_capa",
        entity_id=capa.id,
        action="create",
        branch_id=finding.branch_id,
        new={"capa_number": capa.capa_number, "finding_id": str(finding.id)},
    )
    commit(db)
    db.refresh(capa)
    return capa


@router.patch("/capa/{capa_id}", response_model=AuditCapaRead)
def update_capa(
    capa_id: uuid.UUID,
    payload: AuditCapaUpdate,
    request: Request,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("quality_audit.manage"))],
) -> AuditCapa:
    capa = get_capa(db, capa_id, context)
    finding = get_finding(db, capa.finding_id, context)
    previous = {"status": capa.status}
    data = payload.model_dump(exclude_unset=True)
    new_status = data.pop("status", None)
    for key, value in data.items():
        setattr(capa, key, value)
    if new_status is not None:
        apply_capa_status(capa, new_status, context)
    record_event(
        db,
        request,
        context,
        event_type="quality_audit.capa_updated",
        entity_type="audit_capa",
        entity_id=capa.id,
        action="update",
        branch_id=finding.branch_id,
        previous=previous,
        new={"status": capa.status},
    )
    commit(db)
    db.refresh(capa)
    return capa


@router.get("/audits/{audit_id}/evidence", response_model=list[AuditEvidenceRead])
def list_evidence(
    audit_id: uuid.UUID,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("quality_audit.read"))],
) -> list[AuditEvidence]:
    get_quality_audit(db, audit_id, context)
    return list(
        db.scalars(
            select(AuditEvidence).where(
                AuditEvidence.organization_id == context.organization_id,
                AuditEvidence.audit_id == audit_id,
            )
        ).all()
    )


@router.post("/audits/{audit_id}/evidence", response_model=AuditEvidenceRead, status_code=201)
def create_evidence(
    audit_id: uuid.UUID,
    payload: AuditEvidenceCreate,
    request: Request,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("quality_audit.manage"))],
) -> AuditEvidence:
    audit = get_quality_audit(db, audit_id, context)
    evidence = AuditEvidence(
        organization_id=context.organization_id,
        audit_id=audit.id,
        finding_id=payload.finding_id,
        capa_id=payload.capa_id,
        document_reference=payload.document_reference,
        description=payload.description,
        uploaded_by=context.user_id,
        uploaded_at=datetime.now(UTC),
        version=payload.version,
        verification_status=payload.verification_status,
        is_demo=False,
    )
    db.add(evidence)
    flush(db)
    record_event(
        db,
        request,
        context,
        event_type="quality_audit.evidence_uploaded",
        entity_type="audit_evidence",
        entity_id=evidence.id,
        action="create",
        branch_id=audit.branch_id,
        new={"document_reference": evidence.document_reference},
    )
    commit(db)
    db.refresh(evidence)
    return evidence


@router.get("/audit-checklists", response_model=list[AuditChecklistRead])
def list_checklists(
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("quality_audit.read"))],
    audit_type: Annotated[str | None, Query(pattern="^(NABL|INTERNAL)$")] = None,
) -> list[AuditChecklistRead]:
    statement = select(AuditChecklist).where(
        AuditChecklist.organization_id == context.organization_id
    )
    if audit_type:
        statement = statement.where(AuditChecklist.audit_type == audit_type)
    checklists = list(db.scalars(statement.order_by(AuditChecklist.name)).all())
    result: list[AuditChecklistRead] = []
    for checklist in checklists:
        items = list(
            db.scalars(
                select(AuditChecklistItem)
                .where(
                    AuditChecklistItem.checklist_id == checklist.id,
                    AuditChecklistItem.active.is_(True),
                )
                .order_by(AuditChecklistItem.sequence)
            ).all()
        )
        row = AuditChecklistRead.model_validate(checklist)
        row.items = [AuditChecklistItemRead.model_validate(item) for item in items]
        result.append(row)
    return result


@router.get("/audit-standards", response_model=list[AuditStandardRead])
def list_standards(
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("quality_audit.read"))],
) -> list[AuditStandard]:
    return list(
        db.scalars(
            select(AuditStandard)
            .where(AuditStandard.organization_id == context.organization_id)
            .order_by(AuditStandard.code)
        ).all()
    )


@router.get("/audit-standards/{standard_id}/clauses", response_model=list[AuditClauseRead])
def list_clauses(
    standard_id: uuid.UUID,
    db: Db,
    context: Annotated[AuthContext, Depends(require_permission("quality_audit.read"))],
) -> list[AuditClause]:
    standard = db.scalar(
        select(AuditStandard).where(
            AuditStandard.id == standard_id,
            AuditStandard.organization_id == context.organization_id,
        )
    )
    if standard is None:
        raise HTTPException(status_code=404, detail="Standard not found")
    return list(
        db.scalars(
            select(AuditClause)
            .where(
                AuditClause.organization_id == context.organization_id,
                AuditClause.standard_id == standard_id,
                AuditClause.active.is_(True),
            )
            .order_by(AuditClause.sequence)
        ).all()
    )
