import requests
from dataclasses import dataclass
from typing import Optional
import config as cfg

DEXSCREENER_API = "https://api.dexscreener.com/latest/dex/tokens"


@dataclass
class TokenSignal:
    token: str
    symbol: str
    signal: str  # "buy now" | "sell" | "hold"
    price_usd: str
    change_1h: str
    change_6h: str
    change_24h: str
    volume_24h: str
    liquidity_usd: str
    buy_pressure: str
    dexscreener_url: str


def _fetch_pair(address: str) -> Optional[dict]:
    try:
        r = requests.get(f"{DEXSCREENER_API}/{address}", timeout=10)
        r.raise_for_status()
        pairs = r.json().get("pairs") or []
        solana = [p for p in pairs if p.get("chainId") == "solana"]
        candidates = solana or pairs
        if not candidates:
            return None
        return max(candidates, key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0))
    except Exception:
        return None


def _buy_pressure(pair: dict) -> float:
    txns = (pair.get("txns") or {}).get("h1") or {}
    buys = txns.get("buys", 0)
    sells = txns.get("sells", 0)
    total = buys + sells
    return (buys / total) if total else 0.5


def _signal_for(pair: dict) -> str:
    pc = pair.get("priceChange") or {}
    change_1h = float(pc.get("h1") or 0)
    change_24h = float(pc.get("h24") or 0)
    liquidity = float((pair.get("liquidity") or {}).get("usd") or 0)
    bp = _buy_pressure(pair)

    if (
        change_1h >= cfg.BUY_1H_CHANGE_THRESHOLD
        and bp >= cfg.BUY_PRESSURE_THRESHOLD
        and liquidity >= cfg.BUY_MIN_LIQUIDITY
        and change_24h > 0
    ):
        return "buy now"

    if change_1h <= -cfg.BUY_1H_CHANGE_THRESHOLD or (change_24h < -15 and bp < 0.4):
        return "sell"

    return "hold"


def check_tokens(addresses: list[str]) -> list[TokenSignal]:
    results = []
    for addr in addresses:
        pair = _fetch_pair(addr)
        if not pair:
            continue
        base = pair.get("baseToken") or {}
        pc = pair.get("priceChange") or {}
        bp = _buy_pressure(pair)
        results.append(TokenSignal(
            token=base.get("name") or addr,
            symbol=base.get("symbol") or "",
            signal=_signal_for(pair),
            price_usd=str(pair.get("priceUsd") or ""),
            change_1h=str(pc.get("h1") or ""),
            change_6h=str(pc.get("h6") or ""),
            change_24h=str(pc.get("h24") or ""),
            volume_24h=str((pair.get("volume") or {}).get("h24") or ""),
            liquidity_usd=str((pair.get("liquidity") or {}).get("usd") or ""),
            buy_pressure=f"{bp:.1%}",
            dexscreener_url=pair.get("url") or "",
        ))
    return results
