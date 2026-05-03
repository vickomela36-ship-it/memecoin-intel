"""
Central configuration for memecoin-intel.
Values here are defaults; override via environment variables.
"""

import os

# Alert email
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "vickomela36@gmail.com")

# Notion database (data source ID for Memecoin Buy Signals Log)
NOTION_SIGNALS_DB = os.getenv(
    "NOTION_SIGNALS_DB",
    "73b5d85d-86bf-4b6e-b8d7-c43e92bc0391",
)

# How often (seconds) the runner sleeps between checks when run standalone
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "3600"))
