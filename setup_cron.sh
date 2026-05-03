#!/usr/bin/env bash
# Install the hourly memecoin signal cron job.
# Run once: bash setup_cron.sh
#
# Required env vars (add to ~/.bashrc or ~/.zshrc before running):
#   export GMAIL_APP_PASSWORD="your-gmail-app-password"
#   export NOTION_TOKEN="ntn_xxxxxxxxxxxxxxxxxxxx"
#
# Optional:
#   export COINGECKO_API_KEY="your-demo-key"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$(which python3 || which python)"
RUNNER="$SCRIPT_DIR/signal_runner.py"
LOG="$SCRIPT_DIR/runner.log"

if [[ ! -f "$RUNNER" ]]; then
  echo "ERROR: $RUNNER not found. Run this from the memecoin-intel directory."
  exit 1
fi

# Build the cron line: every hour at :00
CRON_LINE="0 * * * * cd $SCRIPT_DIR && GMAIL_APP_PASSWORD=\$GMAIL_APP_PASSWORD NOTION_TOKEN=\$NOTION_TOKEN $PYTHON $RUNNER >> $LOG 2>&1"

# Remove any existing memecoin-intel cron entry then add fresh one
( crontab -l 2>/dev/null | grep -v "signal_runner"; echo "$CRON_LINE" ) | crontab -

echo "✓ Cron job installed. Runs every hour."
echo "  Log file: $LOG"
echo "  View jobs: crontab -l"
echo "  Remove:    crontab -l | grep -v signal_runner | crontab -"
echo ""
echo "Run a quick test now:"
echo "  python $RUNNER --test"
