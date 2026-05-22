"""
Team sync: refreshes club facts for existing Supabase teams.

Transfermarkt is the primary source for club profile facts. The sync updates
only factual club fields and leaves editorial fields alone unless empty.
"""
import asyncio
import logging
from datetime import datetime

from sqlalchemy import select

from backend.database.db import get_session_factory, init_db
from backend.database.models import Team
from backend.sync.sync_logger import log_sync_run

logger = logging.getLogger(__name__)


def fetch_team_profile(name: str) -> dict | None:
    try:
        from backend.sync.transfermarkt import get_club
        return get_club(name)
    except Exception as exc:
        logger.warning("Transfermarkt club error for '%s': %s", name, exc)
        return None


async def sync_teams() -> dict:
    """
    Refresh all existing teams in Supabase from Transfermarkt.
    Returns a run summary.
    """
    logger.info("Starting team sync (Transfermarkt)...")
    await init_db()
    factory = get_session_factory()

    updated = 0
    errors = 0

    async with factory() as session:
        result = await session.execute(select(Team).order_by(Team.name))
        teams = result.scalars().all()

        for team in teams:
            try:
                facts = fetch_team_profile(team.name)
                if not facts:
                    logger.warning("No Transfermarkt data for team: %s", team.name)
                    errors += 1
                    continue

                if facts.get("country"):
                    team.country = facts["country"]
                if facts.get("league"):
                    team.league = facts["league"]
                if facts.get("manager"):
                    team.manager = facts["manager"]
                if facts.get("notes") and not team.notes:
                    team.notes = facts["notes"]
                team.updated_at = datetime.utcnow()
                await session.flush()
                updated += 1

            except Exception as exc:
                logger.error("Team sync failed for '%s': %s", team.name, exc)
                errors += 1

        await session.commit()

    await log_sync_run(
        sync_type="team_sync",
        api_used="transfermarkt",
        records_updated=updated,
        errors=errors,
        notes="Club profiles refreshed from Transfermarkt",
    )

    logger.info("Team sync complete: %d updated, %d errors", updated, errors)
    return {"updated": updated, "errors": errors, "sources": {"transfermarkt": updated}}


if __name__ == "__main__":
    asyncio.run(sync_teams())
