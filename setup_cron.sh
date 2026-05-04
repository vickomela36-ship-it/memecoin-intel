#!/usr/bin/env bash
# Installs an hourly cron job for the memecoin buy-signal monitor.
# Run once: bash setup_cron.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$(which python3)"

# Ensure .env exists
if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
  echo "ERROR: .env not found. Copy .env.example to .env and fill in credentials."
  exit 1
fi

# Install Python dependencies if needed
"$PYTHON" -m pip install -q -r "$SCRIPT_DIR/requirements.txt"

CRON_LINE="0 * * * * cd \"$SCRIPT_DIR\" && \"$PYTHON\" monitor.py >> \"$SCRIPT_DIR/monitor.log\" 2>&1"

# Add to crontab (idempotent — removes old entry first)
(
  crontab -l 2>/dev/null | grep -v "memecoin-intel.*monitor.py" || true
  echo "$CRON_LINE"
) | crontab -

echo "Cron job installed (runs every hour at :00):"
echo "  $CRON_LINE"
echo ""
echo "Test run now?  python3 monitor.py"
