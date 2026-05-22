"""LP position monitor — polls Meteora DLMM pools for open positions."""

import os
import requests

METEORA_API = "https://dlmm-api.meteora.ag"
WALLET = os.getenv("WALLET_ADDRESS", "")


def get_positions(wallet: str = WALLET) -> list[dict]:
    if not wallet:
        return []
    resp = requests.get(
        f"{METEORA_API}/position/all_by_wallet/{wallet}",
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("positions", [])


def summarize_positions(wallet: str = WALLET) -> None:
    positions = get_positions(wallet)
    if not positions:
        print("No open Meteora positions.")
        return
    for pos in positions:
        pool = pos.get("pool_address", "?")
        value = pos.get("total_usd_value", 0)
        print(f"  Pool {pool[:8]}… — ${value:,.2f}")


if __name__ == "__main__":
    summarize_positions()
