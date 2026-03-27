#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="mahoraga-sse.service"
SERVICE_PATH="${HOME}/.config/systemd/user/${SERVICE_NAME}"

if systemctl --user list-unit-files | grep -q "^${SERVICE_NAME}"; then
  echo "🛑 Stopping and disabling ${SERVICE_NAME}"
  systemctl --user disable --now "${SERVICE_NAME}" || true
fi

if [[ -f "${SERVICE_PATH}" ]]; then
  rm -f "${SERVICE_PATH}"
  echo "🗑️ Removed ${SERVICE_PATH}"
fi

systemctl --user daemon-reload
systemctl --user reset-failed || true

echo "✅ ${SERVICE_NAME} uninstalled"
