#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-schedule-reminder}"
LINES="${LINES:-120}"
LOCAL_LOG="${LOCAL_LOG:-logs/schedule-reminder.log}"

sudo journalctl -u "$SERVICE_NAME" -n "$LINES" --no-pager || true
if [[ -f "$LOCAL_LOG" ]]; then
  tail -n "$LINES" "$LOCAL_LOG"
fi
