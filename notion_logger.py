import os
import requests
from datetime import datetime, timezone

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

DEFAULT_DB_ID = "9bef3e9d-e23f-482b-a4be-628efce7f371"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def log_buy_signal(coin, email_sent: bool = False) -> None:
    database_id = os.environ.get("NOTION_DATABASE_ID", DEFAULT_DB_ID)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    payload = {
        "parent": {"database_id": database_id},
        "properties": {
            "Coin": {
                "title": [{"text": {"content": f"{coin.name} ({coin.symbol})"}}]
            },
            "Signal": {"select": {"name": "buy now"}},
            "Price (USD)": {"number": round(coin.price_usd, 10)},
            "24h Change (%)": {"number": round(coin.change_24h, 4)},
            "Volume (24h)": {"number": round(coin.volume_24h, 2)},
            "Market Cap": {"number": round(coin.market_cap, 2)},
            "Detected At": {"date": {"start": now}},
            "Email Sent": {"checkbox": email_sent},
        },
    }

    resp = requests.post(
        f"{NOTION_API}/pages", json=payload, headers=_headers(), timeout=15
    )
    resp.raise_for_status()
    print(f"Logged to Notion: {coin.name} ({coin.symbol})")
