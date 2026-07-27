# LaboraIQ

LaboraIQ is a cloud Laboratory Information System foundation that supports both
existing-LIS enhancement (Mode A) and a future complete LIS (Mode B). Milestone 1
contains tenant/branch configuration, identity abstraction, configurable RBAC,
immutable audit evidence, administration UI, validation drafts, and an undeployed AWS
Terraform baseline. It contains no patient workflow or clinical decision rules.

## Structure

```text
apps/api                 FastAPI, SQLAlchemy, Alembic and Pytest
apps/web                 Next.js App Router administration UI
infrastructure/terraform Encrypted AWS baseline
docs/architecture        Architecture decisions
docs/validation          URS/FS/DS/RTM/IQ/OQ/PQ/risk drafts
docs/security            Security controls and production gaps
sales                    Existing business-development data (preserved)
```

## Local start

Prerequisites: Docker with Compose.

```bash
cp .env.example .env
docker compose up --build
```

Open the UI at `http://localhost:3000`, API docs at
`http://localhost:8000/api/docs`, liveness at `/api/v1/health`, and readiness at
`/api/v1/ready`. The development identity is synthetic and configured by `.env`.
Never enable the development provider in a production environment.

Migration and seed commands:

```bash
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m app.seed
```

Local checks (with Python 3.12 and Node 22):

```bash
cd apps/api && pip install -e ".[dev]" && pytest && ruff check . && mypy app
cd apps/web && npm ci && npm test && npm run lint && npm run typecheck && npm run build
cd infrastructure/terraform && terraform fmt -check -recursive && terraform init -backend=false && terraform validate
```

## Authentication and API context

For local development, requests use `X-Dev-User-Email` to identify an already
provisioned synthetic user. Organization and branch scope are resolved from that
user's active assignments; tenant IDs are not accepted from request bodies.
Production requires the documented OIDC adapter and gateway controls.

## AWS

Terraform is plan-only until explicit AWS credentials, approved network/ingress
design, quality review and deployment approval exist. See
`infrastructure/terraform/README.md`. Do not commit tfvars, state, credentials, or
secret values.

