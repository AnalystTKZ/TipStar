from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db, get_all_matches, get_match_by_id, insert_match

router = APIRouter(prefix="/matches", tags=["matches"])


class MatchBody(BaseModel):
    home_team: str
    away_team: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    stage: Optional[str] = None
    tournament: Optional[str] = None
    venue: Optional[str] = None
    match_date: Optional[str] = None
    scorers: Optional[str] = None
    key_events: Optional[str] = None
    coverage_status: Optional[str] = "Not Covered"


@router.get("")
async def list_matches(db: AsyncSession = Depends(get_db)):
    return await get_all_matches(db)


@router.get("/{match_id}")
async def get_match(match_id: str, db: AsyncSession = Depends(get_db)):
    match = await get_match_by_id(db, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


@router.post("", status_code=201)
async def create_match(body: MatchBody, db: AsyncSession = Depends(get_db)):
    match = await insert_match(db, body.model_dump())
    await db.commit()
    return match.to_dict()
