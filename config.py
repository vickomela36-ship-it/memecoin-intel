"""
Central config for memecoin-intel.

All sensitive values come from environment variables.
Copy .env.example to .env and fill in your values for local development.
"""

import os

# ── Gmail ─────────────────────────────────────────────────────────────────────
GMAIL_SENDER_EMAIL: str = os.getenv("GMAIL_SENDER_EMAIL", "")
GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "")
ALERT_RECIPIENT: str = os.getenv("ALERT_RECIPIENT", "vickomela36@gmail.com")

# ── Notion ─────────────────────────────────────────────────────────────────────
NOTION_TOKEN: str = os.getenv("NOTION_TOKEN", "")
# Database created at: https://www.notion.so/685b3530321a4a7ea5af6553774f29b0
NOTION_DATABASE_ID: str = os.getenv("NOTION_DATABASE_ID", "685b3530-321a-4a7e-a5af-6553774f29b0")

# ── Signal thresholds (override via env if needed) ────────────────────────────
BUY_CHANGE_MIN: float = float(os.getenv("BUY_CHANGE_MIN", "15.0"))
BUY_CHANGE_MAX: float = float(os.getenv("BUY_CHANGE_MAX", "150.0"))
BUY_VOLUME_MIN: float = float(os.getenv("BUY_VOLUME_MIN", "200000"))
BUY_LIQUIDITY_MIN: float = float(os.getenv("BUY_LIQUIDITY_MIN", "30000"))


def validate() -> list[str]:
    """Return a list of missing required config keys."""
    missing = []
    if not GMAIL_SENDER_EMAIL:
        missing.append("GMAIL_SENDER_EMAIL")
    if not GMAIL_APP_PASSWORD:
        missing.append("GMAIL_APP_PASSWORD")
    if not NOTION_TOKEN:
        missing.append("NOTION_TOKEN")
    return missing
