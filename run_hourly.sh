#!/usr/bin/env bash
# Wrapper called by cron every hour.
# Set GMAIL_APP_PASSWORD and NOTION_TOKEN in ~/.memecoin.env (never commit that file).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/notifier.log"
ENV_FILE="$HOME/.memecoin.env"

# Load credentials if the env file exists
if [[ -f "$ENV_FILE" ]]; then
    # shellcheck source=/dev/null
    set -a; source "$ENV_FILE"; set +a
fi

cd "$SCRIPT_DIR"
python3 notifier.py >> "$LOG_FILE" 2>&1
