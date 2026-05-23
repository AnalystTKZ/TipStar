"""
Sync scheduler: runs player, match, and world cup syncs on schedule.
- player_sync: every 6 hours
- match_sync: every 30 min on match days, every 6 hours otherwise
- world_cup_sync: every 1 hour

Match day detection: checks Supabase matches table for today's fixtures.
Stores match_day flag in Supabase settings table.
"""
import asyncio
import logging
import os
import sys
import time
from datetime import date, datetime, time as dt_time, timezone

from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from backend.database.db import get_session_factory, init_db
from backend.sync.player_sync import sync_players
from backend.sync.team_sync import sync_teams
from backend.sync.match_sync import sync_matches
from backend.sync.tournament_sync import sync_tournaments
from backend.sync.world_cup_sync import sync_world_cup
from backend.scheduler.orchestrator import run_youtube_harvest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/sync.log"),
    ],
)
logger = logging.getLogger("sync_scheduler")

# Intervals in seconds
_PLAYER_INTERVAL = 6 * 3600
_TEAM_INTERVAL = 6 * 3600
_TOURNAMENT_INTERVAL = 1 * 3600
_MATCH_INTERVAL_MATCHDAY = 30 * 60
_MATCH_INTERVAL_NORMAL = 6 * 3600
_WC_INTERVAL = 1 * 3600
_YOUTUBE_INTERVAL_NORMAL = 2 * 3600
_YOUTUBE_INTERVAL_WORLD_CUP = 1 * 3600


async def is_match_day() -> bool:
    """Return True if any match is scheduled in Supabase for today (UTC)."""
    try:
        factory = get_session_factory()
        today = datetime.now(timezone.utc).date().isoformat()
        async with factory() as session:
            result = await session.execute(
                text(
                    "SELECT COUNT(*) FROM matches WHERE DATE(match_date) = :today"
                ).bindparams(today=today)
            )
            count = result.scalar()
            return (count or 0) > 0
    except Exception as exc:
        logger.warning("match day check failed: %s", exc)
        return False


async def _set_match_day_flag(value: bool) -> None:
    """Upsert the match_day flag in the settings table."""
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                text(
                    """INSERT INTO settings (key, value, updated_at)
                    VALUES ('match_day', :val, :now)
                    ON CONFLICT (key) DO UPDATE SET value = :val, updated_at = :now"""
                ).bindparams(
                    val="true" if value else "false",
                    now=datetime.now(timezone.utc),
                )
            )
            await session.commit()
    except Exception as exc:
        logger.warning("Could not update match_day flag: %s", exc)


def _is_world_cup_window() -> bool:
    today = datetime.now(timezone.utc).date()
    return date(2026, 6, 11) <= today <= date(2026, 7, 19)


def _should_run_youtube_now() -> bool:
    if _is_world_cup_window():
        return True
    now = datetime.now(timezone.utc).time()
    return dt_time(6, 0) <= now <= dt_time(23, 59)


async def run_scheduler() -> None:
    logger.info("=== TipStar sync scheduler starting ===")
    await init_db()

    last_player_sync = 0.0
    last_team_sync = 0.0
    last_tournament_sync = 0.0
    last_match_sync = 0.0
    last_wc_sync = 0.0
    last_youtube_harvest = 0.0

    while True:
        now = time.monotonic()

        # Player sync every 6 hours
        if now - last_player_sync >= _PLAYER_INTERVAL:
            logger.info("Running player sync...")
            try:
                result = await sync_players()
                logger.info("Player sync done: %s", result)
            except Exception as exc:
                logger.error("Player sync crashed: %s", exc)
            last_player_sync = time.monotonic()

        # Team sync every 6 hours (manager changes, league updates)
        if now - last_team_sync >= _TEAM_INTERVAL:
            logger.info("Running team sync...")
            try:
                result = await sync_teams()
                logger.info("Team sync done: %s", result)
            except Exception as exc:
                logger.error("Team sync crashed: %s", exc)
            last_team_sync = time.monotonic()

        # Tournament sync every hour (stage, leader, scorer — changes with each matchday)
        if now - last_tournament_sync >= _TOURNAMENT_INTERVAL:
            logger.info("Running tournament sync...")
            try:
                result = await sync_tournaments()
                logger.info("Tournament sync done: %s", result)
            except Exception as exc:
                logger.error("Tournament sync crashed: %s", exc)
            last_tournament_sync = time.monotonic()

        # World Cup sync every hour
        if now - last_wc_sync >= _WC_INTERVAL:
            logger.info("Running World Cup sync...")
            try:
                result = await sync_world_cup()
                logger.info("World Cup sync done: %s", result)
            except Exception as exc:
                logger.error("World Cup sync crashed: %s", exc)
            last_wc_sync = time.monotonic()

        # Match sync -- interval depends on match day
        match_day = await is_match_day()
        await _set_match_day_flag(match_day)
        match_interval = _MATCH_INTERVAL_MATCHDAY if match_day else _MATCH_INTERVAL_NORMAL

        if now - last_match_sync >= match_interval:
            logger.info("Running match sync (match_day=%s)...", match_day)
            try:
                result = await sync_matches()
                logger.info("Match sync done: %s", result)
            except Exception as exc:
                logger.error("Match sync crashed: %s", exc)
            last_match_sync = time.monotonic()

        youtube_interval = _YOUTUBE_INTERVAL_WORLD_CUP if _is_world_cup_window() else _YOUTUBE_INTERVAL_NORMAL
        if now - last_youtube_harvest >= youtube_interval and _should_run_youtube_now():
            logger.info("Running YouTube intelligence harvest...")
            try:
                result = await run_youtube_harvest(hours=6)
                logger.info("YouTube intelligence harvest done: %s", result)
            except Exception as exc:
                logger.error("YouTube intelligence harvest crashed: %s", exc)
            last_youtube_harvest = time.monotonic()

        # Sleep 60s between each loop tick
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(run_scheduler())
