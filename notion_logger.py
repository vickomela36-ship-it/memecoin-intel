"""Log buy signals to the Notion database."""

import requests
from datetime import datetime, timezone
from config import NOTION_API_TOKEN, NOTION_DATABASE_ID

_BASE = "https://api.notion.com/v1"
_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def _props(result: dict, email_sent: bool) -> dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    props: dict = {
        "Coin": {"title": [{"text": {"content": f"{result['name']} ({result['symbol']})"}}]},
        "Signal": {"select": {"name": result["signal"]}},
        "Date": {"date": {"start": today}},
        "Email Sent": {"checkbox": email_sent},
    }
    if result.get("price") is not None:
        props["Price (USD)"] = {"number": result["price"]}
    if result.get("change_24h") is not None:
        props["24h Change %"] = {"number": round(result["change_24h"], 4)}
    if result.get("volume_24h") is not None:
        props["Volume 24h"] = {"number": result["volume_24h"]}
    if result.get("market_cap") is not None:
        props["Market Cap"] = {"number": result["market_cap"]}
    if result.get("rsi") is not None:
        props["RSI"] = {"number": result["rsi"]}
    if result.get("confidence"):
        props["Confidence"] = {"select": {"name": result["confidence"]}}
    if result.get("volume_spike") is not None:
        props["Notes"] = {"rich_text": [{"text": {"content": f"Volume spike: {result['volume_spike']}x 7-day avg"}}]}
    return props


def log_signal(result: dict, email_sent: bool = False) -> str:
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": _props(result, email_sent),
    }
    resp = requests.post(f"{_BASE}/pages", json=payload, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    page_id = resp.json().get("id", "")
    print(f"  [Notion] logged {result['name']} ({result['signal']}) → page {page_id[:8]}…")
    return page_id
