#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-schedule-reminder}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8030/health}"

if curl -fsS --max-time 5 "$HEALTH_URL" |
  grep -q '"status"[[:space:]]*:[[:space:]]*"ok"' &&
  curl -fsS --max-time 5 "$HEALTH_URL" |
    grep -q '"service"[[:space:]]*:[[:space:]]*"schedule-reminder"'; then
  echo "Smoke test passed"
  exit 0
fi

sudo systemctl --no-pager --full status "$SERVICE_NAME" || true
sudo journalctl -u "$SERVICE_NAME" -n 100 --no-pager || true
echo "Smoke test failed"
exit 1
