# ── Gmail ─────────────────────────────────────────────────────────────────────
# Use a Gmail App Password, NOT your account password.
# Steps: myaccount.google.com → Security → 2-Step Verification → App passwords
#        Create app "Memecoin Intel" and paste the 16-char password below.
GMAIL_SENDER       = "your-gmail@gmail.com"       # account used to send alerts
GMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"        # 16-char App Password
ALERT_EMAIL        = "vickomela36@gmail.com"       # recipient

# ── Notion ────────────────────────────────────────────────────────────────────
# 1. Go to notion.so/my-integrations → New integration → copy the token
# 2. Open the "Memecoin Buy Signals" database in Notion
# 3. Click ··· → Add connections → select your integration
NOTION_TOKEN       = "ntn_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
NOTION_DATABASE_ID = "347d49061af04a12b116e0601217bcaf"   # created by Claude

# ── Signal tuning ─────────────────────────────────────────────────────────────
CHAIN                  = "solana"   # chain monitored by DexScreener
CHECK_INTERVAL_HOURS   = 1          # must match your cron frequency
