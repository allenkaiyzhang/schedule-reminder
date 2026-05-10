#!/usr/bin/env bash
set -euo pipefail

# Convenience orchestrator for the split deployment.
# For production automation you can also run each service script directly:
#   /opt/ops-core/redeploy.sh
#   /opt/tg_schedule_bot/redeploy.sh

OPS_CORE_DIR="${OPS_CORE_DIR:-/opt/ops-core}"
TG_BOT_DIR="${TG_BOT_DIR:-/opt/tg_schedule_bot}"
DEPLOY_LOG="${DEPLOY_LOG:-./deploy.log}"

exec > >(tee -a "${DEPLOY_LOG}") 2>&1

echo "============================================================"
echo "Split deploy started at $(date -Is)"
echo "OPS_CORE_DIR=${OPS_CORE_DIR}"
echo "TG_BOT_DIR=${TG_BOT_DIR}"

if [ ! -x "${OPS_CORE_DIR}/redeploy.sh" ]; then
  echo "Missing executable redeploy script: ${OPS_CORE_DIR}/redeploy.sh"
  exit 1
fi

if [ ! -x "${TG_BOT_DIR}/redeploy.sh" ]; then
  echo "Missing executable redeploy script: ${TG_BOT_DIR}/redeploy.sh"
  exit 1
fi

echo "[1/2] redeploy ops-core"
"${OPS_CORE_DIR}/redeploy.sh"

echo "[2/2] redeploy tg_schedule_bot"
"${TG_BOT_DIR}/redeploy.sh"

echo "Split deploy finished at $(date -Is)"
