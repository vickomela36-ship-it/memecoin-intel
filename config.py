"""
Central configuration for memecoin-intel.

Copy .env.example to .env and fill in your credentials, then:
    python scheduler.py

Alternatively, export environment variables directly before running.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ── Blockchain ────────────────────────────────────────────────────────────────

CHAIN = "solana"  # DexScreener chain slug

# DexScreener pair addresses to monitor.
# Find them at https://dexscreener.com/solana/<pair_address>
TRACKED_TOKENS: list[str] = [
    # "8HoQnePLqPj4M7PUDzfw8e3Ymdwgc6NaAnmk8ztQHuc",  # example: BONK/SOL
    # "GHvFFSZ9BctWsEc5nujR1MTmmJWY7tgQz2AXE6WVFtGN",  # example: JUP/SOL
]

# ── Email ─────────────────────────────────────────────────────────────────────

ALERT_EMAIL = "vickomela36@gmail.com"

# Gmail SMTP — use an App Password (not your account password).
# Generate one at: https://myaccount.google.com/apppasswords
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")   # your Gmail address
SMTP_PASS = os.getenv("SMTP_PASS", "")  # Gmail app password (16 chars)

# ── Notion ────────────────────────────────────────────────────────────────────

# Internal integration token from https://www.notion.so/my-integrations
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")

# Pre-existing "Memecoin Buy Signals" database (data source 684a50fb-…)
NOTION_DATABASE_ID = "684a50fb-f6b5-44c6-b1f5-36a3a6f2679e"

# ── Signal thresholds ─────────────────────────────────────────────────────────

# Minimum liquidity (USD) — ignore illiquid tokens
MIN_LIQUIDITY_USD: float = float(os.getenv("MIN_LIQUIDITY_USD", "50000"))

# Minimum 24h volume (USD) — filter out low-activity pairs
MIN_VOLUME_24H_USD: float = float(os.getenv("MIN_VOLUME_24H_USD", "100000"))

# Fraction of transactions that must be buys (0.0–1.0)
BUY_PRESSURE_THRESHOLD: float = float(os.getenv("BUY_PRESSURE_THRESHOLD", "0.6"))

# Minimum 1h price increase (%) required for a "buy now" signal
PRICE_CHANGE_1H_THRESHOLD: float = float(os.getenv("PRICE_CHANGE_1H_THRESHOLD", "5.0"))
