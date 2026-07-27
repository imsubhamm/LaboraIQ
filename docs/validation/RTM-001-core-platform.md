# RTM-001 — Core platform requirements traceability

Status: Controlled draft · Version 0.1

| URS | Functional spec / design | Jira | Test case | Stage | Approval |
|---|---|---|---|---|---|
| URS-CORE-001 | FS-001 / tenant query policy | LAB-19 | `test_tenant_isolation_returns_not_found` | OQ | Draft |
| URS-CORE-002 | FS-001 / branch context | LAB-19 | `test_branch_isolation` | OQ | Draft |
| URS-CORE-003 | FS-003 / branch API and UI | LAB-19 | `test_branch_and_department_crud`; UI suite | OQ | Draft |
| URS-CORE-004 | FS-002, FS-004 / RBAC tables | LAB-20 | `test_rbac_forbidden` | OQ | Draft |
| URS-CORE-005 | FS-004 / assignment model | LAB-20 | `test_role_assignment_and_deactivation` | OQ | Draft |
| URS-CORE-006 | FS-006 / auth dependencies | LAB-20 | `test_unauthorized_without_override`; `test_rbac_forbidden` | OQ | Draft |
| URS-CORE-007 | FS-003 / auth adapter | LAB-20 | design review | IQ/OQ | Draft |
| URS-CORE-008 | FS-005 / append-only audit | LAB-21 | `test_audit_event_is_immutable` | OQ | Draft |
| URS-CORE-009 | FS-005 / event schema | LAB-21 | `test_organization_read_and_update_are_audited` | OQ | Draft |
| URS-CORE-010 | audit masking / structured logging | LAB-21 | security review | OQ | Draft |
| URS-CORE-011 | SQLAlchemy/Alembic constraints | LAB-19 | duplicate and migration tests | IQ/OQ | Draft |
| URS-CORE-012 | RDS backup/KMS design | LAB-33 | restore protocol (pending deployed env) | IQ/PQ | Draft |
| URS-CORE-013 | validation document set | LAB-18 | RTM review | IQ | Draft |
| URS-CORE-014 | versioned list APIs / resource UI | LAB-19 | API/UI tests | OQ | Draft |

