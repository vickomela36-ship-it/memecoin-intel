import logging
from datetime import datetime, timezone

import requests

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

log = logging.getLogger(__name__)


def log_signal(signal, cfg) -> None:
    if not cfg.NOTION_TOKEN:
        log.warning("NOTION_TOKEN not configured — skipping Notion log")
        return

    headers = {
        "Authorization": f"Bearer {cfg.NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }

    now = datetime.now(timezone.utc).isoformat()

    payload = {
        "parent": {"database_id": cfg.NOTION_DATABASE_ID},
        "properties": {
            "Token": {"title": [{"text": {"content": signal.token}}]},
            "Symbol": {"rich_text": [{"text": {"content": signal.symbol}}]},
            "Signal": {"select": {"name": signal.signal}},
            "Price USD": {"rich_text": [{"text": {"content": signal.price_usd}}]},
            "1h Change %": {"rich_text": [{"text": {"content": signal.change_1h}}]},
            "6h Change %": {"rich_text": [{"text": {"content": signal.change_6h}}]},
            "24h Change %": {"rich_text": [{"text": {"content": signal.change_24h}}]},
            "Volume 24h USD": {"rich_text": [{"text": {"content": signal.volume_24h}}]},
            "Liquidity USD": {"rich_text": [{"text": {"content": signal.liquidity_usd}}]},
            "Buy Pressure": {"rich_text": [{"text": {"content": signal.buy_pressure}}]},
            "DexScreener URL": {"url": signal.dexscreener_url or None},
            "Checked At": {"date": {"start": now}},
        },
    }

    r = requests.post(f"{NOTION_API}/pages", headers=headers, json=payload, timeout=10)
    if r.ok:
        log.info("Logged %s to Notion (signal: %s)", signal.symbol, signal.signal)
    else:
        log.error("Notion log failed [%s]: %s", r.status_code, r.text[:200])
