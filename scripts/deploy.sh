#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-schedule-reminder}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"
PYTHON="$VENV_DIR/bin/python"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8030/health}"
SKIP_TESTS="${SKIP_TESTS:-0}"

cd "$PROJECT_ROOT"
mkdir -p data logs

if [[ ! -x "$PYTHON" ]]; then
  rm -rf "$VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

"$PYTHON" -m pip install -U pip
"$PYTHON" -m pip install -r requirements.txt
"$PYTHON" -m pip install pytest

if [[ "$SKIP_TESTS" != "1" ]]; then
  ENABLE_BOT=false DISABLE_TELEGRAM_SEND=true "$PYTHON" -m compileall .
  ENABLE_BOT=false DISABLE_TELEGRAM_SEND=true "$PYTHON" -m pytest -q
fi

sudo cp systemd/schedule-reminder.service /etc/systemd/system/schedule-reminder.service
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

sleep 2
sudo systemctl --no-pager --full status "$SERVICE_NAME" || true

for attempt in $(seq 1 10); do
  if curl -fsS --max-time 5 "$HEALTH_URL" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
    echo "Deploy finished for $SERVICE_NAME"
    exit 0
  fi
  echo "Health check attempt $attempt failed"
  sleep 2
done

sudo journalctl -u "$SERVICE_NAME" -n 100 --no-pager || true
exit 1
