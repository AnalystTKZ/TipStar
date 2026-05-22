"""
Notion integration routes.

- GET  /notion/databases          -- list all discovered Notion DBs
- POST /notion/registry/reload    -- force re-discovery of databases
- GET  /notion/calendar           -- read Content Calendar entries
- POST /notion/calendar           -- add an entry to Content Calendar
- PATCH /notion/calendar/{page_id} -- update status / engagement score
- POST /notion/import             -- import all Notion DBs into Supabase
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/notion", tags=["notion"])


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@router.get("/databases")
async def list_notion_databases():
    """Return all Notion databases discovered for this workspace."""
    from backend.harvester.notion_registry import list_databases, reload
    dbs = list_databases()
    if not dbs:
        dbs = reload()
    return {"databases": dbs, "count": len(dbs)}


@router.post("/registry/reload")
async def reload_notion_registry():
    """Force re-discovery of Notion databases (clears cache)."""
    from backend.harvester.notion_registry import reload
    dbs = reload()
    return {"reloaded": True, "databases": dbs, "count": len(dbs)}


# ---------------------------------------------------------------------------
# Content Calendar
# ---------------------------------------------------------------------------

class CalendarEntryBody(BaseModel):
    post_idea: str
    platform: Optional[str] = "X Post"
    content_type: Optional[str] = None
    priority: Optional[str] = "Medium"
    target_date: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = "Idea"
    related_player_urls: Optional[list[str]] = None
    related_team_urls: Optional[list[str]] = None


class CalendarStatusBody(BaseModel):
    status: str
    engagement_score: Optional[int] = None


@router.get("/calendar")
async def get_calendar(status: Optional[str] = None):
    """
    Read Content Calendar from Notion.
    Optional ?status= filter: Idea | In Progress | Scheduled | Posted | Rejected
    """
    from backend.harvester.notion_harvester import fetch_content_calendar
    entries = fetch_content_calendar(status_filter=status)
    return {"entries": entries, "count": len(entries)}


@router.post("/calendar", status_code=201)
async def add_calendar_entry(body: CalendarEntryBody):
    """Add a post idea to the Notion Content Calendar."""
    from backend.harvester.notion_harvester import insert_content_calendar_entry
    page_id = insert_content_calendar_entry(body.model_dump())
    if not page_id:
        raise HTTPException(status_code=503, detail="Failed to write to Notion Content Calendar")
    return {"page_id": page_id, "post_idea": body.post_idea}


@router.patch("/calendar/{page_id}")
async def update_calendar_entry(page_id: str, body: CalendarStatusBody):
    """Update the status (and optionally engagement score) of a calendar entry."""
    from backend.harvester.notion_harvester import update_content_calendar_status
    ok = update_content_calendar_status(page_id, body.status, body.engagement_score)
    if not ok:
        raise HTTPException(status_code=503, detail="Failed to update Notion page")
    return {"updated": True, "page_id": page_id, "status": body.status}


# ---------------------------------------------------------------------------
# Bulk import
# ---------------------------------------------------------------------------

@router.post("/import")
async def import_all_from_notion():
    """
    Import all Notion databases (players, teams, drama, tournaments) into Supabase.
    Idempotent -- safe to run multiple times.
    Each row uses a savepoint so one bad row never aborts the whole transaction.
    """
    from backend.database.db import get_session_factory
    from backend.harvester.notion_sync import sync_notion_knowledge

    factory = get_session_factory()
    async with factory() as session:
        return await sync_notion_knowledge(session, with_embeddings=True)
