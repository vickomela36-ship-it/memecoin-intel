import os

GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "vickomela36@gmail.com")

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
# Database ID for the "Memecoin Buy Now Signals" Notion database
NOTION_DATABASE_ID = os.environ.get(
    "NOTION_DATABASE_ID", "59e4585ed95f44468482212087064088"
)
