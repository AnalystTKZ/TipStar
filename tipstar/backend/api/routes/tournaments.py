import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db, get_all_tournaments, upsert_tournament, delete_tournament

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


@router.get("")
async def list_tournaments(db: AsyncSession = Depends(get_db)):
    return await get_all_tournaments(db)


@router.post("/import-from-notion")
async def import_tournaments_from_notion(db: AsyncSession = Depends(get_db)):
    from backend.harvester.notion_harvester import fetch_tournaments
    tournaments = fetch_tournaments()
    if not tournaments:
        return {"imported": 0, "message": "No tournaments returned from Notion"}
    imported = 0
    errors = 0
    for t in tournaments:
        try:
            data = {k: v for k, v in t.items() if k != "_notion_page_id" and v is not None}
            await upsert_tournament(db, data)
            imported += 1
        except Exception:
            errors += 1
    await db.commit()
    return {"imported": imported, "errors": errors, "total_from_notion": len(tournaments)}


@router.post("/sync")
async def sync_all_tournaments():
    from backend.sync.tournament_sync import sync_tournaments
    asyncio.create_task(sync_tournaments())
    return {"status": "started", "message": "Tournament sync running in background — check back in ~30 seconds."}


@router.delete("/{tournament_id}", status_code=200)
async def remove_tournament(tournament_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await delete_tournament(db, tournament_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tournament not found")
    await db.commit()
    return {"deleted": tournament_id}
