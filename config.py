"""
Central configuration — override via environment variables.
"""

import os

# Recipient for buy-now email alerts
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "vickomela36@gmail.com")

# Comma-separated DexScreener Solana pair addresses to monitor
# e.g. TRACKED_PAIRS=abc123,def456
TRACKED_PAIRS_RAW = os.environ.get("TRACKED_PAIRS", "")

# Notion database ID for signal logs (set after first run creates it)
NOTION_DB_ID = os.environ.get("NOTION_DB_ID", "")

# How often to check signals (seconds). Default = 3600 (1 hour)
CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL_SECONDS", 3600))
