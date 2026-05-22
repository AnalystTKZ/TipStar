from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db, get_all_players, get_player_by_id, upsert_player
from backend.sync.player_sync import sync_players

router = APIRouter(prefix="/players", tags=["players"])


class PlayerBody(BaseModel):
    name: str
    nationality: Optional[str] = None
    current_club: Optional[str] = None
    position: Optional[str] = None
    tier: Optional[str] = None
    age: Optional[int] = None
    world_cup_appearances: Optional[int] = 0
    world_cup_goals: Optional[int] = 0
    status: Optional[str] = "Active"
    notes: Optional[str] = None


class ScrapePlayerBody(BaseModel):
    name: str
    tier: Optional[str] = None
    notes: Optional[str] = None


def _player_embedding(data: dict) -> list[float] | None:
    try:
        from backend.embeddings.miniLM import encode
        text = f"{data.get('name', '')} {data.get('current_club', '')} {data.get('position', '')}"
        return encode(text)
    except Exception:
        return None


@router.get("")
async def list_players(db: AsyncSession = Depends(get_db)):
    return await get_all_players(db)


@router.post("/sync")
async def sync_all_players():
    return await sync_players()


@router.post("/scrape", status_code=201)
async def scrape_player_profile(body: ScrapePlayerBody, db: AsyncSession = Depends(get_db)):
    from backend.sync.transfermarkt import get_player as scrape_transfermarkt_player

    facts = scrape_transfermarkt_player(body.name)
    if not facts:
        raise HTTPException(status_code=404, detail="Player profile not found")

    data = {
        "name": facts.get("name") or body.name,
        "nationality": facts.get("nationality"),
        "current_club": facts.get("current_club"),
        "position": facts.get("position"),
        "age": facts.get("age"),
        "status": facts.get("status") or "Active",
        "world_cup_appearances": 0,
        "world_cup_goals": 0,
    }
    if body.tier:
        data["tier"] = body.tier
    if body.notes:
        data["notes"] = body.notes

    embedding = _player_embedding(data)
    if embedding:
        data["embedding"] = embedding

    player = await upsert_player(db, data)
    await db.commit()
    return player.to_dict()


@router.get("/{player_id}")
async def get_player(player_id: str, db: AsyncSession = Depends(get_db)):
    player = await get_player_by_id(db, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player


@router.post("", status_code=201)
async def create_player(body: PlayerBody, db: AsyncSession = Depends(get_db)):
    player = await upsert_player(db, body.model_dump())
    await db.commit()
    return player.to_dict()


@router.patch("/{player_id}")
async def update_player(player_id: str, body: PlayerBody, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from backend.database.models import Player
    row = await db.get(Player, player_id)
    if not row:
        raise HTTPException(status_code=404, detail="Player not found")
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    player = await upsert_player(db, data)
    await db.commit()
    return player.to_dict()
