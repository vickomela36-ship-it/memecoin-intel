import requests
from config import METEORA_API, WALLET_ADDRESS


def get_positions() -> list[dict]:
    """Return open DLMM LP positions for the configured wallet."""
    if not WALLET_ADDRESS:
        return []
    url = f"{METEORA_API}/position/wallet/{WALLET_ADDRESS}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json() or []
    except Exception as exc:
        print(f"Meteora fetch error: {exc}")
        return []


def print_positions(positions: list[dict]) -> None:
    if not positions:
        print("No open Meteora LP positions.")
        return
    for pos in positions:
        name = pos.get("name", "Unknown")
        value = pos.get("total_fee_x_and_y", 0)
        print(f"  {name}  |  fees earned: ${value:.4f}")
