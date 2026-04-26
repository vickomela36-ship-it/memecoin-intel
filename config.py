# config.py — fill in your credentials before running
# ⚠️  Do NOT commit this file with real values.

# ── Notion ─────────────────────────────────────────────────────────────────
# 1. Go to https://www.notion.so/my-integrations → New integration
# 2. Copy the "Internal Integration Secret" (starts with ntn_...)
# 3. Open the "Memecoin Buy Signals Log" DB in Notion → ••• → Add connections → your integration
NOTION_TOKEN = "ntn_REPLACE_ME"
NOTION_DB_ID = "5ee05dca-c8a4-463f-bf56-39a2eb08f364"   # already correct

# ── Gmail SMTP (App Password) ───────────────────────────────────────────────
# 1. Enable 2-Step Verification on your Google account
# 2. Go to https://myaccount.google.com/apppasswords
# 3. Create an App Password for "Mail" / "Other (memecoin-intel)"
# 4. Paste the 16-char password below (no spaces)
GMAIL_SENDER     = "vickomela36@gmail.com"   # the account that SENDS the email
GMAIL_APP_PASS   = "REPLACE_ME"             # 16-char App Password
ALERT_RECIPIENT  = "vickomela36@gmail.com"  # who receives the alerts
