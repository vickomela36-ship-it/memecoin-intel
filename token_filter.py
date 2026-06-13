"""
token_filter.py — Safety and eligibility check module for Solana tokens.

Uses rugcheck.xyz API, Helius RPC, and DexScreener pair data to evaluate
whether a token passes safety thresholds for volume, liquidity, age,
holder concentration, and rug-pull risk indicators.
"""

import time
import logging
from dataclasses import dataclass, field

import requests

from config import (
    HELIUS_RPC, RUGCHECK_API,
    MIN_24H_VOLUME, MIN_5M_VOLUME, MIN_LIQUIDITY,
    MIN_TOKEN_AGE_HOURS, MIN_HOLDER_COUNT, MAX_TOP10_HOLDER_PCT,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Data class
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _safe_float(obj, *keys, default=0.0):
    """Safely traverse nested dicts and return a float, or *default* on any failure."""
    current = obj
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return default
    try:
        return float(current) if current is not None else default
    except (TypeError, ValueError):
        return default


def _check_rugcheck(mint_address: str) -> dict:
    """Fetch the rugcheck.xyz report for a token mint address.

    Returns the parsed JSON dict on success, or an empty dict on any error.
    """
    url = f"{RUGCHECK_API}/tokens/{mint_address}/report"
    try:
        resp = requests.get(url, timeout=12)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("Rugcheck request failed for %s: %s", mint_address, exc)
        return {}


def _check_helius_holders(mint_address: str) -> list:
    """Get the largest token-account holders via Helius RPC (getTokenLargestAccounts).

    Returns a list of holder dicts on success, or an empty list on any error.
    Each item has at least ``amount`` (str) and ``uiAmount`` (float|None).
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenLargestAccounts",
        "params": [mint_address],
    }
    try:
        resp = requests.post(HELIUS_RPC, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", {}).get("value", [])
    except Exception as exc:
        logger.warning("Helius holder request failed for %s: %s", mint_address, exc)
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# Main safety check
# ═══════════════════════════════════════════════════════════════════════════════

def check_token_safety(mint_address: str, pair_data: dict) -> SafetyResult:
    """Run a comprehensive safety and eligibility check on a Solana token.

    Parameters
    ----------
    mint_address : str
        The token's mint address on Solana.
    pair_data : dict
        A DexScreener pair object containing volume, liquidity, and creation
        timestamp fields.

    Returns
    -------
    SafetyResult
        Populated result with pass/fail verdict and supporting evidence.
    """
    result = SafetyResult()

    # ── 1. Extract market data from pair_data ─────────────────────────────
    result.volume_24h = _safe_float(pair_data, "volume", "h24")
    result.volume_5m = _safe_float(pair_data, "volume", "m5")
    result.liquidity_usd = _safe_float(pair_data, "liquidity", "usd")

    # ── 2. Calculate token age ────────────────────────────────────────────
    created_at_ms = pair_data.get("pairCreatedAt")
    if created_at_ms:
        try:
            age_seconds = time.time() - (float(created_at_ms) / 1000.0)
            result.token_age_hours = max(age_seconds / 3600.0, 0.0)
        except (TypeError, ValueError):
            result.token_age_hours = 0.0

    # ── 3. Threshold checks ──────────────────────────────────────────────
    critical_fails = 0

    if result.volume_24h >= MIN_24H_VOLUME:
        result.pass_reasons.append(
            f"24h volume ${result.volume_24h:,.0f} >= ${MIN_24H_VOLUME:,}"
        )
    else:
        result.fail_reasons.append(
            f"24h volume ${result.volume_24h:,.0f} < ${MIN_24H_VOLUME:,}"
        )
        critical_fails += 1

    if result.volume_5m >= MIN_5M_VOLUME:
        result.pass_reasons.append(
            f"5m volume ${result.volume_5m:,.0f} >= ${MIN_5M_VOLUME:,}"
        )
    else:
        result.fail_reasons.append(
            f"5m volume ${result.volume_5m:,.0f} < ${MIN_5M_VOLUME:,}"
        )
        critical_fails += 1

    if result.liquidity_usd >= MIN_LIQUIDITY:
        result.pass_reasons.append(
            f"Liquidity ${result.liquidity_usd:,.0f} >= ${MIN_LIQUIDITY:,}"
        )
    else:
        result.fail_reasons.append(
            f"Liquidity ${result.liquidity_usd:,.0f} < ${MIN_LIQUIDITY:,}"
        )
        critical_fails += 1

    if result.token_age_hours >= MIN_TOKEN_AGE_HOURS:
        result.pass_reasons.append(
            f"Token age {result.token_age_hours:.1f}h >= {MIN_TOKEN_AGE_HOURS}h"
        )
    else:
        result.fail_reasons.append(
            f"Token age {result.token_age_hours:.1f}h < {MIN_TOKEN_AGE_HOURS}h"
        )
        critical_fails += 1

    # ── 4. Rugcheck analysis ─────────────────────────────────────────────
    report = _check_rugcheck(mint_address)

    if report:
        # Score interpretation
        raw_score = report.get("score")
        if raw_score is not None:
            try:
                score_val = int(raw_score)
                result.rug_score = str(score_val)
                if score_val >= 800:
                    result.rug_risk_level = "good"
                    result.pass_reasons.append(
                        f"Rug score {score_val} (Good)"
                    )
                elif score_val >= 500:
                    result.rug_risk_level = "warning"
                    result.pass_reasons.append(
                        f"Rug score {score_val} (Warning)"
                    )
                else:
                    result.rug_risk_level = "danger"
                    result.fail_reasons.append(
                        f"Rug score {score_val} (Danger)"
                    )
            except (TypeError, ValueError):
                result.rug_score = str(raw_score)

        # Parse individual risks
        risks = report.get("risks", [])
        for risk in risks:
            name = risk.get("name", "")
            description = risk.get("description", "")
            level = risk.get("level", "")
            result.rug_risks.append(
                {"name": name, "description": description, "level": level}
            )

            name_lower = name.lower()
            desc_lower = description.lower()

            # Detect mint authority
            if "mint" in name_lower or "mint authority" in desc_lower:
                result.has_mint_authority = True

            # Detect freeze authority
            if "freeze" in name_lower or "freeze authority" in desc_lower:
                result.has_freeze_authority = True

        # Mint/freeze are soft warnings, not hard fails
        if result.has_mint_authority:
            result.fail_reasons.append("Mint authority still enabled (soft warning)")

        if result.has_freeze_authority:
            result.fail_reasons.append("Freeze authority still enabled (soft warning)")

        # ── 5. LP lock detection from markets data ───────────────────────
        markets = report.get("markets", [])
        for market in markets:
            lp_locked = market.get("lp", {}).get("lpLocked", 0)
            if isinstance(lp_locked, (int, float)) and lp_locked > 0:
                result.lp_locked = True
                result.pass_reasons.append("LP liquidity is locked")
                break

        # Holder count from rugcheck
        result.holder_count = report.get("totalHolders", 0) or report.get(
            "holderCount", 0
        )

        # Top-10 holder concentration from rugcheck
        top_holders = report.get("topHolders", [])
        if top_holders:
            total_pct = sum(
                _safe_float(h, "pct") for h in top_holders[:10]
            )
            result.top10_holder_pct = total_pct
    else:
        result.fail_reasons.append("Rugcheck data unavailable")

    # ── 6. Top holders via Helius (primary or backup) ────────────────────
    helius_holders = _check_helius_holders(mint_address)

    if helius_holders:
        # If rugcheck didn't provide top-10 concentration, compute from Helius
        if result.top10_holder_pct == 0.0:
            total_supply = sum(
                _safe_float(h, "uiAmount") for h in helius_holders
            )
            if total_supply > 0:
                top10_supply = sum(
                    _safe_float(h, "uiAmount") for h in helius_holders[:10]
                )
                result.top10_holder_pct = (top10_supply / total_supply) * 100.0

        # ── 7. Backup holder count from Helius if rugcheck was low ────
        if result.holder_count < MIN_HOLDER_COUNT:
            helius_count = len(helius_holders)
            if helius_count > result.holder_count:
                result.holder_count = helius_count

    # Holder count threshold check
    if result.holder_count >= MIN_HOLDER_COUNT:
        result.pass_reasons.append(
            f"Holder count {result.holder_count} >= {MIN_HOLDER_COUNT}"
        )
    else:
        result.fail_reasons.append(
            f"Holder count {result.holder_count} < {MIN_HOLDER_COUNT}"
        )

    # Top-10 concentration check
    if result.top10_holder_pct > 0:
        if result.top10_holder_pct <= MAX_TOP10_HOLDER_PCT:
            result.pass_reasons.append(
                f"Top-10 holders own {result.top10_holder_pct:.1f}% <= {MAX_TOP10_HOLDER_PCT}%"
            )
        else:
            result.fail_reasons.append(
                f"Top-10 holders own {result.top10_holder_pct:.1f}% > {MAX_TOP10_HOLDER_PCT}%"
            )

    # ── 8. Final verdict ─────────────────────────────────────────────────
    # Hard fail: rug risk level is "danger"
    if result.rug_risk_level == "danger":
        result.passed = False
        return result

    # Mint/freeze authority are soft warnings — do NOT count them as
    # critical fails.  Only volume/liquidity/age/holder thresholds counted.
    # Allow up to 1 critical fail.
    if critical_fails <= 1:
        result.passed = True
    else:
        result.passed = False

    return result
