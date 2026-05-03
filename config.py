"""Runtime configuration loaded from environment variables."""

import os

# Gmail SMTP — generate an app-password at myaccount.google.com/apppasswords
GMAIL_SENDER = os.environ.get("GMAIL_SENDER", "")          # e.g. you@gmail.com
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")  # 16-char app password
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "vickomela36@gmail.com")

# Notion internal-integration token — create one at notion.so/my-integrations
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DATABASE_ID = "951ef2fb-9adb-4524-bedb-ff2272b44560"

# How long (seconds) before we re-alert on the same token
DEDUP_WINDOW_SECONDS = 2 * 60 * 60  # 2 hours
