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

Production deploys from GitHub `main` the same way as Dascon: push (or manual workflow dispatch) runs `.github/workflows/deploy-ec2.yml`, which SSHs to EC2, `git reset --hard origin/main`, reinstalls API deps, rebuilds the web app, and restarts `laboraiq-api` / `laboraiq-web`.

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

The current simulator is a connectivity-only TCP listener:

```bash
python3 tools/analyzer_tcp_simulator.py --host 100.122.201.68 --port 55001
```

The Mac and EC2 must both be connected to the same Tailscale network. Current analyzer configuration:

- Analyzer code: `MAC-UAT-01`
- Host: `100.122.201.68`
- Port: `55001`
- Mode: bidirectional configuration, but message exchange is not implemented.
- Current protocol label: vendor proprietary.

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

The current system stops after TCP reachability. It does not yet send the accepted specimen to the simulator.

The next UAT should not be considered successful until all of these are independently demonstrated:

- Worklist created from the accepted specimen.
- Correct analyzer selected from the active mapping.
- Order message transmitted.
- Application-level acknowledgement received.
- Result message returned.
- Result matched to the specimen and requested test.
- Unit and reference range applied.
- Result reviewed and released.

## Operational cautions

- `Connected` means TCP connection established, not analyzer protocol validated.
- Tests showing `specimen` or container `Unspecified` need test-master correction.
- Imported zero prices are placeholders, not approved billing tariffs.
- Do not use UAT patient, order, analyzer, or result data for clinical care.
- Back up the production database before applying schema migrations or bulk master-data changes.
