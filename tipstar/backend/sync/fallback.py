"""
FootballAPIClient: reads structured football facts from configured providers.

API-Football is opt-in because its free tier can lag or return stale data. By
default the app uses football-data.org for basic fixtures/tables and skips
API-Football unless ENABLE_API_FOOTBALL_LIVE_SYNC=true.
"""
import logging
import os
from typing import Optional

from backend.sync.api_football import (
    APIFootballError, RateLimitError,
    get_player as af_get_player,
    get_matches as af_get_matches,
    get_world_cup_squads as af_get_squads,
    get_standings as af_get_standings,
)
from backend.sync.football_data import (
    FootballDataError,
    get_player as fd_get_player,
    get_matches as fd_get_matches,
    get_world_cup_squads as fd_get_squads,
    get_standings as fd_get_standings,
)

logger = logging.getLogger(__name__)


def _api_football_enabled() -> bool:
    return os.getenv("ENABLE_API_FOOTBALL_LIVE_SYNC", "").lower() in {"1", "true", "yes"}


class FootballAPIClient:

    def get_player(self, player_name: str) -> tuple[Optional[dict], str]:
        """
        Returns (player_dict_or_None, api_used).
        api_used is 'api_football', 'football_data', or 'none'.
        """
        if _api_football_enabled():
            try:
                result = af_get_player(player_name)
                return result, "api_football"
            except RateLimitError as exc:
                logger.warning("API-Football rate limit for player '%s': %s -- falling back", player_name, exc)
            except APIFootballError as exc:
                logger.warning("API-Football error for player '%s': %s -- falling back", player_name, exc)

        try:
            result = fd_get_player(player_name)
            return result, "football_data"
        except FootballDataError as exc:
            logger.error("football-data.org error for player '%s': %s -- skipping", player_name, exc)

        return None, "none"

    def get_matches(
        self, competition: str, date_from: str, date_to: str
    ) -> tuple[list[dict], str]:
        """
        Returns (match_list, api_used).
        """
        if _api_football_enabled():
            try:
                result = af_get_matches(competition, date_from, date_to)
                return result, "api_football"
            except RateLimitError as exc:
                logger.warning("API-Football rate limit for matches '%s': %s -- falling back", competition, exc)
            except APIFootballError as exc:
                logger.warning("API-Football error for matches '%s': %s -- falling back", competition, exc)

        try:
            result = fd_get_matches(competition, date_from, date_to)
            return result, "football_data"
        except FootballDataError as exc:
            logger.error("football-data.org error for matches '%s': %s -- skipping", competition, exc)

        return [], "none"

    def get_world_cup_squads(self) -> tuple[dict, str]:
        """
        Returns (squads_dict, api_used).
        squads_dict: {team_name: [player_dict, ...]}
        """
        if _api_football_enabled():
            try:
                result = af_get_squads()
                return result, "api_football"
            except RateLimitError as exc:
                logger.warning("API-Football rate limit for WC squads: %s -- falling back", exc)
            except APIFootballError as exc:
                logger.warning("API-Football error for WC squads: %s -- falling back", exc)

        try:
            result = fd_get_squads()
            return result, "football_data"
        except FootballDataError as exc:
            logger.error("football-data.org error for WC squads: %s -- skipping", exc)

        return {}, "none"

    def get_standings(self, competition: str) -> tuple[list[dict], str]:
        """
        Returns (standings_list, api_used).
        """
        if _api_football_enabled():
            try:
                result = af_get_standings(competition)
                return result, "api_football"
            except RateLimitError as exc:
                logger.warning("API-Football rate limit for standings '%s': %s -- falling back", competition, exc)
            except APIFootballError as exc:
                logger.warning("API-Football error for standings '%s': %s -- falling back", competition, exc)

        try:
            result = fd_get_standings(competition)
            return result, "football_data"
        except FootballDataError as exc:
            logger.error("football-data.org error for standings '%s': %s -- skipping", competition, exc)

        return [], "none"
