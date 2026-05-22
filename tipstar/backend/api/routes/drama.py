from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db, get_all_drama, get_drama_by_id, insert_drama

router = APIRouter(prefix="/drama", tags=["drama"])


class DramaBody(BaseModel):
    title: str
    players_involved: Optional[str] = None
    teams_involved: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    summary: Optional[str] = None
    status: Optional[str] = "Ongoing"
    source: Optional[str] = None
    drama_date: Optional[str] = None


@router.get("")
async def list_drama(db: AsyncSession = Depends(get_db)):
    return await get_all_drama(db)


@router.get("/{drama_id}")
async def get_drama(drama_id: str, db: AsyncSession = Depends(get_db)):
    entry = await get_drama_by_id(db, drama_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Drama entry not found")
    return entry


@router.post("", status_code=201)
async def create_drama(body: DramaBody, db: AsyncSession = Depends(get_db)):
    entry = await insert_drama(db, body.model_dump())
    await db.commit()
    return entry.to_dict()
