# ADR-001 — Core platform for dual LaboraIQ operating modes

- Status: Proposed for review
- Date: 2026-07-27
- Jira: LAB-18, LAB-19, LAB-20, LAB-21, LAB-33
- Decision owners: Solution Architect and Laboratory Director

## Context

LaboraIQ must enhance an existing LIS (Mode A) and later operate as a complete LIS
(Mode B). The foundation must not couple tenant, identity, authorization, audit, or
evidence services to either clinical workflow. PostgreSQL is the operational system
of record. No clinical thresholds or patient workflows are decided here.

## Decision

Use a modular monolith for the MVP: a Next.js administration application, FastAPI
service modules, PostgreSQL, and reliable asynchronous integration through SQS.
Boundaries are explicit so high-volume workers can be extracted later without
changing ownership.

### Mode A boundary

```text
Analyzer / existing LIS -> on-prem connector -> integration ingress
-> raw evidence in S3 -> normalized message -> verification module (future)
-> decision handoff -> existing LIS
```

The source LIS owns patient/order master data and the final operational result
record. LaboraIQ owns normalized integration evidence, rule versions, decisions,
review evidence, and the handoff receipt. Integration contracts must be idempotent
and correlated; LaboraIQ never silently assumes the result was accepted.

### Mode B boundary

```text
Registration -> order -> collection/barcode -> analyzer work order
-> ingestion -> technical verification -> approval -> report
```

LaboraIQ owns the transactional patient, order, specimen, result, approval and report
records when those future modules are enabled. Each module owns writes to its tables;
other modules use defined service interfaces and events.

### Shared services and ownership

| Boundary | Owns | Does not own |
|---|---|---|
| Tenant configuration | organization, branch, department | clinical configuration |
| Identity and access | user reference, roles, permissions, scoped assignments | credentials |
| Audit | immutable event evidence | mutable business state |
| Integration | envelopes, raw payload references, delivery state | analyzer device control |
| Validation evidence | approved specifications and execution evidence | clinical claims |

Every tenant record carries `organization_id`. Authenticated identity resolves the
organization and allowed branches; client-supplied tenant context is never trusted.
Branch-scoped access is an additional restriction, not a replacement for tenant
scope. PostgreSQL row-level security is a future defence-in-depth option after the
application query policy stabilizes.

### Authentication and authorization

Authentication is an adapter boundary supporting OIDC/OAuth 2.0, Amazon Cognito, or
Microsoft Entra ID. The platform stores provider subject identifiers, not passwords.
Authorization uses configurable roles composed of granular permissions. Assignments
can be organization- or branch-scoped and effective-dated. The API is authoritative;
the UI only mirrors permission decisions.

### Audit trail

Safety-relevant mutations append actor, tenant/branch, action, before/after values,
correlation ID, network context, and timestamp in the same database transaction.
Sensitive fields are masked. The API has read-only audit routes; ORM listeners and a
PostgreSQL trigger reject update/delete. Longer-term tamper evidence may add signed
event batches exported to S3 Object Lock after quality review.

### Synchronous and asynchronous work

Interactive configuration commands are synchronous database transactions. Analyzer
messages, document generation, evidence export, and retriable external handoffs are
asynchronous. SQS provides visibility timeouts, bounded retries, and a dead-letter
queue. Consumers use idempotency keys and commit business state before acknowledging.
Failures retain the raw payload reference and correlation ID; DLQ replay is an
authorized and audited operation.

### Storage and analytics

PostgreSQL is the sole transactional source of truth. S3 holds raw integration files,
generated documents, and immutable validation evidence; KMS encrypts storage and SQS.
Kafka is not required for the MVP because there is no demonstrated multi-consumer
event-stream throughput or replay requirement that justifies its operational burden.
Databricks is not in the operational result path: analytics latency and availability
must never gate laboratory decisions. Future analytics consumes de-identified,
versioned exports or CDC into a separate lakehouse boundary.

### On-premises connector

The connector terminates analyzer/LIS protocols within the laboratory network,
buffers during WAN failure, signs/authenticates outbound envelopes, and never embeds
clinical decision logic. It is separately deployable and validated. Cloud services
accept only the versioned integration contract.

### Validation evidence

Each requirement maps through URS, FS, design component, Jira item, automated/manual
test, and IQ/OQ/PQ stage. CI preserves machine-readable results, dependency and secret
scan output, migration/build logs, and Terraform plans as controlled evidence after
the validation process is approved.

## Consequences

The modular monolith minimizes distributed failure modes while enforcing ownership.
Mode A and Mode B reuse governance controls without mixing result ownership. AWS
resources remain declarative and undeployed until credentials, networking, quality
review, and an approved plan are available.

