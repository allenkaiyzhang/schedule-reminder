#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-schedule-reminder}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8030/health}"

for attempt in $(seq 1 10); do
  if response="$(curl -fsS --max-time 5 "$HEALTH_URL")"; then
    if echo "$response" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"' &&
       echo "$response" | grep -q '"service"[[:space:]]*:[[:space:]]*"schedule-reminder"'; then
      echo "Smoke test passed"
      exit 0
    fi
    echo "Health response did not match expected payload: $response"
  else
    echo "Health check attempt $attempt failed"
  fi
  sleep 2
done

sudo systemctl --no-pager --full status "$SERVICE_NAME" || true
sudo journalctl -u "$SERVICE_NAME" -n 100 --no-pager || true
echo "Smoke test failed"
exit 1
