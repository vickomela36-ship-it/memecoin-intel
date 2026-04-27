#!/usr/bin/env bash
# Installs an hourly cron job that runs runner.py.
# Run once: bash setup_cron.sh
# Requires: NOTION_TOKEN, SMTP_USER, SMTP_PASSWORD set in your environment
#           (or hardcode them in the cron env block below).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"
LOG_FILE="${SCRIPT_DIR}/runner.log"
CRON_TAG="memecoin-intel"

# Resolve the python to use (prefer venv if present)
if [[ -f "${SCRIPT_DIR}/venv/bin/python" ]]; then
    PYTHON="${SCRIPT_DIR}/venv/bin/python"
fi

# Build the cron line — runs at minute 0 every hour
CRON_CMD="0 * * * * cd \"${SCRIPT_DIR}\" && \
NOTION_TOKEN=\"${NOTION_TOKEN:-CHANGE_ME}\" \
SMTP_USER=\"${SMTP_USER:-CHANGE_ME}\" \
SMTP_PASSWORD=\"${SMTP_PASSWORD:-CHANGE_ME}\" \
\"${PYTHON}\" runner.py >> \"${LOG_FILE}\" 2>&1  # ${CRON_TAG}"

# Remove any old entry for this project, then append the new one
(crontab -l 2>/dev/null | grep -v "${CRON_TAG}"; echo "${CRON_CMD}") | crontab -

echo "Cron job installed. Runs every hour."
echo "Logs → ${LOG_FILE}"
echo ""
echo "Current crontab:"
crontab -l | grep "${CRON_TAG}"
