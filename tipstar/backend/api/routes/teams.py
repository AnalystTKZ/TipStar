from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db, get_all_teams, get_team_by_id, upsert_team, delete_team
from backend.sync.team_sync import sync_teams

router = APIRouter(prefix="/teams", tags=["teams"])


class TeamBody(BaseModel):
    name: str
    country: Optional[str] = None
    league: Optional[str] = None
    manager: Optional[str] = None
    world_cup_group: Optional[str] = None
    world_cup_status: Optional[str] = "TBC"
    playing_style: Optional[str] = None
    priority: Optional[str] = None
    notes: Optional[str] = None


class ScrapeTeamBody(BaseModel):
    name: str
    priority: Optional[str] = None
    notes: Optional[str] = None


def _team_embedding(data: dict) -> list[float] | None:
    try:
        from backend.embeddings.miniLM import encode
        text = f"{data.get('name', '')} {data.get('league', '')} {data.get('playing_style', '')}"
        return encode(text)
    except Exception:
        return None


@router.get("")
async def list_teams(db: AsyncSession = Depends(get_db)):
    return await get_all_teams(db)


@router.post("/sync")
async def sync_all_teams():
    import asyncio
    asyncio.create_task(sync_teams())
    return {"status": "started", "message": "Team sync running in background — check back in ~1 minute."}


@router.post("/import-from-notion")
async def import_teams_from_notion(db: AsyncSession = Depends(get_db)):
    from backend.harvester.notion_harvester import fetch_teams
    teams = fetch_teams()
    if not teams:
        return {"imported": 0, "message": "No teams returned from Notion"}

    imported = 0
    errors = 0
    for t in teams:
        try:
            data = {k: v for k, v in t.items() if k != "_notion_page_id" and v is not None}
            embedding = _team_embedding(data)
            if embedding:
                data["embedding"] = embedding
            await upsert_team(db, data)
            imported += 1
        except Exception as exc:
            errors += 1
    await db.commit()
    return {"imported": imported, "errors": errors, "total_from_notion": len(teams)}


@router.post("/scrape", status_code=201)
async def scrape_team_profile(body: ScrapeTeamBody, db: AsyncSession = Depends(get_db)):
    from backend.sync.transfermarkt import get_club

    facts = get_club(body.name)
    if not facts:
        raise HTTPException(status_code=404, detail="Club profile not found")

    data = {
        "name": facts.get("name") or body.name,
        "country": facts.get("country"),
        "league": facts.get("league"),
        "manager": facts.get("manager"),
        "world_cup_status": "TBC",
        "notes": facts.get("notes"),
    }
    if body.priority:
        data["priority"] = body.priority
    if body.notes:
        data["notes"] = body.notes

    embedding = _team_embedding(data)
    if embedding:
        data["embedding"] = embedding

    team = await upsert_team(db, data)
    await db.commit()
    return team.to_dict()


@router.get("/{team_id}")
async def get_team(team_id: str, db: AsyncSession = Depends(get_db)):
    team = await get_team_by_id(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.post("", status_code=201)
async def create_team(body: TeamBody, db: AsyncSession = Depends(get_db)):
    data = body.model_dump()
    embedding = _team_embedding(data)
    if embedding:
        data["embedding"] = embedding
    team = await upsert_team(db, data)
    await db.commit()
    return team.to_dict()


@router.delete("/{team_id}", status_code=200)
async def remove_team(team_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await delete_team(db, team_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Team not found")
    await db.commit()
    return {"deleted": team_id}


@router.patch("/{team_id}")
async def update_team(team_id: str, body: TeamBody, db: AsyncSession = Depends(get_db)):
    from backend.database.models import Team
    row = await db.get(Team, team_id)
    if not row:
        raise HTTPException(status_code=404, detail="Team not found")

    data = {k: v for k, v in body.model_dump().items() if v is not None}
    data["name"] = data.get("name") or row.name
    embedding = _team_embedding(data)
    if embedding:
        data["embedding"] = embedding
    team = await upsert_team(db, data)
    await db.commit()
    return team.to_dict()
