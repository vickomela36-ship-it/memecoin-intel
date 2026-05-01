"""Meteora LP position monitor (Solana DLMM pools)."""

import requests
from config import WALLET_ADDRESS

METEORA_API = "https://dlmm-api.meteora.ag"


def get_lp_positions(wallet: str = WALLET_ADDRESS) -> list[dict]:
    if not wallet:
        return []
    try:
        resp = requests.get(f"{METEORA_API}/pair/all_by_user?user={wallet}", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def get_position_summary(wallet: str = WALLET_ADDRESS) -> dict:
    positions = get_lp_positions(wallet)
    total_value = sum(float(p.get("total_fee_usd", 0)) for p in positions)
    return {
        "wallet": wallet,
        "open_positions": len(positions),
        "total_fees_usd": round(total_value, 2),
        "positions": positions[:10],
    }
