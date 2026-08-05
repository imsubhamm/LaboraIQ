# LaboraIQ Production and UAT Runbook

Updated: 2026-08-05

## Deployment overview

- Public URL: `https://app.laboraiq.workers.dev`
- EC2: `16.16.97.239`
- Remote application root: `/opt/laboraiq`
- API systemd unit: `laboraiq-api`
- Web systemd unit: `laboraiq-web`

Credentials are intentionally excluded. Use the approved local SSH configuration and never copy private keys into the repository.

## Production deployment

Production pipeline on `main`:

1. Merge a PR → **Core platform CI** runs once.
2. If CI succeeds → **Deploy to EC2** starts (no parallel push trigger).
3. Manual deploy remains available via `workflow_dispatch` / `gh workflow run`.

Deploy SSHs to EC2, `git reset --hard origin/main`, reinstalls API deps, rebuilds the web app, and restarts `laboraiq-api` / `laboraiq-web`.

Required GitHub Actions secrets:

- `EC2_HOST` — `16.16.97.239`
- `EC2_USER` — `ubuntu`
- `EC2_SSH_KEY` — private key that can SSH to the instance

One-time EC2 bootstrap (preserves `.env`, backups, and local venvs):

```bash
ssh -i <key.pem> ubuntu@16.16.97.239
cd /opt/laboraiq
bash scripts/bootstrap-ec2-git.sh
```

Manual deploy on the box (same steps as CI):

```bash
cd /opt/laboraiq
bash scripts/deploy-ec2.sh
```

Or trigger from GitHub:

```bash
gh workflow run deploy-ec2.yml --repo imsubhamm/LaboraIQ
```

When API models change, ensure the Alembic migration is on `main` before deploy. The API service runs `alembic upgrade head` as `ExecStartPre`.

Review logs with:

```bash
sudo journalctl -u laboraiq-api -n 100 --no-pager
sudo journalctl -u laboraiq-web -n 100 --no-pager
```

## Mac analyzer simulator

HL7 LAW MLLP listener (order → ACK → optional ORU):

```bash
python3 tools/analyzer_tcp_simulator.py --host 100.122.201.68 --port 55001 \
  --analyzer-code MAC-UAT-01 --expected-test-code A4
```

Use `--no-result` for ACK-only. Optional `--expected-barcode` rejects mismatched specimen IDs with MSA AE.

The Mac and EC2 must both be connected to the same Tailscale network. Current analyzer configuration:

- Analyzer code: `MAC-UAT-01`
- Host: `100.122.201.68`
- Port: `55001`
- Protocol: `HL7_LAW`
- Mode: bidirectional MLLP order/ACK/result exchange for UAT.

## End-to-end UAT completed so far

1. Register or find patient.
2. Select requested test.
3. Create order and invoice.
4. Record payment.
5. Generate and print a real Code 128 specimen label.
6. Scan the specimen ID.
7. Collect specimen.
8. Receive specimen and assign accession number.
9. Accept specimen.
10. Map LIS test `BIO0231` to Mac simulator code `A4`.
11. Test EC2-to-Mac TCP connection successfully.

## Barcode verification

The barcode payload for the current UAT specimen is:

```text
LQ0805063919C2AA0601
```

A scanner must return that exact value. The barcode intentionally contains only the unique specimen identifier. Patient, order, requested tests, analyzer routing, and workflow status are resolved from the database after scanning.

Use 100% print scale. Do not use browser fit-to-page scaling for small tube labels without rescanning the result.

## Analyzer mapping UAT

Correct mapping:

```text
MAC-UAT-01
LIS test: BIO0231
Machine test code: A4
```

Incorrect mapping currently present and requiring removal:

```text
HEM-01 / Sysmex XN-1000
BIO0231 -> A4
```

## Current stopping point

Order transmission and application ACK/ORU capture are implemented for `HL7_LAW`. The next UAT gate is result normalization and clinical release:

- Worklist created from the accepted specimen.
- Correct analyzer selected from the active mapping.
- OML^O33 order transmitted over MLLP.
- Application-level ACK (MSA AA) received.
- ORU result message returned and stored raw.
- Result matched/normalized to the specimen and requested test (Phase 4).
- Unit and reference range applied (Phase 4).
- Result reviewed and released (Phase 4).

## Operational cautions

- `Connected` means TCP connection established, not analyzer protocol validated.
- Tests showing `specimen` or container `Unspecified` need test-master correction.
- Imported zero prices are placeholders, not approved billing tariffs.
- Do not use UAT patient, order, analyzer, or result data for clinical care.
- Back up the production database before applying schema migrations or bulk master-data changes.
