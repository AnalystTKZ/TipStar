"""
Match sync: pulls fixtures and results for all tracked competitions,
upserts to Supabase matches table, and syncs World Cup 2026 matches to Notion.

Notion Coverage Status rules:
- New matches: set to "Not Covered"
- Never change if already "Covered" or "Scheduled" -- editorial decisions
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests
from sqlalchemy import select, text

from backend.database.db import get_session_factory, init_db
from backend.database.models import Match
from backend.sync.fallback import FootballAPIClient
from backend.sync.sync_logger import log_sync_run

logger = logging.getLogger(__name__)

_NOTION_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"

TRACKED_COMPETITIONS = [
    "FIFA World Cup 2026",
    "UEFA Champions League",
    "Premier League",
    "La Liga",
    "Bundesliga",
    "Serie A",
    "Ligue 1",
]

_EDITORIAL_COVERAGE_STATUSES = {"Covered", "Scheduled"}

_client = FootballAPIClient()


def _notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('NOTION_API_KEY', '')}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _query_notion_match(title: str) -> Optional[dict]:
    """
    Query Notion World Cup 2026 database for a match by title (Team A vs Team B).
    Returns {"page_id": str, "coverage_status": str} or None.
    """
    db_id = os.getenv("NOTION_MATCHES_DB_ID", "")
    if not db_id:
        return None
    try:
        resp = requests.post(
            f"{_NOTION_BASE}/databases/{db_id}/query",
            json={"filter": {"property": "Match", "title": {"equals": title}}},
            headers=_notion_headers(),
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        results = resp.json().get("results", [])
        if not results:
            return None
        page = results[0]
        coverage = (
            page.get("properties", {})
            .get("Coverage Status", {})
            .get("select", {}) or {}
        ).get("name", "")
        return {"page_id": page["id"], "coverage_status": coverage}
    except Exception as exc:
        logger.warning("Notion match query error for '%s': %s", title, exc)
        return None


def _upsert_notion_match(match: dict) -> bool:
    """
    Create or update a World Cup match in Notion.
    Never overwrites Coverage Status if it is an editorial value.
    """
    db_id = os.getenv("NOTION_MATCHES_DB_ID", "")
    if not db_id:
        return False

    title = f"{match['home_team']} vs {match['away_team']}"
    existing = _query_notion_match(title)

    score = ""
    if match.get("home_score") is not None and match.get("away_score") is not None:
        score = f"{match['home_score']} - {match['away_score']}"

    props = {
        "Score": {"rich_text": [{"text": {"content": score}}]},
        "Stage": {"rich_text": [{"text": {"content": str(match.get("stage") or "")}}]},
        "Scorers": {"rich_text": [{"text": {"content": str(match.get("scorers") or "")}}]},
        "Key Events": {"rich_text": [{"text": {"content": str(match.get("key_events") or "")}}]},
    }

    if match.get("match_date"):
        try:
            dt = match["match_date"]
            if isinstance(dt, str):
                dt = dt.replace("Z", "+00:00")
                dt = datetime.fromisoformat(dt).date().isoformat()
            elif isinstance(dt, datetime):
                dt = dt.date().isoformat()
            props["Match Date"] = {"date": {"start": dt}}
        except Exception:
            pass

    try:
        if existing:
            # Never change editorial coverage statuses
            if existing["coverage_status"] not in _EDITORIAL_COVERAGE_STATUSES:
                props["Coverage Status"] = {"select": {"name": "Not Covered"}}

            resp = requests.patch(
                f"{_NOTION_BASE}/pages/{existing['page_id']}",
                json={"properties": props},
                headers=_notion_headers(),
                timeout=15,
            )
        else:
            props["Match"] = {"title": [{"text": {"content": title}}]}
            props["Coverage Status"] = {"select": {"name": "Not Covered"}}
            resp = requests.post(
                f"{_NOTION_BASE}/pages",
                json={"parent": {"database_id": db_id}, "properties": props},
                headers=_notion_headers(),
                timeout=15,
            )

        if resp.status_code not in (200, 201):
            logger.warning("Notion match upsert failed for '%s': %s", title, resp.status_code)
            return False
        return True
    except Exception as exc:
        logger.warning("Notion match upsert error for '%s': %s", title, exc)
        return False


async def _upsert_match_supabase(session, match: dict) -> bool:
    """Upsert a match by api_fixture_id if present, else by team names + date."""
    try:
        existing = None
        fixture_id = match.get("api_fixture_id")

        if fixture_id:
            result = await session.execute(
                select(Match).where(
                    text("key_events::text LIKE :fid").bindparams(fid=f"%fixture:{fixture_id}%")
                )
            )
            existing = result.scalar_one_or_none()

        if not existing:
            result = await session.execute(
                select(Match).where(
                    Match.home_team == match.get("home_team"),
                    Match.away_team == match.get("away_team"),
                    Match.tournament == match.get("tournament"),
                )
            )
            existing = result.scalar_one_or_none()

        match_dt = match.get("match_date")
        if isinstance(match_dt, str):
            try:
                match_dt = datetime.fromisoformat(match_dt.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                match_dt = None

        key_events_str = match.get("key_events", "")
        if fixture_id:
            sep = "; " if key_events_str else ""
            key_events_str = f"fixture:{fixture_id}{sep}{key_events_str}"

        if existing:
            existing.home_score = match.get("home_score")
            existing.away_score = match.get("away_score")
            existing.stage = match.get("stage") or existing.stage
            existing.venue = match.get("venue") or existing.venue
            existing.match_date = match_dt or existing.match_date
            existing.scorers = match.get("scorers") or existing.scorers
            existing.key_events = key_events_str or existing.key_events
        else:
            row = Match(
                home_team=match.get("home_team"),
                away_team=match.get("away_team"),
                home_score=match.get("home_score"),
                away_score=match.get("away_score"),
                stage=match.get("stage"),
                tournament=match.get("tournament"),
                venue=match.get("venue"),
                match_date=match_dt,
                scorers=match.get("scorers", ""),
                key_events=key_events_str,
                coverage_status="Not Covered",
            )
            session.add(row)

        await session.flush()
        return True
    except Exception as exc:
        logger.error("Supabase match upsert error: %s", exc)
        return False


async def sync_matches(date_from: Optional[str] = None, date_to: Optional[str] = None) -> dict:
    """
    Sync matches for all tracked competitions over the given date range.
    Defaults to today +/- 3 days if not specified.
    """
    today = datetime.now(timezone.utc).date()
    date_from = date_from or (today - timedelta(days=1)).isoformat()
    date_to = date_to or (today + timedelta(days=3)).isoformat()

    logger.info("Starting match sync: %s to %s", date_from, date_to)
    factory = get_session_factory()

    total_updated = 0
    total_errors = 0
    api_used_counts: dict[str, int] = {}

    async with factory() as session:
        for competition in TRACKED_COMPETITIONS:
            try:
                matches, api_used = _client.get_matches(competition, date_from, date_to)
                api_used_counts[api_used] = api_used_counts.get(api_used, 0) + 1

                comp_updated = 0
                for match in matches:
                    ok = await _upsert_match_supabase(session, match)
                    if ok:
                        comp_updated += 1
                        # Sync World Cup matches to Notion
                        if competition == "FIFA World Cup 2026":
                            _upsert_notion_match(match)
                    else:
                        total_errors += 1

                await session.commit()
                logger.info(
                    "%s: %d matches synced (via %s)", competition, comp_updated, api_used
                )
                total_updated += comp_updated

            except Exception as exc:
                logger.error("Match sync error for %s: %s", competition, exc)
                total_errors += 1
                await session.rollback()

    dominant_api = max(api_used_counts, key=api_used_counts.get) if api_used_counts else "none"
    notes = f"Date range: {date_from} to {date_to} | API: {api_used_counts}"

    await log_sync_run(
        sync_type="match_sync",
        api_used=dominant_api,
        records_updated=total_updated,
        errors=total_errors,
        notes=notes,
    )

    logger.info("Match sync complete: %d matches, %d errors", total_updated, total_errors)
    return {"updated": total_updated, "errors": total_errors, "api_used": dominant_api}


async def _main():
    await init_db()
    await sync_matches()

if __name__ == "__main__":
    asyncio.run(_main())
