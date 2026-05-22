from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db, get_fact_claims

router = APIRouter(prefix="/facts", tags=["facts"])


@router.get("")
async def list_facts(
    status: str | None = Query(None, pattern="^(candidate|verified|conflicting|rejected)$"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    return await get_fact_claims(db, status=status, limit=limit)
