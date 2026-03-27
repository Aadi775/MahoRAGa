#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="mahoraga-sse.service"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
SERVICE_PATH="${SYSTEMD_USER_DIR}/${SERVICE_NAME}"

PORT="${MAHORAGA_SSE_PORT:-8000}"
HOST="${MAHORAGA_SSE_HOST:-127.0.0.1}"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_PATH="${REPO_DIR}/.venv/bin/mahoraga-kg"

if [[ ! -x "${BIN_PATH}" ]]; then
  echo "❌ ${BIN_PATH} not found or not executable."
  echo "Run ./setup.sh first to create .venv and install mahoraga-kg."
  exit 1
fi

mkdir -p "${SYSTEMD_USER_DIR}"

cat > "${SERVICE_PATH}" <<EOF
[Unit]
Description=MahoRAGa SSE MCP Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${REPO_DIR}
ExecStart=${BIN_PATH} --transport sse --host ${HOST} --port ${PORT}
Restart=always
RestartSec=2
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

echo "🔧 Installed user service file: ${SERVICE_PATH}"

systemctl --user daemon-reload
systemctl --user enable --now "${SERVICE_NAME}"

echo "✅ ${SERVICE_NAME} enabled and started"
echo "📡 SSE endpoint: http://${HOST}:${PORT}/sse"

if command -v loginctl >/dev/null 2>&1; then
  if ! loginctl show-user "${USER}" -p Linger --value | grep -q "yes"; then
    echo
    echo "ℹ️ To start this user service at boot before login, enable linger:"
    echo "   sudo loginctl enable-linger ${USER}"
  fi
fi

echo
echo "Useful commands:"
echo "  systemctl --user status ${SERVICE_NAME}"
echo "  journalctl --user -u ${SERVICE_NAME} -f"
