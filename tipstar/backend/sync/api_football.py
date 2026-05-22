"""
API-Football client (v3.football.api-sports.io direct plan).
Primary data source for player facts, match results, and tournament data.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_BASE_URL = "https://v3.football.api-sports.io"

# Competition IDs on API-Football
COMPETITION_IDS = {
    "FIFA World Cup 2026": 1,
    "UEFA Champions League": 2,
    "Premier League": 39,
    "La Liga": 140,
    "Bundesliga": 78,
    "Serie A": 135,
    "Ligue 1": 61,
}

# World Cup season ID -- API-Football will add 2026 when the tournament begins (June 11 2026).
# Until then, 2022 is the last available World Cup season.
WC_SEASON = 2026

_DAILY_LIMIT = 100
_RATE_WARN_THRESHOLD = 0.80


class APIFootballError(Exception):
    pass


class RateLimitError(APIFootballError):
    pass


def _headers() -> dict:
    return {"x-apisports-key": os.getenv("API_FOOTBALL_KEY", "")}


def _get(endpoint: str, params: dict = None) -> dict:
    url = f"{_BASE_URL}/{endpoint}"
    try:
        resp = requests.get(url, headers=_headers(), params=params or {}, timeout=15)
    except requests.RequestException as exc:
        raise APIFootballError(f"Request failed: {exc}") from exc

    if resp.status_code == 429:
        raise RateLimitError("API-Football rate limit hit")
    if resp.status_code != 200:
        raise APIFootballError(f"HTTP {resp.status_code}: {resp.text[:200]}")

    data = resp.json()

    # Warn at 80% of daily limit
    remaining = data.get("results", {})
    headers_remaining = resp.headers.get("x-ratelimit-requests-remaining")
    if headers_remaining is not None:
        try:
            rem = int(headers_remaining)
            if rem < _DAILY_LIMIT * (1 - _RATE_WARN_THRESHOLD):
                logger.warning(
                    "API-Football rate limit warning: %d requests remaining today", rem
                )
        except ValueError:
            pass

    errors = data.get("errors", {})
    if errors:
        raise APIFootballError(f"API errors: {errors}")

    return data


def get_player(player_name: str) -> Optional[dict]:
    """
    Search for a player by name and return normalised facts.
    Returns None if not found.
    """
    try:
        from datetime import date as _date
        today = _date.today()
        current_season = today.year if today.month >= 8 else today.year - 1
        data = _get("players", {"search": player_name, "season": current_season})
        results = data.get("response", [])
        if not results:
            data = _get("players", {"search": player_name, "season": current_season - 1})
            results = data.get("response", [])
        if not results:
            return None

        entry = results[0]
        p = entry.get("player", {})
        stats = (entry.get("statistics") or [{}])[0]
        team_info = stats.get("team", {})

        birth = p.get("birth", {}) or {}
        age = None
        if birth.get("date"):
            try:
                born = datetime.strptime(birth["date"], "%Y-%m-%d")
                age = (datetime.now(timezone.utc).replace(tzinfo=None) - born).days // 365
            except ValueError:
                pass

        injuries = p.get("injuries") or []
        injury_active = any(
            i.get("season") == WC_SEASON for i in injuries
        )
        status = "Injured" if injury_active else "Active"

        return {
            "api_football_id": p.get("id"),
            "name": p.get("name"),
            "nationality": p.get("nationality"),
            "current_club": team_info.get("name"),
            "age": age,
            "status": status,
            "world_cup_appearances": None,
            "world_cup_goals": None,
        }
    except (APIFootballError, RateLimitError):
        raise
    except Exception as exc:
        logger.error("Unexpected error fetching player %s: %s", player_name, exc)
        return None


def get_matches(competition: str, date_from: str, date_to: str) -> list[dict]:
    """
    Pull fixtures/results for a competition in a date range.
    date_from, date_to: YYYY-MM-DD strings.
    Returns list of normalised match dicts.
    """
    league_id = COMPETITION_IDS.get(competition)
    if not league_id:
        logger.warning("Unknown competition: %s", competition)
        return []

    year = int(date_from[:4])
    # API-Football uses the start year of the season: 2025/26 = 2025
    # Matches in Jan-Jul belong to the season that started the previous year
    from datetime import date as _date
    season = year if _date.today().month >= 8 else year - 1
    try:
        data = _get(
            "fixtures",
            {
                "league": league_id,
                "season": season,
                "from": date_from,
                "to": date_to,
            },
        )
    except (APIFootballError, RateLimitError):
        raise

    results = []
    for fixture in data.get("response", []):
        f = fixture.get("fixture", {})
        teams = fixture.get("teams", {})
        goals = fixture.get("goals", {})
        score = fixture.get("score", {})
        events = fixture.get("events") or []

        scorers = [
            e.get("player", {}).get("name")
            for e in events
            if e.get("type") == "Goal" and e.get("detail") != "Missed Penalty"
        ]

        key_events = []
        for e in events:
            etype = e.get("type", "")
            detail = e.get("detail", "")
            player = e.get("player", {}).get("name", "")
            time = e.get("time", {}).get("elapsed")
            if etype in ("Card", "Var", "Goal"):
                key_events.append(f"{time}' {detail} - {player}")

        venue_info = f.get("venue", {}) or {}
        match_dt = f.get("date")

        results.append({
            "api_fixture_id": f.get("id"),
            "tournament": competition,
            "home_team": teams.get("home", {}).get("name"),
            "away_team": teams.get("away", {}).get("name"),
            "home_score": goals.get("home"),
            "away_score": goals.get("away"),
            "stage": fixture.get("league", {}).get("round"),
            "venue": venue_info.get("name"),
            "match_date": match_dt,
            "scorers": ", ".join(filter(None, scorers)),
            "key_events": "; ".join(key_events),
            "status": f.get("status", {}).get("short"),
        })

    return results


def get_world_cup_squads() -> dict:
    """
    Pull all squad lists for World Cup 2026.
    Returns {team_name: [player_dict, ...]}
    """
    try:
        data = _get("teams", {"league": COMPETITION_IDS["FIFA World Cup 2026"], "season": WC_SEASON})
    except (APIFootballError, RateLimitError):
        raise

    squads = {}
    for entry in data.get("response", []):
        team = entry.get("team", {})
        team_name = team.get("name")
        if not team_name:
            continue

        try:
            sq_data = _get("players/squads", {"team": team.get("id")})
        except APIFootballError as exc:
            logger.warning("Could not fetch squad for %s: %s", team_name, exc)
            continue

        players = []
        for item in sq_data.get("response", []):
            for p in item.get("players", []):
                players.append({
                    "player_name": p.get("name"),
                    "position": p.get("position"),
                    "age": p.get("age"),
                })
        squads[team_name] = players

    return squads


def get_standings(competition: str) -> list[dict]:
    """
    Pull league/group standings for a competition.
    Returns list of standing entry dicts.
    """
    league_id = COMPETITION_IDS.get(competition)
    if not league_id:
        logger.warning("Unknown competition: %s", competition)
        return []

    from datetime import date as _date
    today = _date.today()
    if "World Cup" in competition:
        season = WC_SEASON
    else:
        # API-Football season ID = start year of the season (e.g. 2025 for 2025/26)
        season = today.year if today.month >= 8 else today.year - 1
    try:
        data = _get("standings", {"league": league_id, "season": season})
    except (APIFootballError, RateLimitError):
        raise

    results = []
    for entry in data.get("response", []):
        league_info = entry.get("league", {})
        for group in league_info.get("standings", []):
            for row in group:
                team = row.get("team", {})
                all_stats = row.get("all", {})
                goals = all_stats.get("goals", {})
                results.append({
                    "group_name": row.get("group", ""),
                    "team": team.get("name"),
                    "played": all_stats.get("played", 0),
                    "won": all_stats.get("win", 0),
                    "drawn": all_stats.get("draw", 0),
                    "lost": all_stats.get("lose", 0),
                    "goals_for": goals.get("for", 0),
                    "goals_against": goals.get("against", 0),
                    "goal_difference": row.get("goalsDiff", 0),
                    "points": row.get("points", 0),
                })

    return results
