#!/usr/bin/env bash
# Manual one-shot deploy on the EC2 box (same steps as CI).
# Run as ubuntu from /opt/laboraiq after the directory is a git checkout of main.
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/laboraiq}"
BRANCH="${BRANCH:-main}"

cd "$APP_ROOT"

if [[ ! -d .git ]]; then
  echo "ERROR: $APP_ROOT is not a git repository."
  echo "Bootstrap once with: scripts/bootstrap-ec2-git.sh"
  exit 1
fi

echo "== Sync $BRANCH =="
git remote set-url origin https://github.com/imsubhamm/LaboraIQ.git
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"
git clean -fd --exclude=.env --exclude=backups --exclude=apps/api/.venv --exclude=apps/web/node_modules --exclude=apps/web/.next

echo "== API dependencies =="
cd "$APP_ROOT/apps/api"
if [[ ! -x .venv/bin/pip ]]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -e . -q

echo "== Restart API =="
sudo systemctl restart laboraiq-api

echo "== Web build =="
cd "$APP_ROOT/apps/web"
npm ci
npm run build

echo "== Restart web =="
sudo systemctl restart laboraiq-web

echo "== Health check =="
for _ in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/v1/health || true)
  if [[ "$code" == "200" ]]; then
    sudo systemctl is-active laboraiq-api laboraiq-web
    echo "Deploy OK"
    exit 0
  fi
  sleep 2
done

echo "API did not become healthy in time"
sudo journalctl -u laboraiq-api -n 80 --no-pager
exit 1
