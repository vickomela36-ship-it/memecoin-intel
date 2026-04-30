import os

# ── Notion ────────────────────────────────────────────────────────────────────
NOTION_API_KEY      = os.environ.get("NOTION_API_KEY", "YOUR_NOTION_API_KEY")
NOTION_DATABASE_ID  = "44763c62-4d07-4fde-bb1c-503846807aeb"

# ── Gmail SMTP ────────────────────────────────────────────────────────────────
# Use a Gmail App Password (myaccount.google.com/apppasswords), NOT your login password.
GMAIL_USER          = os.environ.get("GMAIL_USER", "your@gmail.com")
GMAIL_APP_PASSWORD  = os.environ.get("GMAIL_APP_PASSWORD", "YOUR_APP_PASSWORD")
ALERT_EMAIL         = "vickomela36@gmail.com"

# ── Wallet (used by tracker / meteora) ───────────────────────────────────────
WALLET_ADDRESS      = os.environ.get("WALLET_ADDRESS", "YOUR_SOLANA_WALLET_ADDRESS")

# ── Pairs to monitor (Solana pair addresses from DexScreener) ─────────────────
# Find addresses at https://dexscreener.com – copy the pair address from the URL.
WATCHED_PAIRS: list[str] = [
    # "PAIR_ADDRESS_1",
    # "PAIR_ADDRESS_2",
]

# ── Signal thresholds ─────────────────────────────────────────────────────────
BUY_NOW_MIN_PRICE_CHANGE_5M  = 2.0      # 5-min gain must exceed this %
BUY_NOW_MIN_VOLUME_5M_USD    = 10_000   # 5-min volume floor ($)
BUY_NOW_MIN_LIQUIDITY_USD    = 50_000   # liquidity floor ($)
BUY_NOW_MAX_PRICE_CHANGE_1H  = 50.0    # cap — avoid already-pumped tokens
SELL_TRIGGER_5M_DROP         = -3.0     # 5-min drop triggers sell
SELL_TRIGGER_1H_DROP         = -10.0    # 1h drop triggers sell
