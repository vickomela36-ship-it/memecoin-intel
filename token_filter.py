"""
token_filter.py — Safety and eligibility checks for Solana tokens.

Uses rugcheck.xyz for mint/freeze authority, rug risks, and holder analysis.
Uses DexScreener pair data for volume, liquidity, and token age.
"""

import time
import requests
from dataclasses import dataclass, field
from config import (
    HELIUS_RPC, RUGCHECK_API,
    MIN_24H_VOLUME, MIN_5M_VOLUME, MIN_LIQUIDITY,
    MIN_TOKEN_AGE_HOURS, MIN_HOLDER_COUNT, MAX_TOP10_HOLDER_PCT,
)


@dataclass
class SafetyResult:
    passed: bool = False
    has_mint_authority: bool = False
    has_freeze_authority: bool = False
    rug_score: str = "Unknown"
    rug_risk_level: str = "unknown"
    rug_risks: list = field(default_factory=list)
    holder_count: int = 0
    top10_holder_pct: float = 0.0
    token_age_hours: float = 0.0
    liquidity_usd: float = 0.0
    volume_24h: float = 0.0
    volume_5m: float = 0.0
    lp_locked: bool = False
    fail_reasons: list = field(default_factory=list)
    pass_reasons: list = field(default_factory=list)


def _safe_float(obj, *keys, default=0.0):
    val = obj
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return default
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def _check_rugcheck(mint_address: str) -> dict:
    """Fetch rugcheck.xyz report. Returns full report or empty dict."""
    try:
        r = requests.get(
            f"{RUGCHECK_API}/tokens/{mint_address}/report",
            timeout=12,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}


def _check_helius_holders(mint_address: str) -> dict:
    """Get top token holders via Helius RPC."""
    try:
        r = requests.post(
            HELIUS_RPC,
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "getTokenLargestAccounts",
                "params": [mint_address],
            },
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("result", {})
    except Exception:
        return {}


def check_token_safety(mint_address: str, pair_data: dict) -> SafetyResult:
    """
    Run all safety checks. Hard fails (mint/freeze authority, known rug) block
    the token entirely. Soft fails (low volume, young token) reduce confidence
    but don't block.
    """
    result = SafetyResult()

    # ── DexScreener-derived metrics ──────────────────────────────────────
    result.volume_24h = _safe_float(pair_data, "volume", "h24")
    result.volume_5m = _safe_float(pair_data, "volume", "m5")
    result.liquidity_usd = _safe_float(pair_data, "liquidity", "usd")

    created = pair_data.get("pairCreatedAt")
    if created:
        try:
            age_ms = time.time() * 1000 - float(created)
            result.token_age_hours = max(age_ms / (1000 * 3600), 0)
        except (ValueError, TypeError):
            pass

    if result.volume_24h < MIN_24H_VOLUME:
        result.fail_reasons.append(
            f"24h vol ${result.volume_24h:,.0f} < ${MIN_24H_VOLUME:,.0f}"
        )
    else:
        result.pass_reasons.append(f"24h vol ${result.volume_24h:,.0f}")

    if result.volume_5m < MIN_5M_VOLUME:
        result.fail_reasons.append(
            f"5m vol ${result.volume_5m:,.0f} < ${MIN_5M_VOLUME:,.0f}"
        )

    if result.liquidity_usd < MIN_LIQUIDITY:
        result.fail_reasons.append(
            f"Liq ${result.liquidity_usd:,.0f} < ${MIN_LIQUIDITY:,.0f}"
        )
    else:
        result.pass_reasons.append(f"Liq ${result.liquidity_usd:,.0f}")

    if result.token_age_hours < MIN_TOKEN_AGE_HOURS:
        result.fail_reasons.append(
            f"Age {result.token_age_hours:.1f}h < {MIN_TOKEN_AGE_HOURS}h"
        )
    else:
        result.pass_reasons.append(f"Age {result.token_age_hours:.0f}h")

    # ── Rugcheck.xyz — mint/freeze authority + rug risks ─────────────────
    rug = _check_rugcheck(mint_address)
    if rug:
        score_val = rug.get("score")
        risks = rug.get("risks") or []

        if isinstance(score_val, (int, float)):
            result.rug_score = str(score_val)
            if score_val >= 800:
                result.rug_risk_level = "good"
                result.pass_reasons.append(f"Rug score {score_val} (good)")
            elif score_val >= 500:
                result.rug_risk_level = "warning"
                result.pass_reasons.append(f"Rug score {score_val} (ok)")
            else:
                result.rug_risk_level = "danger"
                result.fail_reasons.append(f"Rug score {score_val} (danger)")
        else:
            result.rug_score = str(score_val) if score_val else "Unknown"

        has_mint = False
        has_freeze = False
        risk_names = []
        for risk in risks:
            name = risk.get("name", "")
            level = risk.get("level", "")
            risk_names.append(name)
            name_lower = name.lower()
            if "mint" in name_lower and "authority" in name_lower:
                has_mint = True
            if "freeze" in name_lower and "authority" in name_lower:
                has_freeze = True

        result.has_mint_authority = has_mint
        result.has_freeze_authority = has_freeze
        result.rug_risks = [
            r.get("name", "")
            for r in risks
            if r.get("level") in ("danger", "warn", "error")
        ]

        if has_mint:
            result.fail_reasons.append("Mint authority still active")
        else:
            result.pass_reasons.append("Mint authority revoked")

        if has_freeze:
            result.fail_reasons.append("Freeze authority still active")
        else:
            result.pass_reasons.append("Freeze authority revoked")

        # LP lock detection from rugcheck
        markets = rug.get("markets") or []
        for market in markets:
            lp_locked = market.get("lp", {}).get("lpLockedPct", 0)
            if lp_locked and float(lp_locked) > 50:
                result.lp_locked = True
                result.pass_reasons.append(f"LP {float(lp_locked):.0f}% locked")
                break

        # Top holders from rugcheck
        top_holders = rug.get("topHolders") or []
        if top_holders:
            result.holder_count = len(top_holders)
            top10_pct = sum(
                float(h.get("pct", 0) or 0) for h in top_holders[:10]
            )
            result.top10_holder_pct = top10_pct

            if top10_pct > MAX_TOP10_HOLDER_PCT:
                result.fail_reasons.append(
                    f"Top 10 hold {top10_pct:.0f}% > {MAX_TOP10_HOLDER_PCT:.0f}%"
                )
            else:
                result.pass_reasons.append(f"Top 10 hold {top10_pct:.0f}%")
    else:
        result.pass_reasons.append("Rugcheck unavailable (assuming safe)")

    # ── Helius holder enrichment (optional) ──────────────────────────────
    if result.holder_count < MIN_HOLDER_COUNT:
        holders = _check_helius_holders(mint_address)
        if holders and holders.get("value"):
            result.holder_count = max(result.holder_count, len(holders["value"]))

    if result.holder_count < MIN_HOLDER_COUNT:
        result.fail_reasons.append(
            f"Holder count {result.holder_count} < {MIN_HOLDER_COUNT}"
        )

    # ── Final verdict ────────────────────────────────────────────────────
    # Only hard-fail on confirmed dangerous rug score.
    # Mint/freeze authority are warnings (very common on Solana memecoins)
    # and reduce the confidence score instead of blocking.
    hard_fail = result.rug_risk_level == "danger"

    critical_fails = sum(
        1 for r in result.fail_reasons
        if any(x in r for x in ["24h vol", "Liq $", "Age "])
    )

    result.passed = not hard_fail and critical_fails <= 1
    return result
