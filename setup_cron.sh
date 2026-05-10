#!/usr/bin/env bash
# Installs a daily cron job that runs daily_runner.py at 08:00 UTC.
# Run once: bash setup_cron.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$(command -v python3)"
CRON_CMD="0 8 * * * cd \"$REPO_DIR\" && $PYTHON daily_runner.py >> /tmp/memecoin-intel.log 2>&1"

# Load .env variables into cron environment
if [ -f "$REPO_DIR/.env" ]; then
  ENV_VARS=$(grep -v '^#' "$REPO_DIR/.env" | grep '=' | xargs)
  CRON_CMD="0 8 * * * env $ENV_VARS cd \"$REPO_DIR\" && $PYTHON daily_runner.py >> /tmp/memecoin-intel.log 2>&1"
fi

# Add to crontab (idempotent)
(crontab -l 2>/dev/null | grep -v "memecoin-intel"; echo "$CRON_CMD") | crontab -
echo "Cron job installed: daily_runner.py will run at 08:00 UTC every day."
echo "Logs → /tmp/memecoin-intel.log"
