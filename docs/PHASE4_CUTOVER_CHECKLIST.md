# Phase 4 Cutover Checklist

This checklist turns the completed analyzer order/result path and LIS operational
message support into a controlled UAT and cutover sequence.

## Pre-cutover

1. Confirm the target branch contains the latest Alembic head and Phase 3/4 API changes.
2. Set the LIS transport configuration in the deployed `.env`:
   - `LIS_DISPATCH_MODE`
   - `LIS_OUTBOUND_HOST`
   - `LIS_OUTBOUND_PORT`
   - `LIS_OUTBOUND_USE_MLLP`
   - `LIS_OUTBOUND_TIMEOUT_SECONDS`
3. Validate analyzer configuration:
   - correct branch
   - `HL7_LAW` protocol
   - correct host/port
   - active test mappings only
4. Remove stale or duplicate analyzer mappings before UAT.
5. Back up the database before migration and cutover.

## Dry run

1. Run `alembic upgrade head`.
2. Start the Mac simulator or target middleware endpoint.
3. Create a UAT patient and order with mapped tests.
4. Complete specimen collection, receive, and accept.
5. Verify analyzer worklist creation.
6. Enqueue and process analyzer orders.
7. Confirm:
   - outbound `OML^O33` stored
   - inbound ACK stored
   - inbound `ORU^R01` stored
   - normalized result created
8. Trigger Phase 3 operational messages:
   - `POST /api/v1/specimens/{barcode}/lis-status`
   - `POST /api/v1/specimens/{barcode}/lis-storage`
   - `POST /api/v1/specimens/{barcode}/lis-routing-message`
9. If `LIS_DISPATCH_MODE=outbox_only`, run `POST /api/v1/lis-messages/process`.
10. Confirm LIS messages are marked `sent` or capture the exact failure reason.

## Clinical workflow verification

1. Perform technical review.
2. Perform pathologist validation.
3. Release the result.
4. Download the generated PDF report.
5. Verify units, flags, comments, and reference ranges on the released result.

## Cutover day

1. Freeze non-essential analyzer configuration changes.
2. Deploy application update and migrations.
3. Re-check TCP reachability to analyzer and LIS endpoints.
4. Process one controlled specimen first.
5. Review:
   - audit trail
   - analyzer messages
   - LIS integration messages
   - result status transitions
6. Only then move to the planned UAT/cutover batch.

## Rollback triggers

Rollback or switch to outbox-only if any of the following occurs:

- repeated HL7 ACK mismatches
- repeated NAKs for valid worklist traffic
- LIS message dispatch failures caused by endpoint instability
- incorrect analyzer mapping causing wrong machine test code routing
- normalization output that does not match expected clinical semantics

## Evidence to retain

- message samples for OML, ACK, ORU, and LIS operational events
- screenshots or exports of released results
- migration revision applied
- simulator or middleware endpoint used
- operator/date/time of dry run and cutover checks
