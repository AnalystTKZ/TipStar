"""
Player sync: pulls live player facts and overwrites factual fields
in Supabase players table and Notion Players database.

Source priority:
  1. Transfermarkt scraper  -- club, age, market value, injury/suspension status, nationality
  2. FBref direct scrape    -- optional club confirmation, position, appearances
  3. API-Football           -- optional paid-plan supplement for WC player data

Owned fields (overwritten every run):
  current_club, age, status, world_cup_appearances, world_cup_goals,
  nationality

Never touched:
  notes, tier, content_angle, instagram_followers
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests
from sqlalchemy import select

from backend.database.db import get_session_factory, init_db
from backend.database.models import Player
from backend.sync.sync_logger import log_sync_run

logger = logging.getLogger(__name__)

_NOTION_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


def _notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('NOTION_API_KEY', '')}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _query_notion_player(name: str) -> Optional[str]:
    db_id = os.getenv("NOTION_PLAYERS_DB_ID", "")
    if not db_id:
        return None
    try:
        resp = requests.post(
            f"{_NOTION_BASE}/databases/{db_id}/query",
            json={"filter": {"property": "Name", "title": {"equals": name}}},
            headers=_notion_headers(),
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        results = resp.json().get("results", [])
        return results[0]["id"] if results else None
    except Exception as exc:
        logger.warning("Notion player query error for '%s': %s", name, exc)
        return None


def _update_notion_player(page_id: str, facts: dict) -> bool:
    """Patch only owned factual fields. Never touches Name, Notes, Tier, Content Angle, Position."""
    props = {}

    if facts.get("current_club") is not None:
        props["Current Club"] = {
            "rich_text": [{"text": {"content": str(facts["current_club"])}}]
        }
    if facts.get("age") is not None:
        props["Age"] = {"number": int(facts["age"])}
    if facts.get("status") is not None:
        props["Status"] = {"select": {"name": str(facts["status"])}}
    if facts.get("world_cup_appearances") is not None:
        props["World Cup Appearances"] = {"number": int(facts["world_cup_appearances"])}
    if facts.get("world_cup_goals") is not None:
        props["World Cup Goals"] = {"number": int(facts["world_cup_goals"])}
    if facts.get("nationality") is not None:
        props["Nationality"] = {
            "rich_text": [{"text": {"content": str(facts["nationality"])}}]
        }
    if facts.get("market_value_eur") is not None:
        props["Market Value"] = {"number": int(facts["market_value_eur"])}

    props["Last Updated"] = {
        "date": {"start": datetime.now(timezone.utc).date().isoformat()}
    }

    if not props:
        return True

    try:
        resp = requests.patch(
            f"{_NOTION_BASE}/pages/{page_id}",
            json={"properties": props},
            headers=_notion_headers(),
            timeout=15,
        )
        return resp.status_code == 200
    except Exception as exc:
        logger.warning("Notion player update error for page %s: %s", page_id, exc)
        return False


def _fetch_from_transfermarkt(name: str) -> tuple[Optional[dict], str]:
    try:
        from backend.sync.transfermarkt import get_player
        result = get_player(name)
        return result, "transfermarkt"
    except Exception as exc:
        logger.warning("Transfermarkt error for '%s': %s", name, exc)
        return None, "transfermarkt_error"


def _fetch_from_fbref(name: str) -> tuple[Optional[dict], str]:
    try:
        from backend.sync.fbref import get_player_stats
        result = get_player_stats(name)
        return result, "fbref"
    except Exception as exc:
        logger.warning("FBref error for '%s': %s", name, exc)
        return None, "fbref_error"


def _should_fetch_fbref(tm_facts: Optional[dict]) -> bool:
    enabled = os.getenv("ENABLE_FBREF_PLAYER_SYNC", "").lower() in {"1", "true", "yes"}
    if enabled:
        return True
    if not tm_facts:
        return True
    return any(not tm_facts.get(field) for field in ["current_club", "position", "age", "nationality"])


def _fetch_from_api_football(name: str) -> tuple[Optional[dict], str]:
    """Optional paid-plan supplement. Disabled by default to protect the free tier."""
    enabled = os.getenv("ENABLE_API_FOOTBALL_PLAYER_SYNC", "").lower() in {"1", "true", "yes"}
    if not enabled:
        return None, "api_football_disabled"

    try:
        from backend.sync.fallback import FootballAPIClient
        client = FootballAPIClient()
        result, api = client.get_player(name)
        return result, api
    except Exception as exc:
        logger.warning("API-Football error for '%s': %s", name, exc)
        return None, "api_football_error"


def _merge_facts(tm: Optional[dict], fbref: Optional[dict], api: Optional[dict]) -> Optional[dict]:
    """
    Merge facts from all sources. Transfermarkt is authoritative for
    club, value, status. FBref adds stats. API-Football adds WC data.
    """
    merged = {}

    # First source wins. Transfermarkt is authoritative for core player facts.
    for source in [tm, api, fbref]:
        if not source:
            continue
        for field in ["name", "current_club", "age", "nationality", "status", "position"]:
            if source.get(field) and not merged.get(field):
                merged[field] = source[field]

    # Market value only from Transfermarkt
    if tm and tm.get("market_value_eur"):
        merged["market_value_eur"] = tm["market_value_eur"]

    # WC stats only from API-Football when available
    if api:
        if api.get("world_cup_appearances") is not None:
            merged["world_cup_appearances"] = api["world_cup_appearances"]
        if api.get("world_cup_goals") is not None:
            merged["world_cup_goals"] = api["world_cup_goals"]

    return merged if merged else None


async def sync_players() -> dict:
    """
    Pull all players from Supabase, fetch live facts from Transfermarkt + FBref,
    update Supabase and Notion. Returns run summary.
    """
    logger.info("Starting player sync (Transfermarkt + FBref)...")
    await init_db()
    factory = get_session_factory()

    updated = 0
    errors = 0
    source_counts: dict[str, int] = {}

    async with factory() as session:
        result = await session.execute(select(Player).order_by(Player.name))
        players = result.scalars().all()

        for player in players:
            name = player.name
            try:
                tm_facts, tm_src = _fetch_from_transfermarkt(name)
                fbref_facts, fb_src = (None, "fbref_skipped")
                if _should_fetch_fbref(tm_facts):
                    fbref_facts, fb_src = _fetch_from_fbref(name)
                api_facts, api_src = _fetch_from_api_football(name)

                # Track which sources returned data
                if tm_facts:
                    source_counts["transfermarkt"] = source_counts.get("transfermarkt", 0) + 1
                if fbref_facts:
                    source_counts["fbref"] = source_counts.get("fbref", 0) + 1
                if api_facts:
                    source_counts[api_src] = source_counts.get(api_src, 0) + 1

                facts = _merge_facts(tm_facts, fbref_facts, api_facts)

                if facts is None:
                    logger.warning("No data from any source for player: %s", name)
                    errors += 1
                    continue

                # Determine primary source for logging
                primary = "transfermarkt" if tm_facts else ("fbref" if fbref_facts else api_src)

                # Update Supabase -- only owned factual fields
                if facts.get("current_club") is not None:
                    player.current_club = facts["current_club"]
                if facts.get("age") is not None:
                    player.age = facts["age"]
                if facts.get("status") is not None:
                    player.status = facts["status"]
                if facts.get("world_cup_appearances") is not None:
                    player.world_cup_appearances = facts["world_cup_appearances"]
                if facts.get("world_cup_goals") is not None:
                    player.world_cup_goals = facts["world_cup_goals"]
                if facts.get("nationality") is not None:
                    player.nationality = facts["nationality"]
                if facts.get("position") is not None and not player.position:
                    player.position = facts["position"]
                player.updated_at = datetime.utcnow()
                await session.flush()

                # Update Notion (secondary -- failure does not block Supabase)
                notion_page_id = _query_notion_player(name)
                if notion_page_id:
                    ok = _update_notion_player(notion_page_id, facts)
                    if not ok:
                        logger.warning("Notion update failed for player: %s", name)
                else:
                    logger.debug("Player '%s' not in Notion -- Supabase only", name)

                logger.info("Updated player: %s (via %s)", name, primary)
                updated += 1

            except Exception as exc:
                logger.error("Player sync failed for '%s': %s", name, exc)
                errors += 1

        await session.commit()

    notes = f"Sources: {source_counts}"
    dominant = max(source_counts, key=source_counts.get) if source_counts else "none"

    await log_sync_run(
        sync_type="player_sync",
        api_used=dominant,
        records_updated=updated,
        errors=errors,
        notes=notes,
    )

    logger.info("Player sync complete: %d updated, %d errors | %s", updated, errors, source_counts)
    return {"updated": updated, "errors": errors, "sources": source_counts}


if __name__ == "__main__":
    asyncio.run(sync_players())
