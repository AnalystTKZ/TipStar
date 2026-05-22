"""
FBref scraper for player and match stats.

This intentionally uses direct requests + BeautifulSoup instead of ScraperFC as
the runtime dependency. ScraperFC 4.5.0 imports a browser/native-request stack at
module import time, which is brittle in CI and scheduled sync jobs.
"""
import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import requests
from bs4 import BeautifulSoup, Comment

logger = logging.getLogger(__name__)

CURRENT_SEASON = "2025-2026"
_BASE = "https://fbref.com"
_RATE_DELAY = 6.5
_LAST_REQUEST_AT = 0.0
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass(frozen=True)
class _LeagueConfig:
    comp_id: str
    slug: str

    @property
    def standard_stats_url(self) -> str:
        return (
            f"{_BASE}/en/comps/{self.comp_id}/{CURRENT_SEASON}/standard/players/"
            f"{CURRENT_SEASON}-{self.slug}-Stats"
        )

    @property
    def schedule_url(self) -> str:
        return (
            f"{_BASE}/en/comps/{self.comp_id}/{CURRENT_SEASON}/schedule/"
            f"{CURRENT_SEASON}-{self.slug}-Scores-and-Fixtures"
        )

    @property
    def league_table_url(self) -> str:
        return f"{_BASE}/en/comps/{self.comp_id}/{CURRENT_SEASON}/{CURRENT_SEASON}-{self.slug}-Stats"


FBREF_LEAGUES = {
    "Premier League": _LeagueConfig("9", "Premier-League"),
    "England Premier League": _LeagueConfig("9", "Premier-League"),
    "La Liga": _LeagueConfig("12", "La-Liga"),
    "Spain La Liga": _LeagueConfig("12", "La-Liga"),
    "Bundesliga": _LeagueConfig("20", "Bundesliga"),
    "Germany Bundesliga": _LeagueConfig("20", "Bundesliga"),
    "Serie A": _LeagueConfig("11", "Serie-A"),
    "Italy Serie A": _LeagueConfig("11", "Serie-A"),
    "Ligue 1": _LeagueConfig("13", "Ligue-1"),
    "France Ligue 1": _LeagueConfig("13", "Ligue-1"),
    "UEFA Champions League": _LeagueConfig("8", "Champions-League"),
}


def get_league_table(league: str, season: str = CURRENT_SEASON) -> Optional[list[dict]]:
    """Pull current league standings from FBref."""
    config = _league_config(league, season)
    if not config:
        return None

    soup = _get_soup(config.league_table_url)
    if not soup:
        return None

    table = _find_table(soup, lambda tag: tag.name == "table" and tag.find(attrs={"data-stat": "squad"}))
    if not table:
        return None

    rows = []
    for tr in table.select("tbody tr"):
        squad = _cell_text(tr, "squad")
        if not squad:
            continue
        rows.append({
            "team": squad,
            "played": _safe_int(_cell_text(tr, "games")),
            "won": _safe_int(_cell_text(tr, "wins")),
            "drawn": _safe_int(_cell_text(tr, "ties")),
            "lost": _safe_int(_cell_text(tr, "losses")),
            "goals_for": _safe_int(_cell_text(tr, "goals_for")),
            "goals_against": _safe_int(_cell_text(tr, "goals_against")),
            "goal_difference": _safe_int(_cell_text(tr, "goal_diff")),
            "points": _safe_int(_cell_text(tr, "points")),
        })
    return rows or None


def get_player_stats(player_name: str, season: str = CURRENT_SEASON) -> Optional[dict]:
    """Find a player in FBref top-league standard-stat tables."""
    needle = _normalise(player_name)
    if not needle:
        return None

    for league in [
        "Premier League",
        "La Liga",
        "Bundesliga",
        "Serie A",
        "Ligue 1",
        "UEFA Champions League",
    ]:
        rows = _standard_player_rows(league, season)
        for row in rows:
            player = row.get("name") or ""
            haystack = _normalise(player)
            if needle == haystack or needle in haystack or _all_tokens_match(needle, haystack):
                return {
                    "name": player,
                    "current_club": row.get("current_club"),
                    "nationality": row.get("nationality"),
                    "position": row.get("position"),
                    "age": row.get("age"),
                    "goals": row.get("goals"),
                    "assists": row.get("assists"),
                    "appearances": row.get("appearances"),
                    "league": league,
                }

    logger.debug("FBref: player '%s' not found in configured leagues", player_name)
    return None


def get_matches(league: str, season: str = CURRENT_SEASON) -> Optional[list[dict]]:
    """Pull completed fixtures for a league season from FBref."""
    config = _league_config(league, season)
    if not config:
        return None

    soup = _get_soup(config.schedule_url)
    if not soup:
        return None

    table = _find_table(soup, lambda tag: tag.name == "table" and tag.find(attrs={"data-stat": "home_team"}))
    if not table:
        return None

    matches = []
    for tr in table.select("tbody tr"):
        score = _cell_text(tr, "score")
        if not score:
            continue
        home_score, away_score = _parse_score(score)
        matches.append({
            "tournament": league,
            "home_team": _cell_text(tr, "home_team"),
            "away_team": _cell_text(tr, "away_team"),
            "home_score": home_score,
            "away_score": away_score,
            "match_date": _cell_text(tr, "date"),
            "stage": _cell_text(tr, "round"),
            "venue": _cell_text(tr, "venue"),
            "scorers": "",
            "key_events": "",
        })
    return matches or None


@lru_cache(maxsize=32)
def _standard_player_rows(league: str, season: str) -> tuple[dict, ...]:
    config = _league_config(league, season)
    if not config:
        return tuple()

    soup = _get_soup(config.standard_stats_url)
    if not soup:
        return tuple()

    table = _find_table(
        soup,
        lambda tag: tag.name == "table" and (
            tag.get("id") == "stats_standard"
            or tag.find(attrs={"data-stat": "player"})
        ),
    )
    if not table:
        return tuple()

    rows = []
    for tr in table.select("tbody tr"):
        player = _cell_text(tr, "player")
        if not player or player == "Player":
            continue
        rows.append({
            "name": player,
            "current_club": _cell_text(tr, "team"),
            "nationality": _clean_nation(_cell_text(tr, "nationality")),
            "position": _cell_text(tr, "position"),
            "age": _safe_int((_cell_text(tr, "age") or "").split("-")[0]),
            "goals": _safe_int(_cell_text(tr, "goals")),
            "assists": _safe_int(_cell_text(tr, "assists")),
            "appearances": _safe_int(_cell_text(tr, "games")),
        })
    return tuple(rows)


def _league_config(league: str, season: str) -> Optional[_LeagueConfig]:
    if season != CURRENT_SEASON:
        logger.warning("FBref: only configured for current season '%s'", CURRENT_SEASON)
        return None
    config = FBREF_LEAGUES.get(league)
    if not config:
        logger.warning("FBref: unsupported league '%s'", league)
    return config


def _get_soup(url: str) -> Optional[BeautifulSoup]:
    global _LAST_REQUEST_AT
    elapsed = time.monotonic() - _LAST_REQUEST_AT
    if elapsed < _RATE_DELAY:
        time.sleep(_RATE_DELAY - elapsed)

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        _LAST_REQUEST_AT = time.monotonic()
        if resp.status_code != 200:
            logger.warning("FBref HTTP %s: %s", resp.status_code, url)
            return None
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        logger.warning("FBref request error for %s: %s", url, exc)
        return None


def _find_table(soup: BeautifulSoup, predicate) -> Optional[BeautifulSoup]:
    table = soup.find(predicate)
    if table:
        return table

    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        if "<table" not in comment:
            continue
        nested = BeautifulSoup(comment, "html.parser")
        table = nested.find(predicate)
        if table:
            return table
    return None


def _cell_text(row, data_stat: str) -> Optional[str]:
    cell = row.find(attrs={"data-stat": data_stat})
    if not cell:
        return None
    text = cell.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text) or None


def _parse_score(score: str) -> tuple[Optional[int], Optional[int]]:
    parts = re.split(r"\s*[–-]\s*", score.strip())
    if len(parts) != 2:
        return None, None
    return _safe_int(parts[0]), _safe_int(parts[1])


def _safe_int(value) -> Optional[int]:
    try:
        text = str(value).strip()
        if not text or text.lower() == "nan":
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _clean_nation(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return re.sub(r"^[a-z]{2}\s+", "", value.strip(), flags=re.I)


def _normalise(value: str) -> str:
    stripped = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(ch for ch in stripped if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()


def _all_tokens_match(needle: str, haystack: str) -> bool:
    tokens = [token for token in needle.split() if len(token) > 1]
    return bool(tokens) and all(token in haystack for token in tokens)
