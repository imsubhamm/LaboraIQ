# DS-001 — Core platform design specification

Status: Controlled draft · Version 0.1

The Next.js App Router UI calls a typed API adapter. FastAPI routers delegate
authentication, permission, tenant-query and audit concerns. SQLAlchemy models use
UUID identifiers, foreign keys, scoped unique constraints and timezone-aware
timestamps. Alembic owns schema evolution. PostgreSQL is authoritative.

Core tables: `organizations`, `branches`, `departments`, `users`, `roles`,
`permissions`, `role_permissions`, `user_role_assignments`, and `audit_events`.
Audit mutation is blocked in the ORM and by PostgreSQL trigger. Cross-tenant lookups
combine primary key and authenticated `organization_id`; branch restrictions are
then applied. Correlation middleware supplies a stable request identifier.

The development auth adapter accepts a provisioned synthetic identity. Production
must disable it and configure an OIDC adapter with signed-token verification,
issuer/audience allowlists, session expiry and revocation. Terraform establishes
private RDS, encrypted S3/SQS/KMS/secrets/logging and an ECS cluster boundary.

