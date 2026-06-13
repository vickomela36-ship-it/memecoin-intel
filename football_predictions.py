"""
Football match prediction engine using ELO ratings.
Outputs picks with probability, confidence, and upside for use on
simplified platforms like Hotake and Picks.
"""

import json
import os
import math
import requests
from dataclasses import dataclass, field
from datetime import datetime

from config import (
    FOOTBALL_DATA_API,
    FOOTBALL_DATA_API_KEY,
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
    # Club teams
    "Real Madrid": 2080, "Manchester City": 2070, "Bayern Munich": 2040,
    "Liverpool": 2030, "FC Barcelona": 2020, "Arsenal": 2010,
    "Paris Saint-Germain": 2000, "Inter Milan": 1990, "AC Milan": 1960,
    "Juventus": 1950, "Borussia Dortmund": 1940, "Atlético Madrid": 1930,
    "Chelsea": 1920, "Napoli": 1910, "Bayer Leverkusen": 1900,
    "Tottenham Hotspur": 1880, "Aston Villa": 1860, "Newcastle United": 1850,
    "RB Leipzig": 1840, "Atalanta": 1830, "AS Roma": 1810,
    "Manchester United": 1870, "Benfica": 1850, "Porto": 1830,
    "Sporting CP": 1810, "Ajax": 1800, "PSV Eindhoven": 1790,
    "Feyenoord": 1770, "Celtic": 1760, "Rangers": 1740,
    "Olympique Lyonnais": 1800, "Olympique Marseille": 1810,
    "AS Monaco": 1790, "LOSC Lille": 1780, "Stade Rennais": 1740,
    "VfB Stuttgart": 1800, "Eintracht Frankfurt": 1790,
    "SC Freiburg": 1760, "VfL Wolfsburg": 1750, "1. FSV Mainz 05": 1720,
    "Lazio": 1820, "Fiorentina": 1800, "Bologna": 1770, "Torino": 1750,
    "Real Sociedad": 1840, "Athletic Club": 1820, "Villarreal": 1810,
    "Real Betis": 1790, "Sevilla": 1800, "Girona": 1770,
    "West Ham United": 1830, "Brighton & Hove Albion": 1830,
    "Crystal Palace": 1790, "Fulham": 1780, "Brentford": 1780,
    "Wolverhampton Wanderers": 1770, "Nottingham Forest": 1770,
    "Everton": 1750, "Bournemouth": 1770, "Leicester City": 1760,
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
    "FC Bayern München": "Bayern Munich",
    "BV Borussia 09 Dortmund": "Borussia Dortmund",
    "Club Atlético de Madrid": "Atlético Madrid",
    "SSC Napoli": "Napoli",
    "Bayer 04 Leverkusen": "Bayer Leverkusen",
    "Tottenham Hotspur FC": "Tottenham Hotspur",
    "Wolverhampton Wanderers FC": "Wolverhampton Wanderers",
    "Newcastle United FC": "Newcastle United",
    "Manchester City FC": "Manchester City",
    "Manchester United FC": "Manchester United",
    "Liverpool FC": "Liverpool",
    "Arsenal FC": "Arsenal",
    "Chelsea FC": "Chelsea",
    "Aston Villa FC": "Aston Villa",
    "West Ham United FC": "West Ham United",
    "Brighton & Hove Albion FC": "Brighton & Hove Albion",
    "Crystal Palace FC": "Crystal Palace",
    "Fulham FC": "Fulham",
    "Brentford FC": "Brentford",
    "Everton FC": "Everton",
    "AFC Bournemouth": "Bournemouth",
    "Leicester City FC": "Leicester City",
    "Nottingham Forest FC": "Nottingham Forest",
    "Paris Saint-Germain FC": "Paris Saint-Germain",
    "FC Barcelona": "FC Barcelona",
    "Real Madrid CF": "Real Madrid",
    "Club Atlético de Madrid": "Atlético Madrid",
    "Villarreal CF": "Villarreal",
    "Real Betis Balompié": "Real Betis",
    "Sevilla FC": "Sevilla",
    "Girona FC": "Girona",
    "Real Sociedad de Fútbol": "Real Sociedad",
    "SL Benfica": "Benfica",
    "FC Porto": "Porto",
    "AFC Ajax": "Ajax",
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
    home_elo: float = 1500.0
    away_elo: float = 1500.0
    home_win_prob: float = 0.33
    draw_prob: float = 0.34
    away_win_prob: float = 0.33
    # The pick
    pick: str = ""
    pick_probability: float = 0.0
    pick_confidence: str = "Low"
    upside: str = ""
    elo_gap: float = 0.0
    # Score if finished
    home_score: int = None
    away_score: int = None


# ═══════════════════════════════════════════════════════════════════════════════
# JSON Persistence
# ═══════════════════════════════════════════════════════════════════════════════

def _load_json(path):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def load_elo_ratings():
    saved = _load_json(ELO_RATINGS_FILE)
    if saved and isinstance(saved, dict):
        return saved
    return dict(DEFAULT_ELO)


def save_elo_ratings(ratings):
    _save_json(ELO_RATINGS_FILE, ratings)


# ═══════════════════════════════════════════════════════════════════════════════
# Data Fetching
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_football_matches(competition="WC", status=None):
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


# ═══════════════════════════════════════════════════════════════════════════════
# ELO System
# ═══════════════════════════════════════════════════════════════════════════════

def _get_elo(team_name, ratings):
    if not team_name:
        return 1500
    canonical = TEAM_ALIASES.get(team_name, team_name)
    return ratings.get(canonical, 1500)


def _compute_elo_probabilities(home_elo, away_elo, home_advantage=65):
    expected_home = 1.0 / (1.0 + 10.0 ** ((away_elo - home_elo - home_advantage) / 400.0))
    rating_diff = home_elo - away_elo + home_advantage
    draw_prob = 0.27 * math.exp(-abs(rating_diff) / 600.0)
    home_win = expected_home * (1.0 - draw_prob)
    away_win = (1.0 - expected_home) * (1.0 - draw_prob)
    return (home_win, draw_prob, away_win)


# ═══════════════════════════════════════════════════════════════════════════════
# Pick Logic
# ═══════════════════════════════════════════════════════════════════════════════

def _determine_pick(home_team, away_team, home_prob, draw_prob, away_prob, elo_gap):
    """Determine the best pick, its confidence, and the upside narrative."""
    probs = {"home": home_prob, "draw": draw_prob, "away": away_prob}
    best_outcome = max(probs, key=probs.get)
    best_prob = probs[best_outcome]

    if best_outcome == "home":
        pick = home_team
    elif best_outcome == "away":
        pick = away_team
    else:
        pick = "Draw"

    # Confidence based on probability dominance
    if best_prob >= 0.60:
        confidence = "Very High"
    elif best_prob >= 0.48:
        confidence = "High"
    elif best_prob >= 0.38:
        confidence = "Medium"
    else:
        confidence = "Low"

    # Upside — what makes this pick interesting
    abs_gap = abs(elo_gap)
    if abs_gap >= 150 and best_prob >= 0.55:
        upside = "Strong favorite, high-probability pick"
    elif abs_gap >= 150 and best_prob < 0.55:
        upside = "Clear underdog story — massive upside if they pull it off"
    elif abs_gap < 50:
        upside = "Coin-flip match — small edges matter here"
    elif best_prob >= 0.45:
        upside = "Slight lean with home advantage baked in"
    else:
        upside = "Moderate edge — worth a look"

    # Override: if draw is close to the best, flag it
    if best_outcome != "draw" and draw_prob > 0.24:
        upside += " | Draw is live (~{:.0%})".format(draw_prob)

    # Underdog upside callout
    if best_outcome == "away" and away_prob < 0.40:
        upside = f"Underdog pick! {away_team} at {away_prob:.0%} — high upside if right"
    elif best_outcome == "home" and home_prob < 0.40:
        upside = f"Underdog pick! {home_team} at {home_prob:.0%} — high upside if right"

    return pick, best_prob, confidence, upside


# ═══════════════════════════════════════════════════════════════════════════════
# Main Functions
# ═══════════════════════════════════════════════════════════════════════════════

def get_available_competitions():
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
    Build match predictions with ELO probabilities, picks, and upside.
    No odds/bookmaker data — pure model-driven picks.
    """
    ratings = load_elo_ratings()
    matches = _fetch_football_matches(competition)

    if not matches and competition == "WC":
        for code in ["EC", "CL", "PL", "FL1"]:
            matches = _fetch_football_matches(code)
            if matches:
                competition = code
                break

    predictions = []
    for match in matches:
        home_name = match.get("homeTeam", {}).get("name") or "Unknown"
        away_name = match.get("awayTeam", {}).get("name") or "Unknown"

        home_elo = _get_elo(home_name, ratings)
        away_elo = _get_elo(away_name, ratings)
        elo_gap = home_elo - away_elo
        home_prob, draw_prob, away_prob = _compute_elo_probabilities(home_elo, away_elo)

        pick, pick_prob, confidence, upside = _determine_pick(
            home_name, away_name, home_prob, draw_prob, away_prob, elo_gap
        )

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
            pick=pick,
            pick_probability=round(pick_prob, 4),
            pick_confidence=confidence,
            upside=upside,
            elo_gap=round(elo_gap, 1),
            home_score=home_score,
            away_score=away_score,
        )
        predictions.append(pred)

    predictions.sort(key=lambda p: p.utc_date or "")
    return predictions
