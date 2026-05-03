# ── Gmail SMTP ────────────────────────────────────────────────────────────────
# Create an App Password at https://myaccount.google.com/apppasswords
GMAIL_USER = "your_gmail@gmail.com"
GMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"   # 16-char App Password
ALERT_EMAIL = "vickomela36@gmail.com"

# ── Notion ────────────────────────────────────────────────────────────────────
# Create an integration at https://www.notion.so/my-integrations and share the
# "Memecoin Buy Now Signals" database with it.
NOTION_TOKEN = "secret_..."
NOTION_DATABASE_ID = "c7f3d2af-bf40-4406-9e7f-b998f7123168"

# ── Solana wallet (used by tracker.py / dashboard.py) ────────────────────────
WALLET_ADDRESS = "YOUR_SOLANA_WALLET_ADDRESS"

# ── Signal thresholds ─────────────────────────────────────────────────────────
VOLUME_TO_MCAP_THRESHOLD = 0.30   # vol/mcap ratio that adds to score
PRICE_CHANGE_THRESHOLD_HIGH = 20  # 24h % gain → +2 score
PRICE_CHANGE_THRESHOLD_LOW  = 10  # 24h % gain → +1 score
MIN_VOLUME_USD = 500_000          # minimum 24h volume to be considered
MAX_TOKENS_TO_CHECK = 20          # how many trending tokens to scan per run
