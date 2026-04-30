#!/usr/bin/env bash
# Hourly memecoin signal checker — invoked by cron every hour.
# Runs Claude CLI in print mode so it can use Gmail + Notion MCP tools.

set -euo pipefail

PROJECT_DIR="/home/user/memecoin-intel"
LOG_FILE="$PROJECT_DIR/logs/runs.log"
CLAUDE_BIN="/opt/node22/bin/claude"

PROMPT='Run `python /home/user/memecoin-intel/run_hourly.py` and parse the JSON output.

For each item in the "actions" array (these are "buy now" signals):
1. Send an email via Gmail MCP to the "to" address using the "subject" and "body" from that action.
2. Create a new page in Notion using data_source_id "c7f3d2af-bf40-4406-9e7f-b998f7123168" with these properties:
   - Token = signal.token
   - Signal = "buy now"
   - "Price USD" = signal.price_usd
   - "24h Change %" = signal.change_24h
   - "Volume 24h" = signal.volume_24h
   - "Market Cap" = signal.market_cap
   - "Email Sent" = "__YES__"
   - Notes = signal.reason

If the "actions" array is empty, print: "Scan complete — 0 buy now signals."'

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting hourly signal check" >> "$LOG_FILE"

"$CLAUDE_BIN" --print "$PROMPT" >> "$LOG_FILE" 2>&1

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Check complete" >> "$LOG_FILE"
