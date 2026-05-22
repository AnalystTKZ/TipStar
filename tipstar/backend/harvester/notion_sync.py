"""
Shared Notion -> Supabase sync.

Notion remains the editorial source of truth. Supabase is the fast operational
store used by the AI agent for semantic lookup and prompt context. This module
keeps those two layers aligned before imports and generation runs.
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import upsert_drama, upsert_player, upsert_team, upsert_tournament
from backend.harvester.notion_harvester import (
    fetch_drama,
    fetch_players,
    fetch_teams,
    fetch_tournaments,
)

logger = logging.getLogger(__name__)


def _clean(row: dict) -> dict:
    return {k: v for k, v in row.items() if k != "_notion_page_id" and v is not None}


async def sync_notion_knowledge(session: AsyncSession, with_embeddings: bool = True) -> dict:
    """
    Pull Notion editorial data into Supabase.

    Returns per-resource counts and errors. Each row is isolated with a
    savepoint so one malformed Notion row cannot poison the whole transaction.
    """
    if with_embeddings:
        from backend.embeddings.miniLM import encode
    else:
        encode = None

    results: dict[str, dict[str, int]] = {}

    async def sync_rows(resource: str, rows: list[dict], fn, embed_text):
        imported = errors = 0
        for row in rows:
            data = _clean(row)
            if encode and embed_text:
                data["embedding"] = encode(embed_text(data))
            try:
                async with session.begin_nested():
                    await fn(session, data)
                imported += 1
            except Exception as exc:
                logger.warning("Notion sync skipped %s row %r: %s", resource, data.get("name") or data.get("title"), exc)
                errors += 1
        results[resource] = {"imported": imported, "errors": errors}

    await sync_rows(
        "players",
        fetch_players(),
        upsert_player,
        lambda p: f"{p.get('name', '')} {p.get('current_club', '')} {p.get('position', '')} "
                  f"{p.get('tier', '')} {p.get('content_angle', '')} {p.get('notes', '')}",
    )
    await sync_rows(
        "teams",
        fetch_teams(),
        upsert_team,
        lambda t: f"{t.get('name', '')} {t.get('league', '')} {t.get('playing_style', '')} "
                  f"{t.get('priority', '')} {t.get('notes', '')}",
    )
    await sync_rows(
        "drama",
        fetch_drama(),
        upsert_drama,
        lambda d: f"{d.get('title', '')} {d.get('summary', '')} {d.get('players_involved', '')} "
                  f"{d.get('teams_involved', '')}",
    )
    await sync_rows(
        "tournaments",
        fetch_tournaments(),
        upsert_tournament,
        None,
    )

    await session.commit()
    return results
