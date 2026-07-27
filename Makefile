.PHONY: dev migrate seed test lint build

dev:
	docker compose up --build

migrate:
	docker compose run --rm api alembic upgrade head

seed:
	docker compose run --rm api python -m app.seed

test:
	cd apps/api && pytest
	cd apps/web && npm test

lint:
	cd apps/api && ruff check . && mypy app
	cd apps/web && npm run lint && npm run typecheck

build:
	cd apps/web && npm run build

