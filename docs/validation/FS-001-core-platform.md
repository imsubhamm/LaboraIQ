# FS-001 — Core platform functional specification

Status: Controlled draft · Version 0.1

| ID | Function |
|---|---|
| FS-CORE-001 | Resolve tenant and branch scope from the authenticated user and active role assignments. |
| FS-CORE-002 | Enforce named permissions through backend dependencies; suppress unavailable UI actions. |
| FS-CORE-003 | Maintain organizations, branches, departments and external-provider user identities through `/api/v1`. |
| FS-CORE-004 | Compose configurable roles and create effective-dated, scoped assignments; revocation deactivates evidence. |
| FS-CORE-005 | Append audit events in the mutation transaction and expose only tenant-scoped GET operations. |
| FS-CORE-006 | Return 401 for absent/expired identity, 403 for insufficient authority, 404 for tenant-hidden resources, 409 for uniqueness conflict, and 422 for invalid input. |
| FS-CORE-007 | Return stable list envelopes containing items, total, limit and offset with deterministic secondary ID sorting. |
| FS-CORE-008 | Provide liveness and database readiness probes independent of clinical modules. |
| FS-CORE-009 | Seed synthetic, non-clinical development configuration only. |

