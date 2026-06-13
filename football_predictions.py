"""
Football match prediction engine using ELO ratings and odds comparison
to find value bets across international and club competitions.
"""

import time
import json
import os
import math
import requests
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

from config import (
    FOOTBALL_DATA_API,
    FOOTBALL_DATA_API_KEY,
    ODDS_API,
    ODDS_API_KEY,
    FOOTBALL_CACHE_FILE,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

ELO_RATINGS_FILE = "elo_ratings.json"

DEFAULT_ELO = {
    "Argentina": 2150, "France": 2100, "Brazil": 2050, "England": 2040,
    "Spain": 2030, "Germany": 2000, "Netherlands": 1990, "Portugal": 1980,
    "Belgium": 1960, "Italy": 1950, "Croatia": 1940, "Uruguay": 1920,
    "Colombia": 1910, "USA": 1880, "Mexico": 1870, "Morocco": 1860,
    "Japan": 1850, "Senegal": 1840, "Switzerland": 1830, "Denmark": 1820,
    "South Korea": 1810, "Australia": 1800, "Iran": 1790, "Serbia": 1780,
    "Poland": 1770, "Ukraine": 1760, "Ecuador": 1750, "Wales": 1740,
    "Tunisia": 1730, "Cameroon": 1720, "Canada": 1710, "Ghana": 1700,
    "Saudi Arabia": 1690, "Costa Rica": 1680, "Peru": 1670, "Chile": 1660,
    "Nigeria": 1650, "Egypt": 1640, "Qatar": 1620, "Paraguay": 1610,
    "Scotland": 1600, "Turkey": 1590, "Czech Republic": 1580,
    "Austria": 1570, "Hungary": 1560, "Sweden": 1550, "Norway": 1540,
    "Romania": 1530, "Algeria": 1520, "China PR": 1400,
}

TEAM_ALIASES = {
    "Korea Republic": "South Korea",
    "Republic of Korea": "South Korea",
    "Korea DPR": "North Korea",
    "United States": "USA",
    "IR Iran": "Iran",
    "Côte d'Ivoire": "Ivory Coast",
    "Türkiye": "Turkey",
    "Czechia": "Czech Republic",
    "Bosnia and Herzegovina": "Bosnia",
    "Trinidad and Tobago": "Trinidad",
    "Korea, Republic of": "South Korea",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Dataclasses
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MatchPrediction:
    match_id: str = ""
    home_team: str = ""
    away_team: str = ""
    utc_date: str = ""
    competition: str = ""
    status: str = "SCHEDULED"
    # ELO
    home_elo: float = 1500.0
    away_elo: float = 1500.0
    home_win_prob: float = 0.33
    draw_prob: float = 0.34
    away_win_prob: float = 0.33
    # Best odds
    best_home_odds: float = 0.0
    best_draw_odds: float = 0.0
    best_away_odds: float = 0.0
    best_home_bookmaker: str = ""
    best_draw_bookmaker: str = ""
    best_away_bookmaker: str = ""
    # All bookmaker odds for comparison
    all_bookmaker_odds: list = field(default_factory=list)
    # Value bets found
    value_bets: list = field(default_factory=list)
    # Score if finished
    home_score: int = None
    away_score: int = None


# ═══════════════════════════════════════════════════════════════════════════════
# JSON Persistence
# ═══════════════════════════════════════════════════════════════════════════════

def _load_json(path):
    """Load data from a JSON file. Returns None if file missing or corrupt."""
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _save_json(path, data):
    """Persist data to a JSON file."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def load_elo_ratings():
    """Load ELO ratings from disk, falling back to DEFAULT_ELO."""
    saved = _load_json(ELO_RATINGS_FILE)
    if saved and isinstance(saved, dict):
        return saved
    return dict(DEFAULT_ELO)


def save_elo_ratings(ratings):
    """Persist updated ELO ratings to disk."""
    _save_json(ELO_RATINGS_FILE, ratings)


# ═══════════════════════════════════════════════════════════════════════════════
# Data Fetching (thread-safe, no @st.cache_data)
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_football_matches(competition="WC", status=None):
    """
    Fetch matches from football-data.org for a given competition.

    Args:
        competition: Competition code (e.g. "WC", "CL", "EC", "FL1").
        status: Optional filter — "SCHEDULED", "LIVE", or "FINISHED".

    Returns:
        List of match dicts from the API, or empty list on error.
    """
    if not FOOTBALL_DATA_API_KEY:
        return []

    url = f"{FOOTBALL_DATA_API}/competitions/{competition}/matches"
    headers = {"X-Auth-Token": FOOTBALL_DATA_API_KEY}
    params = {}
    if status:
        params["status"] = status

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("matches", [])
    except (requests.RequestException, ValueError, KeyError):
        return []


def _fetch_football_standings(competition="WC"):
    """
    Fetch standings from football-data.org for a given competition.

    Returns:
        Standings data dict, or empty dict on error.
    """
    if not FOOTBALL_DATA_API_KEY:
        return {}

    url = f"{FOOTBALL_DATA_API}/competitions/{competition}/standings"
    headers = {"X-Auth-Token": FOOTBALL_DATA_API_KEY}

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError):
        return {}


def _fetch_odds(sport="soccer_fifa_world_cup", regions="us,uk,eu", markets="h2h"):
    """
    Fetch odds from the-odds-api.com for a given sport.

    Returns:
        List of event dicts, each containing bookmaker odds. Empty list on error.
    """
    if not ODDS_API_KEY:
        return []

    url = f"{ODDS_API}/sports/{sport}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": regions,
        "markets": markets,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError):
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# ELO System
# ═══════════════════════════════════════════════════════════════════════════════

def _get_elo(team_name, ratings):
    """
    Look up a team's ELO rating, resolving aliases first.
    Defaults to 1500 for unknown teams.
    """
    canonical = TEAM_ALIASES.get(team_name, team_name)
    return ratings.get(canonical, 1500)


def _compute_elo_probabilities(home_elo, away_elo, home_advantage=65):
    """
    Compute match outcome probabilities from ELO ratings.

    Returns:
        (home_win_prob, draw_prob, away_win_prob) — sums to ~1.0
    """
    # Expected score for home team (logistic curve)
    expected_home = 1.0 / (1.0 + 10.0 ** ((away_elo - home_elo - home_advantage) / 400.0))

    # Draw probability — peaks at ~27% for equal teams, drops for mismatches
    rating_diff = home_elo - away_elo + home_advantage
    draw_prob = 0.27 * math.exp(-abs(rating_diff) / 600.0)

    # Distribute remaining probability between home and away wins
    home_win = expected_home * (1.0 - draw_prob)
    away_win = (1.0 - expected_home) * (1.0 - draw_prob)

    return (home_win, draw_prob, away_win)


# ═══════════════════════════════════════════════════════════════════════════════
# Value Bet Detection
# ═══════════════════════════════════════════════════════════════════════════════

def _find_value_bets(home_prob, draw_prob, away_prob, bookmaker_odds):
    """
    Compare model probabilities against bookmaker odds to find value bets.

    Args:
        home_prob: Model probability of home win.
        draw_prob: Model probability of draw.
        away_prob: Model probability of away win.
        bookmaker_odds: List of dicts, each with keys:
            bookmaker, home_odds, draw_odds, away_odds.

    Returns:
        List of value bet dicts with outcome, edge, kelly_fraction, etc.
    """
    value_bets = []
    edge_threshold = 0.02  # 2% minimum edge

    outcomes = [
        ("Home Win", home_prob, "home_odds"),
        ("Draw", draw_prob, "draw_odds"),
        ("Away Win", away_prob, "away_odds"),
    ]

    for outcome_name, model_prob, odds_key in outcomes:
        for bookie in bookmaker_odds:
            decimal_odds = bookie.get(odds_key, 0)
            if decimal_odds <= 1.0:
                continue

            implied_prob = 1.0 / decimal_odds
            edge = model_prob - implied_prob

            if edge > edge_threshold:
                # Kelly criterion: fraction of bankroll to wager
                kelly = (model_prob * decimal_odds - 1.0) / (decimal_odds - 1.0)
                kelly = min(kelly, 0.25)  # Cap at 25%

                # Confidence classification
                if edge > 0.10:
                    confidence = "High"
                elif edge > 0.05:
                    confidence = "Medium"
                else:
                    confidence = "Low"

                value_bets.append({
                    "outcome": outcome_name,
                    "model_probability": round(model_prob, 4),
                    "implied_probability": round(implied_prob, 4),
                    "edge": round(edge, 4),
                    "kelly_fraction": round(kelly, 4),
                    "bookmaker": bookie.get("bookmaker", "Unknown"),
                    "decimal_odds": decimal_odds,
                    "confidence": confidence,
                })

    return value_bets


# ═══════════════════════════════════════════════════════════════════════════════
# Match-Odds Joining
# ═══════════════════════════════════════════════════════════════════════════════

def _normalize_team_name(name):
    """Normalize a team name for fuzzy comparison."""
    canonical = TEAM_ALIASES.get(name, name)
    return canonical.lower().strip()


def _match_odds_to_fixtures(matches, odds_events):
    """
    Join football-data.org match fixtures with odds API events.

    Matches are paired by comparing team names (with alias resolution)
    and kick-off dates (within 1 day tolerance).

    Returns:
        List of dicts, each combining match data with matched odds.
    """
    results = []

    for match in matches:
        home = match.get("homeTeam", {}).get("name", "")
        away = match.get("awayTeam", {}).get("name", "")
        utc_date_str = match.get("utcDate", "")

        # Parse match date
        match_date = None
        if utc_date_str:
            try:
                match_date = datetime.fromisoformat(utc_date_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        home_norm = _normalize_team_name(home)
        away_norm = _normalize_team_name(away)

        matched_odds = None
        for event in odds_events:
            event_home = _normalize_team_name(event.get("home_team", ""))
            event_away = _normalize_team_name(event.get("away_team", ""))

            # Check team name match (either order)
            names_match = (
                (home_norm in event_home or event_home in home_norm) and
                (away_norm in event_away or event_away in away_norm)
            )
            if not names_match:
                continue

            # Check date proximity (within 1 day)
            if match_date and event.get("commence_time"):
                try:
                    event_date = datetime.fromisoformat(
                        event["commence_time"].replace("Z", "+00:00")
                    )
                    if abs((match_date - event_date).total_seconds()) > 86400:
                        continue
                except (ValueError, TypeError):
                    pass

            matched_odds = event
            break

        results.append({
            "match": match,
            "odds": matched_odds,
        })

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# Odds Extraction Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_bookmaker_odds(odds_event):
    """
    Extract structured bookmaker odds from an odds API event.

    Returns:
        List of dicts with: bookmaker, home_odds, draw_odds, away_odds.
    """
    if not odds_event:
        return []

    bookmaker_odds = []
    home_team = odds_event.get("home_team", "")

    for bookie in odds_event.get("bookmakers", []):
        bookie_name = bookie.get("title", bookie.get("key", "Unknown"))
        for market in bookie.get("markets", []):
            if market.get("key") != "h2h":
                continue

            odds_dict = {"bookmaker": bookie_name, "home_odds": 0, "draw_odds": 0, "away_odds": 0}
            for outcome in market.get("outcomes", []):
                name = outcome.get("name", "")
                price = outcome.get("price", 0)
                if name == home_team:
                    odds_dict["home_odds"] = price
                elif name == "Draw":
                    odds_dict["draw_odds"] = price
                else:
                    odds_dict["away_odds"] = price

            bookmaker_odds.append(odds_dict)

    return bookmaker_odds


def _find_best_odds(bookmaker_odds):
    """
    Find the best (highest) odds per outcome across all bookmakers.

    Returns:
        Dict with best_home_odds, best_draw_odds, best_away_odds and
        corresponding best_*_bookmaker fields.
    """
    best = {
        "best_home_odds": 0.0, "best_draw_odds": 0.0, "best_away_odds": 0.0,
        "best_home_bookmaker": "", "best_draw_bookmaker": "", "best_away_bookmaker": "",
    }

    for bookie in bookmaker_odds:
        if bookie.get("home_odds", 0) > best["best_home_odds"]:
            best["best_home_odds"] = bookie["home_odds"]
            best["best_home_bookmaker"] = bookie.get("bookmaker", "")
        if bookie.get("draw_odds", 0) > best["best_draw_odds"]:
            best["best_draw_odds"] = bookie["draw_odds"]
            best["best_draw_bookmaker"] = bookie.get("bookmaker", "")
        if bookie.get("away_odds", 0) > best["best_away_odds"]:
            best["best_away_odds"] = bookie["away_odds"]
            best["best_away_bookmaker"] = bookie.get("bookmaker", "")

    return best


# ═══════════════════════════════════════════════════════════════════════════════
# Main Functions
# ═══════════════════════════════════════════════════════════════════════════════

def get_available_competitions():
    """
    List available competitions from football-data.org.

    Returns:
        List of dicts with code, name, and current_season info.
    """
    if not FOOTBALL_DATA_API_KEY:
        return []

    url = f"{FOOTBALL_DATA_API}/competitions"
    headers = {"X-Auth-Token": FOOTBALL_DATA_API_KEY}

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        competitions = []
        for comp in data.get("competitions", []):
            current_season = comp.get("currentSeason", {})
            if current_season:
                competitions.append({
                    "code": comp.get("code", ""),
                    "name": comp.get("name", ""),
                    "current_season": {
                        "start_date": current_season.get("startDate", ""),
                        "end_date": current_season.get("endDate", ""),
                        "current_matchday": current_season.get("currentMatchday"),
                    },
                })
        return competitions
    except (requests.RequestException, ValueError):
        return []


def get_match_predictions(competition="WC"):
    """
    Build match predictions with ELO probabilities and value bets.

    Fetches matches and odds in parallel, computes ELO-based win/draw/loss
    probabilities, matches them against bookmaker odds, and identifies
    value bets where the model edge exceeds 2%.

    Args:
        competition: Competition code — "WC" (World Cup), "CL" (Champions League),
                     "EC" (European Championship), "FL1" (Ligue 1), etc.

    Returns:
        List of MatchPrediction dataclass instances, sorted by date.
    """
    ratings = load_elo_ratings()

    # Map competition codes to odds API sport keys
    comp_to_sport = {
        "WC": "soccer_fifa_world_cup",
        "CL": "soccer_uefa_champions_league",
        "EC": "soccer_uefa_euro",
        "FL1": "soccer_france_ligue_one",
        "PL": "soccer_epl",
        "BL1": "soccer_germany_bundesliga",
        "SA": "soccer_italy_serie_a",
        "PD": "soccer_spain_la_liga",
    }
    sport_key = comp_to_sport.get(competition, "soccer_fifa_world_cup")

    # Fetch matches and odds in parallel
    matches = []
    odds_events = []

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_matches = executor.submit(_fetch_football_matches, competition)
        future_odds = executor.submit(_fetch_odds, sport_key)

        for future in as_completed([future_matches, future_odds]):
            try:
                if future is future_matches:
                    matches = future.result()
                else:
                    odds_events = future.result()
            except Exception:
                pass

    # If primary competition returned nothing, try fallback competitions
    if not matches and competition == "WC":
        fallback_codes = ["EC", "CL", "FL1", "PL"]
        for code in fallback_codes:
            matches = _fetch_football_matches(code)
            if matches:
                competition = code
                sport_key = comp_to_sport.get(code, sport_key)
                # Re-fetch odds for the new sport
                odds_events = _fetch_odds(sport_key)
                break

    # Join matches with odds
    joined = _match_odds_to_fixtures(matches, odds_events)

    predictions = []
    for item in joined:
        match = item["match"]
        odds_event = item["odds"]

        home_name = match.get("homeTeam", {}).get("name", "Unknown")
        away_name = match.get("awayTeam", {}).get("name", "Unknown")

        # ELO lookup and probability computation
        home_elo = _get_elo(home_name, ratings)
        away_elo = _get_elo(away_name, ratings)
        home_prob, draw_prob, away_prob = _compute_elo_probabilities(home_elo, away_elo)

        # Extract odds
        bookmaker_odds = _extract_bookmaker_odds(odds_event)
        best = _find_best_odds(bookmaker_odds)

        # Detect value bets
        value_bets = _find_value_bets(home_prob, draw_prob, away_prob, bookmaker_odds)

        # Extract score if available
        score = match.get("score", {})
        full_time = score.get("fullTime", {}) if score else {}
        home_score = full_time.get("home") if full_time else None
        away_score = full_time.get("away") if full_time else None

        pred = MatchPrediction(
            match_id=str(match.get("id", "")),
            home_team=home_name,
            away_team=away_name,
            utc_date=match.get("utcDate", ""),
            competition=match.get("competition", {}).get("name", competition),
            status=match.get("status", "SCHEDULED"),
            home_elo=home_elo,
            away_elo=away_elo,
            home_win_prob=round(home_prob, 4),
            draw_prob=round(draw_prob, 4),
            away_win_prob=round(away_prob, 4),
            best_home_odds=best["best_home_odds"],
            best_draw_odds=best["best_draw_odds"],
            best_away_odds=best["best_away_odds"],
            best_home_bookmaker=best["best_home_bookmaker"],
            best_draw_bookmaker=best["best_draw_bookmaker"],
            best_away_bookmaker=best["best_away_bookmaker"],
            all_bookmaker_odds=bookmaker_odds,
            value_bets=value_bets,
            home_score=home_score,
            away_score=away_score,
        )
        predictions.append(pred)

    # Sort by date ascending
    predictions.sort(key=lambda p: p.utc_date or "")

    return predictions
