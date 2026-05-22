"""
football-data.org client.
Backup data source used when API-Football is unavailable or rate-limited.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.football-data.org/v4"

# Competition codes on football-data.org
COMPETITION_CODES = {
    "FIFA World Cup 2026": "WC",
    "UEFA Champions League": "CL",
    "Premier League": "PL",
    "La Liga": "PD",
    "Bundesliga": "BL1",
    "Serie A": "SA",
    "Ligue 1": "FL1",
}


class FootballDataError(Exception):
    pass


def _headers() -> dict:
    return {"X-Auth-Token": os.getenv("FOOTBALL_DATA_KEY", "")}


def _get(endpoint: str, params: dict = None) -> dict:
    url = f"{_BASE_URL}/{endpoint}"
    try:
        resp = requests.get(url, headers=_headers(), params=params or {}, timeout=15)
    except requests.RequestException as exc:
        raise FootballDataError(f"Request failed: {exc}") from exc

    if resp.status_code == 429:
        raise FootballDataError("football-data.org rate limit hit")
    if resp.status_code == 403:
        raise FootballDataError("football-data.org: access denied (check tier/competition)")
    if resp.status_code != 200:
        raise FootballDataError(f"HTTP {resp.status_code}: {resp.text[:200]}")

    return resp.json()


def get_player(player_name: str) -> Optional[dict]:
    """
    Player search is not available on the football-data.org free tier.
    Raises FootballDataError so the fallback chain records the skip cleanly.
    """
    raise FootballDataError(
        "football-data.org: player search not available on free tier -- use API-Football"
    )


def get_matches(competition: str, date_from: str, date_to: str) -> list[dict]:
    """
    Pull fixtures/results for a competition in a date range.
    date_from, date_to: YYYY-MM-DD strings.
    """
    code = COMPETITION_CODES.get(competition)
    if not code:
        logger.warning("Unknown competition for football-data.org: %s", competition)
        return []

    try:
        data = _get(
            f"competitions/{code}/matches",
            {"dateFrom": date_from, "dateTo": date_to},
        )
    except FootballDataError:
        raise

    results = []
    for m in data.get("matches", []):
        home = m.get("homeTeam", {})
        away = m.get("awayTeam", {})
        ft = (m.get("score", {}) or {}).get("fullTime", {}) or {}
        scorers_raw = m.get("goals") or []
        scorers = [
            g.get("scorer", {}).get("name")
            for g in scorers_raw
            if g.get("scorer")
        ]

        results.append({
            "api_fixture_id": m.get("id"),
            "tournament": competition,
            "home_team": home.get("shortName") or home.get("name"),
            "away_team": away.get("shortName") or away.get("name"),
            "home_score": ft.get("home"),
            "away_score": ft.get("away"),
            "stage": m.get("stage"),
            "venue": None,
            "match_date": m.get("utcDate"),
            "scorers": ", ".join(filter(None, scorers)),
            "key_events": "",
            "status": m.get("status"),
        })

    return results


def get_world_cup_squads() -> dict:
    """
    Pull World Cup squads via football-data.org teams endpoint.
    Returns {team_name: [player_dict, ...]}
    """
    try:
        data = _get("competitions/WC/teams")
    except FootballDataError:
        raise

    squads = {}
    for team_entry in data.get("teams", []):
        team_name = team_entry.get("shortName") or team_entry.get("name")
        squad = []
        for p in team_entry.get("squad", []):
            squad.append({
                "player_name": p.get("name"),
                "position": p.get("position"),
                "age": None,
            })
        squads[team_name] = squad

    return squads


def get_standings(competition: str) -> list[dict]:
    """
    Pull standings for a competition.
    Returns list of standing entry dicts.
    """
    code = COMPETITION_CODES.get(competition)
    if not code:
        logger.warning("Unknown competition for football-data.org: %s", competition)
        return []

    try:
        data = _get(f"competitions/{code}/standings")
    except FootballDataError:
        raise

    results = []
    for standing in data.get("standings", []):
        group = standing.get("group", "")
        for row in standing.get("table", []):
            team = row.get("team", {})
            results.append({
                "group_name": group,
                "team": team.get("shortName") or team.get("name"),
                "played": row.get("playedGames", 0),
                "won": row.get("won", 0),
                "drawn": row.get("draw", 0),
                "lost": row.get("lost", 0),
                "goals_for": row.get("goalsFor", 0),
                "goals_against": row.get("goalsAgainst", 0),
                "goal_difference": row.get("goalDifference", 0),
                "points": row.get("points", 0),
            })

    return results
