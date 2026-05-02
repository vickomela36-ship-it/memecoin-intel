"""
Central config — reads from environment / .env file.
Copy .env.example to .env and fill in your values before running.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def require(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise EnvironmentError(f"Required env var '{key}' is not set. See .env.example.")
    return val


NOTION_API_KEY = require("NOTION_API_KEY")
NOTION_DATABASE_ID = require("NOTION_DATABASE_ID")
GMAIL_USER = require("GMAIL_USER")
GMAIL_APP_PASSWORD = require("GMAIL_APP_PASSWORD")
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "vickomela36@gmail.com")
