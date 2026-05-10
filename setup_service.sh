#!/usr/bin/env bash
# Installs the memecoin-intel daemon as a systemd service.
# Run once as root: sudo bash setup_service.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$REPO_DIR/memecoin-intel.service"

if [ ! -f "$REPO_DIR/.env" ]; then
  echo "ERROR: .env file not found. Copy .env.example to .env and fill in credentials first."
  exit 1
fi

cp "$SERVICE_FILE" /etc/systemd/system/memecoin-intel.service
systemctl daemon-reload
systemctl enable memecoin-intel
systemctl start memecoin-intel
systemctl status memecoin-intel --no-pager
echo ""
echo "Service installed and started. Logs: journalctl -u memecoin-intel -f"
