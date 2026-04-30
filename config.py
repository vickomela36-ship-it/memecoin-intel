"""Central config — set your credentials here or via environment variables."""

import os

# --- Alert email ---
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "vickomela36@gmail.com")

# --- Gmail SMTP (use a Google App Password, not your regular password) ---
# Generate one at: https://myaccount.google.com/apppasswords
GMAIL_SENDER = os.getenv("GMAIL_SENDER", "")       # your Gmail address
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# --- Notion API ---
# Create an integration at: https://www.notion.so/my-integrations
# Share the "Memecoin Buy Signals Log" database with the integration
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = "73b5d85d-86bf-4b6e-b8d7-c43e92bc0391"  # created 2026-04-30

# --- Wallet (optional, for PnL tracking) ---
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")
