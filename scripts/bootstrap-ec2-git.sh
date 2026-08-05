#!/usr/bin/env bash
# One-time: turn /opt/laboraiq into a git checkout without wiping .env / venv / backups.
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/laboraiq}"
BRANCH="${BRANCH:-main}"

cd "$APP_ROOT"

if [[ -d .git ]]; then
  echo "Already a git repository at $APP_ROOT"
  git remote -v
  git status -sb
  exit 0
fi

if [[ ! -f .env ]]; then
  echo "ERROR: refusing to bootstrap without $APP_ROOT/.env"
  exit 1
fi

git init
git remote add origin https://github.com/imsubhamm/LaboraIQ.git
git fetch origin "$BRANCH"
git checkout -f -B "$BRANCH" "origin/$BRANCH"

echo "Bootstrap complete. Untracked local data preserved (.env, backups, .venv, node_modules, .next)."
git status -sb
