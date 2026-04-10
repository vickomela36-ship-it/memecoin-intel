"""
Helius API client — token metadata, age verification, and market cap lookups.
Uses Helius DAS (Digital Asset Standard) API + enhanced RPC.
"""

import time
import requests
from datetime import datetime, timezone
from config import HELIUS_API_KEY, HELIUS_API_BASE, HELIUS_RPC_BASE


def get_token_metadata(mint_address: str) -> dict | None:
    """Fetch token metadata via Helius DAS API (getAsset)."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getAsset",
        "params": {"id": mint_address},
    }
    try:
        resp = requests.post(HELIUS_RPC_BASE, json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json().get("result")
        if not result:
            return None
        return result
    except requests.RequestException as e:
        print(f"[Helius] Error fetching metadata for {mint_address}: {e}")
        return None


def get_token_creation_time(mint_address: str) -> datetime | None:
    """
    Get the token's creation timestamp by fetching the first transaction
    signature for the mint account.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [
            mint_address,
            {"limit": 1, "commitment": "confirmed"},
        ],
    }
    try:
        resp = requests.post(HELIUS_RPC_BASE, json=payload, timeout=10)
        resp.raise_for_status()
        signatures = resp.json().get("result", [])
        if not signatures:
            return None

        # The last signature in a backward scan is the earliest — but with
        # limit=1 we get the most recent. We need to page to the end.
        # For efficiency, use Helius parsed transaction history instead.
        url = f"{HELIUS_API_BASE}/addresses/{mint_address}/transactions?api-key={HELIUS_API_KEY}&type=CREATE&limit=1"
        resp2 = requests.get(url, timeout=10)
        resp2.raise_for_status()
        txns = resp2.json()
        if txns:
            ts = txns[0].get("timestamp")
            if ts:
                return datetime.fromtimestamp(ts, tz=timezone.utc)

        # Fallback: use the block time from the oldest signature we can find
        oldest = _find_oldest_signature(mint_address)
        if oldest and oldest.get("blockTime"):
            return datetime.fromtimestamp(oldest["blockTime"], tz=timezone.utc)

        return None
    except requests.RequestException as e:
        print(f"[Helius] Error fetching creation time for {mint_address}: {e}")
        return None


def _find_oldest_signature(mint_address: str) -> dict | None:
    """Page through signatures to find the oldest one."""
    before = None
    oldest = None
    for _ in range(20):  # max 20 pages of 1000
        params = [mint_address, {"limit": 1000, "commitment": "confirmed"}]
        if before:
            params[1]["before"] = before
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": params,
        }
        try:
            resp = requests.post(HELIUS_RPC_BASE, json=payload, timeout=15)
            resp.raise_for_status()
            sigs = resp.json().get("result", [])
            if not sigs:
                break
            oldest = sigs[-1]
            if len(sigs) < 1000:
                break
            before = sigs[-1]["signature"]
            time.sleep(0.2)
        except requests.RequestException:
            break
    return oldest


def get_token_age_hours(mint_address: str) -> float | None:
    """Return the token's age in hours, or None if unknown."""
    created = get_token_creation_time(mint_address)
    if not created:
        return None
    delta = datetime.now(timezone.utc) - created
    return delta.total_seconds() / 3600


def get_token_supply(mint_address: str) -> float | None:
    """Get token total supply via RPC."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenSupply",
        "params": [mint_address],
    }
    try:
        resp = requests.post(HELIUS_RPC_BASE, json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json().get("result", {}).get("value", {})
        amount = result.get("uiAmount")
        return float(amount) if amount else None
    except requests.RequestException as e:
        print(f"[Helius] Error fetching supply for {mint_address}: {e}")
        return None


def get_market_cap(mint_address: str, price_usd: float) -> float | None:
    """Calculate market cap = supply * price."""
    supply = get_token_supply(mint_address)
    if supply is None or price_usd is None:
        return None
    return supply * price_usd


def get_token_holders_count(mint_address: str) -> int | None:
    """Get approximate holder count from Helius."""
    # Use the DAS method to get holder info
    metadata = get_token_metadata(mint_address)
    if metadata and metadata.get("ownership"):
        return metadata["ownership"].get("total", None)
    return None
