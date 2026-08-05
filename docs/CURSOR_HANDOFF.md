# LaboraIQ Cursor Handoff

Updated: 2026-08-05

## Purpose

LaboraIQ is a multi-tenant laboratory information system covering patient intake, billing, specimen accessioning, analyzer configuration, and the beginning of analyzer interfacing. This document is the implementation handoff for continuing development in Cursor.

## Repository layout

- `apps/api`: FastAPI, SQLAlchemy, Alembic; Neon PostgreSQL in local/prod, SQLite for tests/CI.
- `apps/web`: Next.js 16, React 19, TypeScript.
- `infrastructure`: AWS and deployment infrastructure.
- `tools/analyzer_tcp_simulator.py`: minimal TCP listener used for Mac-to-EC2 connectivity UAT.
- `docs`: architecture, security, validation, this handoff, and the production runbook.

## Current production deployment

- Public application: `https://app.laboraiq.workers.dev`
- EC2 public address: `16.16.97.239`
- Application directory: `/opt/laboraiq`
- API service: `laboraiq-api`
- Web service: `laboraiq-web`
- API binds to `127.0.0.1:8000`.
- Web binds to `127.0.0.1:3100`.
- Tailscale connects EC2 to the Mac analyzer simulator.
- Production deploys from GitHub `main` via `.github/workflows/deploy-ec2.yml` (Dascon-style SSH + git pull). See `docs/PRODUCTION_UAT_RUNBOOK.md`.


Do not commit SSH keys, Tailscale auth keys, passwords, cookies, tokens, or `.env` files.

## Completed workflows

### Patient intake

- Mandatory patient and visit information appears first.
- Returning-patient lookup supports UUID, patient number, phone, email, exact name, and unique partial name match.
- Duplicate patient names fail safely and request a stronger identifier.
- Test selection is searchable and uses real checkbox controls.
- Patient registration creates the order, invoice, and specimen records.

### Test master

- XLSX import endpoint accepts the LIS/HIS template.
- The production workbook import created 966 tests and 42 parameters across 8 panels.
- Production currently has 974 catalogue tests including the original seed tests.
- The source workbook had 25 rows with no service code; they were rejected instead of receiving invented clinical codes.
- 633 imported tests have missing specimen metadata and require review.
- Imported prices default to `0.00` and container type defaults to `Unspecified` because the workbook does not contain those columns.

### Payment and labels

- Supports UPI, card, and cash payment capture.
- Payment completion generates specimen identifiers.
- Labels render actual Code 128 SVG barcodes via `jsbarcode`.
- The encoded value is the unique specimen identifier only. Test codes should be printed as human-readable metadata, not embedded in the machine-readable payload.

### Specimen workflow

- Search/scan by specimen barcode.
- Collect specimen.
- Receive and generate accession number.
- Accept or reject specimen.
- Audit/status timestamps are stored.

### Analyzer configuration

- Configure analyzer vendor, model, code, protocol, host, port, mode, timeout, retry count, and heartbeat interval.
- Map LIS tests to analyzer-specific test codes.
- Map individual LIS parameters to analyzer parameter codes and units when the test master contains parameters.
- Deactivate or delete analyzer test mappings (including cleanup of incorrect Sysmex BIO0231→A4).
- Search the full test catalogue by code or name in the mapping dialog.
- Test TCP connections with retries and event logging.
- Run manual heartbeat probes.
- Outbound analyzer probes are restricted to private addresses plus `ANALYZER_OVERLAY_TARGETS` (Tailscale allowlist).

### Analyzer worklist

- Accepting a specimen creates pending worklist items for ordered tests with active mappings on active branch analyzers.
- List/filter worklist, enqueue to `queued`, and cancel items.
- UI available at `/analyzers/worklist`.

### Analyzer order queue (Phase 2)

- Enqueue creates an `AnalyzerOrderAttempt` in `queued` and advances the worklist item.
- `POST /analyzer-orders/process` drains queued attempts: `queued` → `sending` → `acknowledged` or retry/`failed`.
- Outbound payload is the stub `LABORAIQ-ORDER-V0` frame over TCP (not HL7 yet). Retries respect analyzer `retry_limit`.
- Immutable `AnalyzerMessage` rows store request (and optional response) payloads with correlation id and payload hash.
- Cancel fails open attempts. Worklist UI shows latest attempt state and a Process order queue action.
- HL7 LAW framing, ACK parsing, and result ingestion remain Phase 3+.

## Current UAT state

- Patient: `UAT Patient One`
- Patient number: `PT-20260805063253-9A7549`
- Order: `ORD-20260805063909-C2AA06`
- Specimen barcode: `LQ0805063919C2AA0601`
- Accession: `ACC-20260805-8F803AB9`
- Specimen status: `accepted`
- Ordered LIS test: `BIO0231 - A4 - ANDROSTENEDIONE TEST`
- Mac simulator analyzer: `MAC-UAT-01`
- Mapping on Mac simulator: `BIO0231 -> A4`
- Mac simulator endpoint: `100.122.201.68:55001`
- EC2-to-Mac TCP connection test: successful.

There is also an incorrect UAT mapping of `BIO0231 -> A4` on the Sysmex XN-1000 record. Add a delete/deactivate mapping action and remove it. Do not route this test to the Sysmex analyzer.

## Important limitations

1. The TCP simulator only accepts and closes connections. It does not parse or acknowledge analyzer messages.
2. `Connected` currently means TCP reachability only, not successful HL7/ASTM application-level communication.
3. Order queue sends a stub TCP payload; “acknowledged” means the remote accepted the TCP write, not an HL7 ACK.
4. There is no HL7/ASTM message framing, ACK/NAK handling, or result ingestion.
5. There is no result model, technical validation, pathologist validation, report release, or result PDF.
6. BIO0231 now has an Androstenedione parameter (`ANDRO`, unit `ng/mL`); reference limits remain pending clinical approval.
7. Most imported tests still need specimen/container and price review.
8. Analyzer overlay allowlisting is configured via `ANALYZER_OVERLAY_TARGETS`.
9. Production still uses development authentication headers and requires a production identity provider/security hardening before real patient use.

## Next implementation milestone

Build the analytical workflow in this order:

1. ~~Add analyzer mapping delete/deactivate support.~~
2. ~~Add test parameter editing, units, reference ranges, and critical thresholds.~~
3. ~~Create an analyzer worklist for accepted specimens whose requested tests have active mappings.~~
4. ~~Add an analyzer order state machine / sender: `queued` → `sending` → `acknowledged` / `failed`.~~
5. ~~Add persistent order attempts, correlation IDs, payload hashes, retries, and immutable message store.~~
6. Implement a real UAT protocol. Prefer HL7 v2.5.1/IHE LAW for the simulator unless a target analyzer manual requires ASTM.
7. Upgrade the Mac simulator to receive an order, validate barcode/test code, send ACK, and return a test result.
8. Store raw inbound/outbound messages separately from normalized results (request store exists; inbound/result path next).
9. Add result normalization by analyzer mapping, including units and flags.
10. Add technical review, pathologist validation, report release, and PDF output.

## Recommended message flow for the next UAT

```text
Accepted specimen
  -> analyzer worklist
  -> route BIO0231 using MAC-UAT-01 mapping
  -> transmit barcode LQ0805063919C2AA0601 and machine code A4
  -> Mac simulator ACK
  -> Mac simulator returns Androstenedione result
  -> normalize and store result
  -> technician review
  -> pathologist validation
  -> release report
```

## Development checks

API:

```bash
cd apps/api
PYTHONPATH=. ../../.venv/bin/pytest
../../.venv/bin/ruff check .
../../.venv/bin/mypy app
```

Web:

```bash
cd apps/web
npm ci
npm run typecheck
npm run lint
npm test
npm run build
```

## Key implementation files

- `apps/api/app/api.py`: API endpoints and workflow logic.
- `apps/api/app/analyzer_orders.py`: order queue sender, retries, stub TCP payload.
- `apps/api/app/models.py`: SQLAlchemy data model.
- `apps/api/app/schemas.py`: request/response contracts.
- `apps/api/migrations/versions/20260805_0008_analyzer_test_mapping.py`
- `apps/api/migrations/versions/20260805_0009_analyzer_connection_monitoring.py`
- `apps/api/migrations/versions/20260805_0010_analyzer_worklist_and_cleanup.py`
- `apps/api/migrations/versions/20260805_0011_analyzer_order_queue.py`
- `apps/web/app/(protected)/patients/new/page.tsx`
- `apps/web/app/(protected)/payments/[orderId]/page.tsx`
- `apps/web/app/(protected)/specimens/page.tsx`
- `apps/web/app/(protected)/analyzers/page.tsx`
- `apps/web/app/(protected)/analyzers/worklist/page.tsx`
- `apps/web/components/specimen-barcode.tsx`
- `tools/analyzer_tcp_simulator.py`

## Safety expectations

- Never guess a patient when a name is ambiguous.
- Never invent missing clinical test codes, units, reference ranges, or critical thresholds.
- Preserve raw analyzer messages and audit every normalized change.
- Treat TCP reachability, protocol acknowledgement, result acceptance, and clinical validation as separate states.
- Do not use the current system for real clinical decisions until validation, security hardening, and regulatory documentation are complete.
