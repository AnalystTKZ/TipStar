"""
Tournament sync: pulls live data from football-data.org and updates the
tournaments table with current_stage, current_leader, matches_played,
top_scorer (where available), and status.

Also syncs World Cup squad data into world_cup_squads for any WC tournament.
"""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from backend.database.db import get_session_factory, init_db, upsert_tournament
from backend.database.models import Tournament
from backend.sync.football_data import (
    COMPETITION_CODES,
    FootballDataError,
    _get,
)
from backend.sync.sync_logger import log_sync_run

logger = logging.getLogger(__name__)

# Maps tournament names stored in DB → football-data.org competition codes.
# Covers common aliases users might have in Notion.
_NAME_TO_CODE: dict[str, str] = {
    **{k.lower(): v for k, v in COMPETITION_CODES.items()},
    # extra aliases
    "fifa world cup": "WC",
    "world cup": "WC",
    "world cup 2026": "WC",
    "champions league": "CL",
    "ucl": "CL",
    "uefa champions league 2024/25": "CL",
    "premier league": "PL",
    "epl": "PL",
    "la liga": "PD",
    "bundesliga": "BL1",
    "serie a": "SA",
    "ligue 1": "FL1",
    "eredivisie": "DED",
    "primeira liga": "PPL",
    "championship": "ELC",
}


def _resolve_code(name: str) -> str | None:
    return _NAME_TO_CODE.get(name.lower().strip())


def _get_competition_info(code: str) -> dict:
    """Fetch competition metadata: currentSeason, lastUpdated, etc."""
    try:
        return _get(f"competitions/{code}")
    except FootballDataError:
        return {}


def _get_standings_raw(code: str) -> dict:
    try:
        return _get(f"competitions/{code}/standings")
    except FootballDataError:
        return {}


def _get_scorers(code: str) -> list[dict]:
    try:
        data = _get(f"competitions/{code}/scorers", {"limit": 1})
        return data.get("scorers", [])
    except FootballDataError:
        return []


def _derive_leader(standings_data: dict) -> str | None:
    """Return the top-of-table team name from standings response."""
    for standing in standings_data.get("standings", []):
        if standing.get("type") == "TOTAL":
            table = standing.get("table", [])
            if table:
                if not any((row.get("playedGames") or 0) > 0 for row in table):
                    return None
                t = table[0].get("team", {})
                return t.get("shortName") or t.get("name")
    # Fallback: first standing group first row
    for standing in standings_data.get("standings", []):
        table = standing.get("table", [])
        if table:
            if not any((row.get("playedGames") or 0) > 0 for row in table):
                continue
            t = table[0].get("team", {})
            return t.get("shortName") or t.get("name")
    return None


def _derive_matches_played(standings_data: dict) -> int | None:
    """Sum playedGames across all table entries in TOTAL standing."""
    for standing in standings_data.get("standings", []):
        if standing.get("type") == "TOTAL":
            table = standing.get("table", [])
            if table:
                return table[0].get("playedGames")
    return None


def _derive_current_stage(comp_info: dict, standings_data: dict) -> str | None:
    season = comp_info.get("currentSeason", {})
    if season.get("currentMatchday"):
        return f"Matchday {season['currentMatchday']}"
    # For knockout competitions, try winner
    for standing in standings_data.get("standings", []):
        stage = standing.get("stage")
        if stage:
            return stage.replace("_", " ").title()
    return None


def _derive_status(comp_info: dict) -> str | None:
    season = comp_info.get("currentSeason", {})
    winner = season.get("winner")
    if winner:
        return "Completed"
    start = season.get("startDate")
    end = season.get("endDate")
    if not start:
        return None
    today = datetime.now(timezone.utc).date()
    try:
        from datetime import date
        s = date.fromisoformat(start[:10])
        e = date.fromisoformat(end[:10]) if end else None
        if today < s:
            return "Upcoming"
        if e and today > e:
            return "Completed"
        return "Active"
    except (ValueError, TypeError):
        return None


async def _sync_one_tournament(session, tournament: Tournament) -> dict:
    """Sync a single tournament row. Returns a dict with what changed."""
    code = _resolve_code(tournament.name)
    if not code:
        logger.debug("No football-data.org code for tournament: %s", tournament.name)
        return {"name": tournament.name, "skipped": True, "reason": "no_code"}

    comp_info = _get_competition_info(code)
    standings_data = _get_standings_raw(code)
    scorers = _get_scorers(code)

    updates: dict = {}

    leader = _derive_leader(standings_data)
    if leader:
        updates["current_leader"] = leader

    played = _derive_matches_played(standings_data)
    if played is not None:
        updates["matches_played"] = played

    stage = _derive_current_stage(comp_info, standings_data)
    if stage:
        updates["current_stage"] = stage

    status = _derive_status(comp_info)
    if status:
        updates["status"] = status

    if scorers:
        top = scorers[0]
        player = top.get("player", {})
        goals = top.get("goals", "")
        name = player.get("name", "")
        if name:
            updates["top_scorer"] = f"{name} ({goals} goals)" if goals else name

    # Check if season winner known
    season = comp_info.get("currentSeason", {})
    winner = season.get("winner") or {}
    winner_name = winner.get("shortName") or winner.get("name")
    if winner_name and not tournament.current_leader:
        updates["current_leader"] = winner_name

    if updates:
        updates["name"] = tournament.name
        await upsert_tournament(session, updates)
        # Mirror live data back to Notion
        _write_tournament_to_notion(tournament.name, updates)

    return {"name": tournament.name, "skipped": False, "updates": list(updates.keys())}


def _write_tournament_to_notion(name: str, updates: dict) -> None:
    """Find the tournament's Notion page and update it with live data."""
    try:
        from backend.harvester.notion_harvester import _find_page_id, update_tournament
        page_id = _find_page_id("tournaments", "Tournament Name", name)
        if page_id:
            update_tournament(page_id, updates)
        else:
            logger.debug("Tournament '%s' not found in Notion -- skipping write-back", name)
    except Exception as exc:
        logger.warning("Notion tournament write-back failed for '%s': %s", name, exc)


async def _sync_wc_squads(session) -> int:
    """Pull WC squads from football-data.org and upsert into world_cup_squads."""
    from backend.sync.world_cup_sync import _upsert_squad_player
    from backend.sync.football_data import get_world_cup_squads

    try:
        squads = get_world_cup_squads()
    except FootballDataError as exc:
        logger.warning("WC squads fetch failed: %s", exc)
        return 0

    count = 0
    for nation, players in squads.items():
        for player in players:
            ok = await _upsert_squad_player(session, nation, player)
            if ok:
                count += 1
    return count


async def sync_tournaments() -> dict:
    """
    Main entry point. Syncs all tournaments in the DB that have a matching
    football-data.org competition code. Also syncs WC squads if WC tournament present.
    """
    logger.info("Starting tournament sync...")
    factory = get_session_factory()
    updated = skipped = errors = 0
    squad_players = 0
    results = []

    async with factory() as session:
        rows = await session.execute(select(Tournament))
        tournaments = rows.scalars().all()

        for t in tournaments:
            try:
                async with session.begin_nested():
                    result = await _sync_one_tournament(session, t)
                    results.append(result)
                    if result.get("skipped"):
                        skipped += 1
                    else:
                        updated += 1
            except Exception as exc:
                logger.error("Tournament sync error for %s: %s", t.name, exc)
                errors += 1

        await session.commit()

        # Sync WC squads if any WC tournament tracked
        wc_names = {t.name.lower() for t in tournaments}
        if any("world cup" in n or "wc" in n for n in wc_names):
            try:
                async with session.begin_nested():
                    squad_players = await _sync_wc_squads(session)
                await session.commit()
                logger.info("WC squad players synced: %d", squad_players)
            except Exception as exc:
                logger.error("WC squad sync error: %s", exc)

    await log_sync_run(
        sync_type="tournament_sync",
        api_used="football-data.org",
        records_updated=updated,
        errors=errors,
        notes=f"updated={updated} skipped={skipped} squad_players={squad_players}",
    )

    logger.info(
        "Tournament sync complete: updated=%d skipped=%d errors=%d squad_players=%d",
        updated, skipped, errors, squad_players,
    )
    return {
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "squad_players": squad_players,
        "details": results,
    }


async def _main():
    await init_db()
    result = await sync_tournaments()
    print(result)


if __name__ == "__main__":
    asyncio.run(_main())
