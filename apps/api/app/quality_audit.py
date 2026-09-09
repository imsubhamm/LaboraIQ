"""Reusable quality-audit domain: workflows, compliance, dashboard aggregation."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.auth import AuthContext
from app.models import (
    AuditCapa,
    AuditCheckResult,
    AuditClause,
    AuditEvidence,
    AuditFinding,
    Department,
    QualityAudit,
    User,
)
from app.schemas import (
    AuditAlertRead,
    AuditDashboardAuditRowRead,
    AuditDashboardRead,
    AuditDashboardSummaryRead,
    AuditNamedCountRead,
    AuditTrendPointRead,
)

AUDIT_TYPES = frozenset({"NABL", "INTERNAL"})
CHECK_RESULTS = frozenset({"COMPLIANT", "PARTIAL", "NON_COMPLIANT", "NOT_APPLICABLE"})
SEVERITIES = frozenset({"CRITICAL", "MAJOR", "MINOR", "OBSERVATION"})
OPEN_FINDING_STATUSES = frozenset(
    {
        "OPEN",
        "ROOT_CAUSE_ANALYSIS",
        "CAPA_ASSIGNED",
        "ACTION_IN_PROGRESS",
        "EFFECTIVENESS_REVIEW",
    }
)
OPEN_CAPA_STATUSES = frozenset(
    {"OPEN", "ROOT_CAUSE_ANALYSIS", "ACTION_IN_PROGRESS", "EFFECTIVENESS_REVIEW"}
)
CLOSED_AUDIT_STATUS = "CLOSED"

AUDIT_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"SCHEDULED", "IN_PROGRESS"}),
    "SCHEDULED": frozenset({"IN_PROGRESS", "DRAFT"}),
    "IN_PROGRESS": frozenset({"COMPLETED", "FINDINGS_REVIEW"}),
    "COMPLETED": frozenset({"FINDINGS_REVIEW", "CAPA_PENDING", "CLOSED"}),
    "FINDINGS_REVIEW": frozenset({"CAPA_PENDING", "VERIFICATION", "CLOSED"}),
    "CAPA_PENDING": frozenset({"VERIFICATION", "CLOSED"}),
    "VERIFICATION": frozenset({"CLOSED"}),
    "CLOSED": frozenset(),
}

FINDING_TRANSITIONS: dict[str, frozenset[str]] = {
    "OPEN": frozenset({"ROOT_CAUSE_ANALYSIS", "CAPA_ASSIGNED", "CLOSED"}),
    "ROOT_CAUSE_ANALYSIS": frozenset({"CAPA_ASSIGNED", "ACTION_IN_PROGRESS", "CLOSED"}),
    "CAPA_ASSIGNED": frozenset({"ACTION_IN_PROGRESS", "CLOSED"}),
    "ACTION_IN_PROGRESS": frozenset({"EFFECTIVENESS_REVIEW", "CLOSED"}),
    "EFFECTIVENESS_REVIEW": frozenset({"CLOSED"}),
    "CLOSED": frozenset(),
}

CAPA_TRANSITIONS: dict[str, frozenset[str]] = {
    "OPEN": frozenset({"ROOT_CAUSE_ANALYSIS", "ACTION_IN_PROGRESS", "CLOSED"}),
    "ROOT_CAUSE_ANALYSIS": frozenset({"ACTION_IN_PROGRESS", "CLOSED"}),
    "ACTION_IN_PROGRESS": frozenset({"EFFECTIVENESS_REVIEW", "CLOSED"}),
    "EFFECTIVENESS_REVIEW": frozenset({"CLOSED"}),
    "CLOSED": frozenset(),
}

DASHBOARD_QUERY_BATCHES = 5


def aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def percent(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return round((numerator / denominator) * 100, 2)


def compliance_percent(results: list[AuditCheckResult]) -> float | None:
    applicable = [row for row in results if row.result != "NOT_APPLICABLE"]
    if not applicable:
        return None
    compliant = sum(1 for row in applicable if row.result == "COMPLIANT")
    return percent(compliant, len(applicable))


def assert_transition(
    current: str, target: str, edges: dict[str, frozenset[str]], label: str
) -> None:
    allowed = edges.get(current, frozenset())
    if target == current:
        return
    if target not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {label} transition from {current} to {target}",
        )


def scoped_audits(context: AuthContext) -> Any:
    statement = select(QualityAudit).where(QualityAudit.organization_id == context.organization_id)
    if not context.is_organization_scoped:
        statement = statement.where(QualityAudit.branch_id.in_(context.branch_ids))
    return statement


def get_quality_audit(db: Session, audit_id: UUID, context: AuthContext) -> QualityAudit:
    audit = db.scalar(scoped_audits(context).where(QualityAudit.id == audit_id))
    if not isinstance(audit, QualityAudit):
        raise HTTPException(status_code=404, detail="Audit not found")
    if not context.can_access_branch(audit.branch_id):
        raise HTTPException(status_code=403, detail="Branch access denied")
    return audit


def get_finding(db: Session, finding_id: UUID, context: AuthContext) -> AuditFinding:
    finding = db.scalar(
        select(AuditFinding).where(
            AuditFinding.id == finding_id,
            AuditFinding.organization_id == context.organization_id,
        )
    )
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    if not context.can_access_branch(finding.branch_id):
        raise HTTPException(status_code=403, detail="Branch access denied")
    return finding


def get_capa(db: Session, capa_id: UUID, context: AuthContext) -> AuditCapa:
    capa = db.scalar(
        select(AuditCapa)
        .join(AuditFinding, AuditFinding.id == AuditCapa.finding_id)
        .where(
            AuditCapa.id == capa_id,
            AuditCapa.organization_id == context.organization_id,
        )
    )
    if capa is None:
        raise HTTPException(status_code=404, detail="CAPA not found")
    finding = get_finding(db, capa.finding_id, context)
    _ = finding
    return capa


def next_number(db: Session, organization_id: UUID, prefix: str, model: Any, field: Any) -> str:
    count = (
        db.scalar(
            select(func.count()).select_from(model).where(model.organization_id == organization_id)
        )
        or 0
    )
    return f"{prefix}-{count + 1:04d}"


def apply_audit_status(audit: QualityAudit, status: str, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    assert_transition(audit.status, status, AUDIT_TRANSITIONS, "audit")
    previous = audit.status
    audit.status = status
    if status == "IN_PROGRESS" and audit.started_at is None:
        audit.started_at = now
    if status == "COMPLETED" and audit.completed_at is None:
        audit.completed_at = now
    if status == CLOSED_AUDIT_STATUS:
        audit.closed_at = now
        if audit.completed_at is None:
            audit.completed_at = now
    _ = previous


def apply_finding_status(finding: AuditFinding, status: str, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    assert_transition(finding.status, status, FINDING_TRANSITIONS, "finding")
    finding.status = status
    if status == "CLOSED":
        finding.closed_at = now


def apply_capa_status(
    capa: AuditCapa, status: str, context: AuthContext, now: datetime | None = None
) -> None:
    now = now or datetime.now(UTC)
    assert_transition(capa.status, status, CAPA_TRANSITIONS, "CAPA")
    capa.status = status
    if status == "CLOSED":
        capa.closed_at = now
        if capa.effectiveness_check_required and not capa.effectiveness_verified:
            capa.effectiveness_verified = True
            capa.verified_by = context.user_id
            capa.verified_at = now


def compliance_by_audit_ids(
    db: Session, organization_id: UUID, audit_ids: list[UUID]
) -> dict[UUID, float | None]:
    if not audit_ids:
        return {}
    rows = db.execute(
        select(
            AuditCheckResult.audit_id,
            func.sum(case((AuditCheckResult.result != "NOT_APPLICABLE", 1), else_=0)).label(
                "applicable"
            ),
            func.sum(case((AuditCheckResult.result == "COMPLIANT", 1), else_=0)).label("compliant"),
        )
        .where(
            AuditCheckResult.organization_id == organization_id,
            AuditCheckResult.audit_id.in_(audit_ids),
        )
        .group_by(AuditCheckResult.audit_id)
    ).all()
    return {
        audit_id: percent(float(compliant or 0), float(applicable or 0))
        for audit_id, applicable, compliant in rows
    }


def get_audit_dashboard(
    db: Session,
    context: AuthContext,
    *,
    audit_type: str,
    branch_id: UUID | None = None,
    department_id: UUID | None = None,
    status: str | None = None,
    severity: str | None = None,
    auditor_user_id: UUID | None = None,
    standard_id: UUID | None = None,
    clause_id: UUID | None = None,
    process_name: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> AuditDashboardRead:
    if audit_type not in AUDIT_TYPES:
        raise HTTPException(status_code=400, detail="audit_type must be NABL or INTERNAL")
    if branch_id and not context.can_access_branch(branch_id):
        raise HTTPException(status_code=403, detail="Branch access denied")

    now = datetime.now(UTC)
    window_end = aware(date_to) or now
    window_start = aware(date_from) or (window_end - timedelta(days=90))

    audits_stmt = select(QualityAudit).where(
        QualityAudit.organization_id == context.organization_id,
        QualityAudit.audit_type == audit_type,
    )
    if not context.is_organization_scoped:
        audits_stmt = audits_stmt.where(QualityAudit.branch_id.in_(context.branch_ids))
    if branch_id:
        audits_stmt = audits_stmt.where(QualityAudit.branch_id == branch_id)
    if department_id:
        audits_stmt = audits_stmt.where(QualityAudit.department_id == department_id)
    if status:
        audits_stmt = audits_stmt.where(QualityAudit.status == status)
    if auditor_user_id:
        audits_stmt = audits_stmt.where(QualityAudit.auditor_user_id == auditor_user_id)
    if standard_id:
        audits_stmt = audits_stmt.where(QualityAudit.standard_id == standard_id)
    if process_name:
        audits_stmt = audits_stmt.where(QualityAudit.process_name == process_name)
    # Date on planned_start_at / started_at / created_at
    audits_stmt = audits_stmt.where(
        func.coalesce(
            QualityAudit.planned_start_at, QualityAudit.started_at, QualityAudit.created_at
        )
        >= window_start,
        func.coalesce(
            QualityAudit.planned_start_at, QualityAudit.started_at, QualityAudit.created_at
        )
        <= window_end,
    )

    audits = list(db.scalars(audits_stmt.order_by(QualityAudit.created_at.desc())).all())
    audit_ids = [row.id for row in audits]

    findings: list[AuditFinding] = []
    if audit_ids:
        findings_stmt = select(AuditFinding).where(
            AuditFinding.organization_id == context.organization_id,
            AuditFinding.audit_id.in_(audit_ids),
        )
        if severity:
            findings_stmt = findings_stmt.where(AuditFinding.severity == severity)
        if clause_id:
            findings_stmt = findings_stmt.where(AuditFinding.clause_id == clause_id)
        if department_id:
            findings_stmt = findings_stmt.where(AuditFinding.department_id == department_id)
        findings = list(db.scalars(findings_stmt).all())

    finding_ids = [row.id for row in findings]
    capas: list[AuditCapa] = []
    if finding_ids:
        capas = list(
            db.scalars(
                select(AuditCapa).where(
                    AuditCapa.organization_id == context.organization_id,
                    AuditCapa.finding_id.in_(finding_ids),
                )
            ).all()
        )

    evidence_pending = 0
    if audit_ids:
        evidence_pending = (
            db.scalar(
                select(func.count())
                .select_from(AuditEvidence)
                .where(
                    AuditEvidence.organization_id == context.organization_id,
                    AuditEvidence.verification_status == "PENDING",
                    AuditEvidence.audit_id.in_(audit_ids),
                )
            )
            or 0
        )

    compliance_map = compliance_by_audit_ids(db, context.organization_id, audit_ids)

    open_findings = [f for f in findings if f.status in OPEN_FINDING_STATUSES]
    overdue_capa = [
        c
        for c in capas
        if c.status in OPEN_CAPA_STATUSES
        and aware(c.due_at) is not None
        and aware(c.due_at) < now  # type: ignore[operator]
    ]
    closed_audits = [a for a in audits if a.status == CLOSED_AUDIT_STATUS]
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    audits_this_month = [
        a
        for a in audits
        if aware(a.created_at) is not None and aware(a.created_at) >= month_start  # type: ignore[operator]
    ]

    compliance_values = [v for v in compliance_map.values() if v is not None]
    overall_compliance = (
        round(sum(compliance_values) / len(compliance_values), 2) if compliance_values else None
    )

    closure_days: list[float] = []
    for audit in closed_audits:
        start = aware(audit.started_at) or aware(audit.planned_start_at) or aware(audit.created_at)
        end = aware(audit.closed_at)
        if start and end and end >= start:
            closure_days.append((end - start).total_seconds() / 86400)
    avg_closure_days = round(sum(closure_days) / len(closure_days), 1) if closure_days else None

    summary = AuditDashboardSummaryRead(
        total_audits=len(audits),
        audits_this_month=len(audits_this_month),
        scheduled=sum(1 for a in audits if a.status == "SCHEDULED"),
        in_progress=sum(1 for a in audits if a.status == "IN_PROGRESS"),
        completed=sum(1 for a in audits if a.status in {"COMPLETED", "FINDINGS_REVIEW", "CLOSED"}),
        compliance_percent=overall_compliance,
        open_findings=len(open_findings),
        critical_findings=sum(1 for f in open_findings if f.severity == "CRITICAL"),
        major_findings=sum(1 for f in open_findings if f.severity == "MAJOR"),
        minor_findings=sum(1 for f in open_findings if f.severity == "MINOR"),
        high_risk_findings=sum(1 for f in open_findings if f.severity in {"CRITICAL", "MAJOR"}),
        overdue_capa=len(overdue_capa),
        evidence_pending=int(evidence_pending),
        closure_percent=percent(len(closed_audits), len(audits)),
        average_closure_days=avg_closure_days,
    )

    # Lookup names in batch
    user_ids = {a.auditor_user_id for a in audits if a.auditor_user_id}
    dept_ids = {a.department_id for a in audits if a.department_id} | {
        f.department_id for f in findings if f.department_id
    }
    clause_ids = {f.clause_id for f in findings if f.clause_id}
    users = {
        u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all() if user_ids
    }
    departments = {
        d.id: d
        for d in db.scalars(select(Department).where(Department.id.in_(dept_ids))).all()
        if dept_ids
    }
    clauses = {
        c.id: c
        for c in db.scalars(select(AuditClause).where(AuditClause.id.in_(clause_ids))).all()
        if clause_ids
    }
    capas_by_finding: dict[UUID, list[AuditCapa]] = defaultdict(list)
    for capa in capas:
        capas_by_finding[capa.finding_id].append(capa)
    findings_by_audit: dict[UUID, list[AuditFinding]] = defaultdict(list)
    for finding in findings:
        findings_by_audit[finding.audit_id].append(finding)

    audit_rows: list[AuditDashboardAuditRowRead] = []
    for audit in audits:
        audit_findings = findings_by_audit.get(audit.id, [])
        open_count = sum(1 for f in audit_findings if f.status in OPEN_FINDING_STATUSES)
        capa_statuses = [c.status for f in audit_findings for c in capas_by_finding.get(f.id, [])]
        if any(s in OPEN_CAPA_STATUSES for s in capa_statuses):
            capa_status = "OPEN"
        elif capa_statuses:
            capa_status = "CLOSED"
        else:
            capa_status = "NONE"
        auditor = users.get(audit.auditor_user_id) if audit.auditor_user_id else None
        dept = departments.get(audit.department_id) if audit.department_id else None
        audit_rows.append(
            AuditDashboardAuditRowRead(
                id=audit.id,
                audit_number=audit.audit_number,
                audit_type=audit.audit_type,
                lab_audit_subtype=audit.lab_audit_subtype,
                title=audit.title,
                scope=audit.scope,
                process_name=audit.process_name,
                department_name=dept.name if dept else None,
                audit_date=aware(audit.planned_start_at)
                or aware(audit.started_at)
                or aware(audit.created_at),
                auditor_name=auditor.display_name if auditor else None,
                status=audit.status,
                findings=len(audit_findings),
                open_findings=open_count,
                compliance_percent=compliance_map.get(audit.id),
                capa_status=capa_status,
                is_demo=audit.is_demo,
            )
        )

    by_severity: dict[str, int] = defaultdict(int)
    for finding in findings:
        by_severity[finding.severity] += 1
    findings_by_severity = [
        AuditNamedCountRead(key=key, label=key.title(), count=count)
        for key, count in sorted(by_severity.items())
    ]

    by_dept: dict[str, int] = defaultdict(int)
    for finding in findings:
        if finding.department_id and finding.department_id in departments:
            by_dept[departments[finding.department_id].name] += 1
        else:
            by_dept["Unassigned"] += 1
    findings_by_department = [
        AuditNamedCountRead(key=name, label=name, count=count)
        for name, count in sorted(by_dept.items(), key=lambda item: (-item[1], item[0]))
    ]

    by_clause: dict[str, int] = defaultdict(int)
    for finding in findings:
        if finding.clause_id and finding.clause_id in clauses:
            clause = clauses[finding.clause_id]
            label = f"{clause.clause_code} · {clause.title}"
            by_clause[label] += 1
        else:
            by_clause["Unmapped"] += 1
    findings_by_clause = [
        AuditNamedCountRead(key=label, label=label, count=count)
        for label, count in sorted(by_clause.items(), key=lambda item: (-item[1], item[0]))
    ]

    by_process: dict[str, list[float]] = defaultdict(list)
    for audit in audits:
        value = compliance_map.get(audit.id)
        if value is None:
            continue
        key = audit.process_name or "Unspecified"
        by_process[key].append(value)
    compliance_by_process = [
        AuditNamedCountRead(
            key=name,
            label=name,
            count=len(values),
            value=round(sum(values) / len(values), 2) if values else None,
        )
        for name, values in sorted(by_process.items())
    ]

    by_dept_comp: dict[str, list[float]] = defaultdict(list)
    for audit in audits:
        value = compliance_map.get(audit.id)
        if value is None:
            continue
        name = (
            departments[audit.department_id].name
            if audit.department_id and audit.department_id in departments
            else "Unassigned"
        )
        by_dept_comp[name].append(value)
    compliance_by_department = [
        AuditNamedCountRead(
            key=name,
            label=name,
            count=len(values),
            value=round(sum(values) / len(values), 2) if values else None,
        )
        for name, values in sorted(by_dept_comp.items())
    ]

    # Monthly trends
    trend_buckets: dict[str, dict[str, float]] = defaultdict(
        lambda: {"audits": 0, "findings": 0, "compliance": 0, "comp_n": 0}
    )
    for audit in audits:
        stamp = aware(audit.planned_start_at) or aware(audit.started_at) or aware(audit.created_at)
        if stamp is None:
            continue
        key = stamp.strftime("%Y-%m")
        trend_buckets[key]["audits"] += 1
        value = compliance_map.get(audit.id)
        if value is not None:
            trend_buckets[key]["compliance"] += value
            trend_buckets[key]["comp_n"] += 1
    for finding in findings:
        stamp = aware(finding.created_at)
        if stamp is None:
            continue
        key = stamp.strftime("%Y-%m")
        trend_buckets[key]["findings"] += 1
    trends = [
        AuditTrendPointRead(
            label=key,
            audits=int(bucket["audits"]),
            findings=int(bucket["findings"]),
            compliance_percent=round(bucket["compliance"] / bucket["comp_n"], 2)
            if bucket["comp_n"]
            else None,
        )
        for key, bucket in sorted(trend_buckets.items())
    ]

    aging_buckets = {"0-7": 0, "8-30": 0, "31-60": 0, "60+": 0}
    for capa in capas:
        if capa.status == "CLOSED" or capa.due_at is None:
            continue
        due = aware(capa.due_at)
        if due is None:
            continue
        age = (now - due).days if due < now else 0
        if age <= 7:
            aging_buckets["0-7"] += 1
        elif age <= 30:
            aging_buckets["8-30"] += 1
        elif age <= 60:
            aging_buckets["31-60"] += 1
        else:
            aging_buckets["60+"] += 1
    capa_aging = [
        AuditNamedCountRead(key=key, label=f"{key} days", count=count)
        for key, count in aging_buckets.items()
    ]

    open_vs_closed = [
        AuditNamedCountRead(
            key="open",
            label="Open",
            count=sum(1 for f in findings if f.status in OPEN_FINDING_STATUSES),
        ),
        AuditNamedCountRead(
            key="closed",
            label="Closed",
            count=sum(1 for f in findings if f.status == "CLOSED"),
        ),
    ]

    alerts: list[AuditAlertRead] = []
    for finding in open_findings:
        if finding.severity == "CRITICAL":
            alerts.append(
                AuditAlertRead(
                    code="critical_finding_open",
                    severity="critical",
                    message=f"{finding.finding_number}: critical finding still open",
                    entity_type="finding",
                    entity_id=str(finding.id),
                )
            )
        due = aware(finding.due_at)
        if due and due < now:
            alerts.append(
                AuditAlertRead(
                    code="overdue_finding",
                    severity="warning",
                    message=f"{finding.finding_number}: finding overdue",
                    entity_type="finding",
                    entity_id=str(finding.id),
                )
            )
    for capa in overdue_capa:
        alerts.append(
            AuditAlertRead(
                code="overdue_capa",
                severity="warning",
                message=f"{capa.capa_number}: CAPA overdue",
                entity_type="capa",
                entity_id=str(capa.id),
            )
        )
    if evidence_pending:
        alerts.append(
            AuditAlertRead(
                code="evidence_pending",
                severity="info",
                message=f"{evidence_pending} evidence item(s) pending verification",
                entity_type="evidence",
                entity_id=None,
            )
        )

    return AuditDashboardRead(
        audit_type=audit_type,
        window_start=window_start,
        window_end=window_end,
        summary=summary,
        trends=trends,
        findings_by_clause=findings_by_clause,
        findings_by_department=findings_by_department,
        findings_by_severity=findings_by_severity,
        findings_open_vs_closed=open_vs_closed,
        compliance_by_department=compliance_by_department,
        compliance_by_process=compliance_by_process,
        capa_aging=capa_aging,
        audits=audit_rows,
        alerts=alerts[:50],
        query_batches=DASHBOARD_QUERY_BATCHES,
    )
