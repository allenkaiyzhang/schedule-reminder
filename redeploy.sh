#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/tg_schedule_bot"
SERVICE_NAME="tg_schedule_bot"
PYTHON_BIN="${APP_DIR}/.venv/bin/python"
PIP_BIN="${PYTHON_BIN} -m pip"
DEPLOY_LOG="${APP_DIR}/deploy.log"

mkdir -p "$(dirname "${DEPLOY_LOG}")"
exec > >(tee -a "${DEPLOY_LOG}") 2>&1

echo "============================================================"
echo "Deploy started at $(date -Is)"
echo "APP_DIR=${APP_DIR}"
echo "SERVICE_NAME=${SERVICE_NAME}"

cd "${APP_DIR}"

echo "[1/7] git pull"
git pull

echo "[2/7] checking virtualenv"
if [ ! -x "${PYTHON_BIN}" ]; then
  python3.11 -m venv "${APP_DIR}/.venv"
fi

echo "[3/7] installing requirements"
${PIP_BIN} install --upgrade pip
${PIP_BIN} install -r "${APP_DIR}/requirements.txt"

echo "[4/7] checking required config files"
for required in ".env" "projects.yaml" "keys/control_key"; do
  if [ ! -e "${APP_DIR}/${required}" ]; then
    echo "Missing required file: ${APP_DIR}/${required}"
    exit 1
  fi
done

echo "[5/7] systemctl daemon-reload"
systemctl daemon-reload

echo "[6/7] restarting service"
systemctl restart "${SERVICE_NAME}"

echo "[7/7] service status"
systemctl --no-pager --full status "${SERVICE_NAME}"

echo "Deploy finished at $(date -Is)"
