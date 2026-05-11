"""
Notion logging for 'buy now' signals.

Required env vars:
  NOTION_TOKEN        – Internal Integration token from notion.so/my-integrations
  NOTION_DATABASE_ID  – ID of the "Memecoin Buy Now Signals" database

The database was created with this schema (column names must match exactly):
  Signal Name, Date, Coin Symbol, Signal, Price USD, Price Change 24h %,
  Volume 24h USD, Liquidity USD, Chain, DEX, Pair Address, Email Sent, Notes
"""

import os
from datetime import datetime, timezone
from notion_client import Client
from notion_client.errors import APIResponseError


DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "685b3530-321a-4a7e-a5af-6553774f29b0")


def _notion_client() -> Client:
    token = os.environ["NOTION_TOKEN"]
    return Client(auth=token)


def log_signal(signal: dict, email_sent: bool = False) -> bool:
    """Append one signal row to the Notion database. Returns True on success."""
    notion = _notion_client()

    date_str = signal.get("timestamp", datetime.now(timezone.utc).isoformat())
    # Notion date property expects ISO-8601 date (YYYY-MM-DD) or datetime string
    date_only = date_str[:10]

    # Capitalise signal value to match SELECT option names in Notion
    signal_value = signal["signal"].title()  # "buy now" → "Buy Now"

    properties: dict = {
        "Signal Name": {
            "title": [{"text": {"content": f"{signal['coin_symbol']} – {signal_value}"}}]
        },
        "Date": {"date": {"start": date_only}},
        "Coin Symbol": {"rich_text": [{"text": {"content": signal.get("coin_symbol", "")}}]},
        "Signal": {"select": {"name": signal_value}},
        "Price Change 24h %": {"number": signal.get("price_change_24h")},
        "Volume 24h USD": {"number": signal.get("volume_24h_usd")},
        "Liquidity USD": {"number": signal.get("liquidity_usd")},
        "Chain": {"rich_text": [{"text": {"content": (signal.get("chain") or "").upper()}}]},
        "DEX": {"rich_text": [{"text": {"content": signal.get("dex", "")}}]},
        "Pair Address": {"rich_text": [{"text": {"content": signal.get("pair_address", "")}}]},
        "Email Sent": {"checkbox": email_sent},
    }

    if signal.get("price_usd") is not None:
        properties["Price USD"] = {"number": signal["price_usd"]}

    notes = signal.get("notes", "")
    if notes:
        properties["Notes"] = {"rich_text": [{"text": {"content": notes}}]}

    try:
        notion.pages.create(
            parent={"database_id": DATABASE_ID},
            properties=properties,
        )
        print(f"[notion] Logged {signal['coin_symbol']} ({signal_value})")
        return True
    except APIResponseError as exc:
        print(f"[notion] Failed to log {signal.get('coin_symbol')}: {exc}")
        return False


def log_signals(signals: list[dict], email_sent: bool = False) -> int:
    """Log multiple signals. Returns count of successfully logged rows."""
    return sum(log_signal(s, email_sent=email_sent) for s in signals)
