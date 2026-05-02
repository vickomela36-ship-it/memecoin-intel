#!/usr/bin/env bash
# Installs an hourly cron job that runs monitor.py.
# Run once after setting up your .env file:
#   chmod +x setup_cron.sh && ./setup_cron.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$(command -v python3)"
CRON_LINE="0 * * * * cd \"$SCRIPT_DIR\" && \"$PYTHON\" monitor.py >> \"$SCRIPT_DIR/cron.log\" 2>&1"

# Append only if not already present
if crontab -l 2>/dev/null | grep -qF "monitor.py"; then
    echo "Cron job already installed:"
    crontab -l | grep "monitor.py"
else
    (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
    echo "Cron job installed:"
    crontab -l | grep "monitor.py"
fi
