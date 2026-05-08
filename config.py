import os

# ── Notifications ──────────────────────────────────────────────────────────────
ALERT_EMAIL = "vickomela36@gmail.com"

# ── Notion ─────────────────────────────────────────────────────────────────────
# "Memecoin Buy Signals" database — data source ID
NOTION_DATA_SOURCE_ID = "b69604b4-b942-4e4b-887a-1a138ccb64ff"

# ── Wallet ─────────────────────────────────────────────────────────────────────
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")

# ── Signal thresholds ──────────────────────────────────────────────────────────
MIN_LIQUIDITY_USD   = 10_000   # ignore tokens with < $10k liquidity
MIN_VOL_LIQ_RATIO   = 1.5     # volume/liquidity ratio must exceed this
MIN_24H_CHANGE_PCT  = 5.0     # minimum 24-h price gain (%)
MIN_5M_CHANGE_PCT   = 0.0     # require positive 5-min momentum

# ── Monitoring ─────────────────────────────────────────────────────────────────
CHECK_INTERVAL_MINUTES = 60
# State file tracks pair addresses already notified (avoids duplicate alerts)
STATE_FILE = os.path.join(os.path.dirname(__file__), "notified_pairs.json")
