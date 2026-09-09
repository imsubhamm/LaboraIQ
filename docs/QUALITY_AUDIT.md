# Quality audit architecture (NABL + LAB)

Two UI modules — **NABL Audit Report** and **LAB Audit Report** — share one
quality-audit domain. System activity remains on immutable `audit_events`
(`record_event`). No second audit-log table.

## Why these tables

| Table | Why |
| --- | --- |
| `audits` | One engagement/event (`audit_type` = `NABL` \| `INTERNAL`) |
| `audit_checklists` / `audit_checklist_items` | Reusable checklist templates |
| `audit_check_results` | One evaluation of one item in one audit |
| `audit_findings` | Generic findings (severity ≠ finding_type) |
| `audit_capas` | CAPA linked to a finding |
| `audit_evidence` | Evidence linked to audit / finding / CAPA |
| `audit_standards` / `audit_clauses` | Configurable accreditation hierarchy (not hard-coded NABL text) |

## Intentionally NOT created

- Separate `nabl_*` / `lab_*` CRUD stacks or dashboard-per-chart APIs
- Duplicate users/roles/permissions/org/branch tables
- Duplicate analyzer/specimen/result copies (findings store optional FKs only)
- Extra alert tables (alerts are derived in `GET /audit-dashboard`)
- Reuse of `audit.read` for this module — that permission is the **system**
  AuditEvent trail at `/audit`. Quality module uses `quality_audit.*`.

## Reused LIS pieces

Organization, Branch, Department, User, RBAC, `AuthContext` scoping,
`record_event`, Resource/shell UI, `TrendChart`-style SVG charts, `page()` /
FastAPI patterns, Alembic.

## Fact grains

| Fact | Grain |
| --- | --- |
| FACT_AUDIT | One `audits` row |
| FACT_AUDIT_CHECK | One `audit_check_results` row |
| FACT_AUDIT_FINDING | One `audit_findings` row |
| FACT_CAPA | One `audit_capas` row |
| FACT_AUDIT_EVIDENCE | One `audit_evidence` row |

Dimensions: organization, branch, department, user, analyzer (optional FK),
audit type, standard, clause, finding type, severity, status, calendar date.

## KPI formulas (backend-centralized)

- **Compliance %** = compliant applicable checks / applicable checks × 100  
  Applicable = result ≠ `NOT_APPLICABLE`. Compliant = `COMPLIANT`.
- **Closure %** = closed audits / total audits in scope × 100
- **CAPA overdue** = status not `CLOSED` and `due_at` &lt; now
- **Evidence pending** = evidence with `verification_status` = `PENDING`
- Average closure days = mean(`closed_at` − `started_at` or `planned_start_at`) for closed audits

## Lifecycles (validated in `app/quality_audit.py`)

**Audit:** `DRAFT` → `SCHEDULED` → `IN_PROGRESS` → `COMPLETED` →
`FINDINGS_REVIEW` → `CAPA_PENDING` → `VERIFICATION` → `CLOSED`  
(forward-only; skip allowed only via explicit service transitions that still
require a valid edge).

**Finding:** `OPEN` → `ROOT_CAUSE_ANALYSIS` → `CAPA_ASSIGNED` →
`ACTION_IN_PROGRESS` → `EFFECTIVENESS_REVIEW` → `CLOSED`

**CAPA:** `OPEN` → `ROOT_CAUSE_ANALYSIS` → `ACTION_IN_PROGRESS` →
`EFFECTIVENESS_REVIEW` → `CLOSED`

## API surface

| Method | Path | Permission |
| --- | --- | --- |
| GET/POST | `/audits` | read / manage |
| GET/PATCH | `/audits/{id}` | read / manage |
| GET/POST | `/audits/{id}/checks` | read / manage |
| GET/POST | `/audits/{id}/findings` | read / manage |
| GET/POST | `/audits/{id}/evidence` | read / manage |
| GET/PATCH | `/findings/{id}` | read / manage |
| GET/POST | `/findings/{id}/capa` | read / manage |
| PATCH | `/capa/{id}` | manage |
| GET | `/audit-checklists` | read |
| GET | `/audit-standards` | read |
| GET | `/audit-dashboard?audit_type=` | read |

One dashboard response: `summary`, `trends`, breakdowns, `audits`, `alerts`.

## Permissions

- `quality_audit.read` — list/view audits, findings, CAPA, dashboard
- `quality_audit.manage` — create/update, evaluate checks, CAPA, evidence, close

Quality Manager / Auditor role templates include these.

## NABL vs LAB

Same engine. UI filters `audit_type=NABL` or `INTERNAL`. NABL filters also use
standard/clause. LAB uses `lab_audit_subtype` / process / department. Standards
and clauses are seeded as **synthetic DEMO** placeholders only — never invent
real accreditation clause text as authoritative content.
