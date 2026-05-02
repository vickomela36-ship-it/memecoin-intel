import os

from dotenv import load_dotenv

load_dotenv()

# ── Notion ────────────────────────────────────────────────────────────────────
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = "ec3ba050-a06d-40c2-a92e-a87b51ceb459"

# ── Gmail SMTP (generate an App Password at myaccount.google.com/apppasswords) ─
GMAIL_SENDER = os.getenv("GMAIL_SENDER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
ALERT_EMAIL = "vickomela36@gmail.com"

# ── Token watchlist ────────────────────────────────────────────────────────────
# Provide contract addresses (any EVM chain or Solana) to watch specific tokens.
# Leave empty to auto-scan DexScreener's latest boosted/trending tokens.
WATCH_TOKENS: list[str] = []

# ── Signal thresholds ──────────────────────────────────────────────────────────
MIN_VOLUME_24H = 50_000      # USD — ignore low-liquidity noise
MIN_LIQUIDITY = 10_000       # USD — must be tradeable
MIN_PRICE_CHANGE_1H = 10.0   # % — strong 1-hour upward momentum

# ── Scheduler ─────────────────────────────────────────────────────────────────
CHECK_INTERVAL_HOURS = 1
