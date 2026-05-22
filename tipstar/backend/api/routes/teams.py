from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db, get_all_teams, get_team_by_id, upsert_team
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
    return await sync_teams()


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
