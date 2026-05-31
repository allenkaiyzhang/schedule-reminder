#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-schedule-reminder}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$PROJECT_ROOT/.venv}"
PYTHON="$VENV_DIR/bin/python"
LOG_FILE="${LOG_FILE:-$PROJECT_ROOT/deploy.log}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8030/health}"

mkdir -p "$PROJECT_ROOT/data" "$PROJECT_ROOT/logs"
touch "$LOG_FILE"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "Deploying $SERVICE_NAME from $PROJECT_ROOT"

cd "$PROJECT_ROOT"

if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
  echo "ERROR: $PROJECT_ROOT/.env is required. Create it from .env.example before deploying."
  exit 1
fi

if [[ ! -f "$PROJECT_ROOT/requirements.txt" ]]; then
  echo "ERROR: $PROJECT_ROOT/requirements.txt is required."
  exit 1
fi

if [[ ! -f "$PROJECT_ROOT/systemd/$SERVICE_NAME.service" ]]; then
  echo "ERROR: $PROJECT_ROOT/systemd/$SERVICE_NAME.service is required."
  exit 1
fi

if [[ ! -x "$PYTHON" ]]; then
  echo "Python executable missing or broken in $VENV_DIR; recreating venv."
  rm -rf "$VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

"$PYTHON" -m pip install -U pip
"$PYTHON" -m pip install -r "$PROJECT_ROOT/requirements.txt"

sudo cp "$PROJECT_ROOT/systemd/$SERVICE_NAME.service" "/etc/systemd/system/$SERVICE_NAME.service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

sleep 2
sudo systemctl --no-pager --full status "$SERVICE_NAME" || true

for attempt in $(seq 1 10); do
  if response="$(curl -fsS --max-time 5 "$HEALTH_URL")"; then
    echo "Health check passed: $response"
    echo "Deploy finished for $SERVICE_NAME"
    exit 0
  fi
  echo "Health check attempt $attempt failed"
  sleep 2
done

sudo journalctl -u "$SERVICE_NAME" -n 100 --no-pager || true
echo "ERROR: health check failed for $HEALTH_URL"
exit 1
