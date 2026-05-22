"""
World Cup 2026 sync: groups, standings, squads, disciplinary records.
Updates Supabase world_cup_groups and world_cup_squads tables.
Updates Notion Teams database with World Cup Status per team.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests
from sqlalchemy import select, text

from backend.database.db import get_session_factory, init_db
from backend.sync.fallback import FootballAPIClient
from backend.sync.sync_logger import log_sync_run

logger = logging.getLogger(__name__)

_NOTION_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"

_client = FootballAPIClient()

# World Cup status mapping from standings position / knockout results
_STATUS_MAP = {
    "winner": "Winner",
    "runner_up": "Runner Up",
    "eliminated": "Eliminated",
    "active": "In Tournament",
}


def _notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('NOTION_API_KEY', '')}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _update_notion_team_wc_status(team_name: str, wc_status: str) -> bool:
    """
    Update World Cup Status on a Notion Teams database entry.
    Only touches World Cup Status -- never priority, playing style, notes, manager.
    """
    db_id = os.getenv("NOTION_TEAMS_DB_ID", "")
    if not db_id:
        return False
    try:
        resp = requests.post(
            f"{_NOTION_BASE}/databases/{db_id}/query",
            json={"filter": {"property": "Name", "title": {"equals": team_name}}},
            headers=_notion_headers(),
            timeout=15,
        )
        if resp.status_code != 200:
            return False
        results = resp.json().get("results", [])
        if not results:
            logger.debug("Team '%s' not found in Notion Teams db", team_name)
            return False

        page_id = results[0]["id"]
        patch = requests.patch(
            f"{_NOTION_BASE}/pages/{page_id}",
            json={"properties": {"World Cup Status": {"select": {"name": wc_status}}}},
            headers=_notion_headers(),
            timeout=15,
        )
        if patch.status_code != 200:
            logger.warning("Notion team WC status update failed for '%s': %s", team_name, patch.status_code)
            return False
        return True
    except Exception as exc:
        logger.warning("Notion team WC status error for '%s': %s", team_name, exc)
        return False


async def _upsert_group_standing(session, row: dict) -> bool:
    try:
        result = await session.execute(
            text(
                "SELECT id FROM world_cup_groups WHERE group_name = :g AND team = :t"
            ).bindparams(g=row.get("group_name", ""), t=row.get("team", ""))
        )
        existing = result.fetchone()

        now = datetime.now(timezone.utc)
        if existing:
            await session.execute(
                text(
                    """UPDATE world_cup_groups SET
                        played = :played, won = :won, drawn = :drawn, lost = :lost,
                        goals_for = :goals_for, goals_against = :goals_against,
                        goal_difference = :goal_difference, points = :points,
                        updated_at = :now
                    WHERE group_name = :group_name AND team = :team"""
                ).bindparams(
                    played=row.get("played", 0),
                    won=row.get("won", 0),
                    drawn=row.get("drawn", 0),
                    lost=row.get("lost", 0),
                    goals_for=row.get("goals_for", 0),
                    goals_against=row.get("goals_against", 0),
                    goal_difference=row.get("goal_difference", 0),
                    points=row.get("points", 0),
                    now=now,
                    group_name=row.get("group_name", ""),
                    team=row.get("team", ""),
                )
            )
        else:
            await session.execute(
                text(
                    """INSERT INTO world_cup_groups
                        (group_name, team, played, won, drawn, lost,
                         goals_for, goals_against, goal_difference, points, updated_at)
                    VALUES
                        (:group_name, :team, :played, :won, :drawn, :lost,
                         :goals_for, :goals_against, :goal_difference, :points, :now)"""
                ).bindparams(
                    group_name=row.get("group_name", ""),
                    team=row.get("team", ""),
                    played=row.get("played", 0),
                    won=row.get("won", 0),
                    drawn=row.get("drawn", 0),
                    lost=row.get("lost", 0),
                    goals_for=row.get("goals_for", 0),
                    goals_against=row.get("goals_against", 0),
                    goal_difference=row.get("goal_difference", 0),
                    points=row.get("points", 0),
                    now=now,
                )
            )
        return True
    except Exception as exc:
        logger.error("Group standing upsert error: %s", exc)
        return False


async def _upsert_squad_player(session, nation: str, player: dict) -> bool:
    try:
        result = await session.execute(
            text(
                "SELECT id FROM world_cup_squads WHERE nation = :n AND player_name = :p"
            ).bindparams(n=nation, p=player.get("player_name", ""))
        )
        existing = result.fetchone()

        now = datetime.now(timezone.utc)
        if existing:
            await session.execute(
                text(
                    """UPDATE world_cup_squads SET
                        club = :club, position = :position, updated_at = :now
                    WHERE nation = :nation AND player_name = :player_name"""
                ).bindparams(
                    club=player.get("club", ""),
                    position=player.get("position", ""),
                    now=now,
                    nation=nation,
                    player_name=player.get("player_name", ""),
                )
            )
        else:
            await session.execute(
                text(
                    """INSERT INTO world_cup_squads
                        (nation, player_name, club, position, updated_at)
                    VALUES (:nation, :player_name, :club, :position, :now)"""
                ).bindparams(
                    nation=nation,
                    player_name=player.get("player_name", ""),
                    club=player.get("club", ""),
                    position=player.get("position", ""),
                    now=now,
                )
            )
        return True
    except Exception as exc:
        logger.error("Squad player upsert error: %s", exc)
        return False


async def sync_world_cup() -> dict:
    """
    Sync World Cup groups, standings, and squads.
    Updates Supabase world_cup_groups and world_cup_squads.
    Updates Notion Teams with World Cup Status.
    """
    logger.info("Starting World Cup sync...")
    await init_db()
    factory = get_session_factory()

    groups_updated = 0
    squads_updated = 0
    errors = 0
    api_used = "none"

    async with factory() as session:
        # Sync group standings
        try:
            standings, api_used = _client.get_standings("FIFA World Cup 2026")
            for row in standings:
                ok = await _upsert_group_standing(session, row)
                if ok:
                    groups_updated += 1
                else:
                    errors += 1

                # Update Notion team WC status
                # Groups stage: all teams still playing = "In Tournament"
                if row.get("team"):
                    _update_notion_team_wc_status(row["team"], "In Tournament")

            await session.commit()
            logger.info("Groups synced: %d rows (via %s)", groups_updated, api_used)
        except Exception as exc:
            logger.error("World Cup standings sync error: %s", exc)
            errors += 1
            await session.rollback()

        # Sync squads
        try:
            squads, sq_api = _client.get_world_cup_squads()
            if sq_api != "none":
                api_used = sq_api
            for nation, players in squads.items():
                for player in players:
                    ok = await _upsert_squad_player(session, nation, player)
                    if ok:
                        squads_updated += 1
                    else:
                        errors += 1
            await session.commit()
            logger.info("Squads synced: %d players (via %s)", squads_updated, sq_api)
        except Exception as exc:
            logger.error("World Cup squads sync error: %s", exc)
            errors += 1
            await session.rollback()

    notes = f"Groups: {groups_updated} rows | Squad players: {squads_updated}"
    await log_sync_run(
        sync_type="world_cup_sync",
        api_used=api_used,
        records_updated=groups_updated + squads_updated,
        errors=errors,
        notes=notes,
    )

    logger.info(
        "World Cup sync complete: %d group rows, %d squad players, %d errors",
        groups_updated, squads_updated, errors,
    )
    return {
        "groups_updated": groups_updated,
        "squads_updated": squads_updated,
        "errors": errors,
        "api_used": api_used,
    }


if __name__ == "__main__":
    asyncio.run(sync_world_cup())
