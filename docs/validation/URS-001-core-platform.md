# URS-001 — Core platform user requirements

Status: Controlled draft · Version 0.1 · Owner: Quality

| ID | User requirement | Verification |
|---|---|---|
| URS-CORE-001 | The system shall isolate all tenant-owned data by organization. | OQ tenant isolation |
| URS-CORE-002 | The system shall restrict branch-scoped users to assigned branches. | OQ branch isolation |
| URS-CORE-003 | Authorized admins shall create, update and deactivate branches. | OQ API/UI |
| URS-CORE-004 | Roles shall be configurable from granular permissions. | OQ RBAC matrix |
| URS-CORE-005 | Role assignments shall support organization/branch scope and effective dates. | OQ assignment |
| URS-CORE-006 | Unauthenticated and unauthorized access shall return 401 and 403 respectively. | OQ security |
| URS-CORE-007 | Credentials shall remain with an approved external identity provider. | Design review |
| URS-CORE-008 | Safety-relevant configuration changes shall produce immutable audit events. | OQ audit |
| URS-CORE-009 | Audit records shall include actor, timestamp, context, correlation and before/after data. | OQ audit |
| URS-CORE-010 | Sensitive authentication values shall not appear in logs or audit values. | Code/test review |
| URS-CORE-011 | Transactional records shall retain referential and uniqueness integrity. | Migration/integration test |
| URS-CORE-012 | Database backups shall be encrypted, retained and restore-tested. | IQ/PQ deployment |
| URS-CORE-013 | Requirements, design, Jira work and tests shall be traceable. | RTM review |
| URS-CORE-014 | Configuration lists shall support deterministic pagination and filtering. | OQ API/UI |

