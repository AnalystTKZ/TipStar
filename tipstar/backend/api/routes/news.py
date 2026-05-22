import logging

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db, get_news_page, get_news_by_id, insert_news
from backend.embeddings.similarity import search_similar_news
from backend.embeddings.miniLM import encode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/news", tags=["news"])


@router.get("")
async def news_feed(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await get_news_page(db, page=page, size=size)


@router.get("/{news_id}")
async def news_detail(news_id: str, db: AsyncSession = Depends(get_db)):
    item = await get_news_by_id(db, news_id)
    if not item:
        raise HTTPException(status_code=404, detail="News item not found")

    # Attach similar stories if the item has an embedding
    from backend.database.models import News
    from sqlalchemy import select
    row = await db.get(News, news_id)
    similar = []
    if row and row.embedding:
        import json
        try:
            emb = json.loads(row.embedding)
            similar = await search_similar_news(db, emb, top_k=5, exclude_id=news_id)
        except Exception:
            pass

    return {**item, "similar_stories": similar}


@router.post("/harvest")
async def harvest_news(db: AsyncSession = Depends(get_db)):
    """
    Manually trigger the news harvester: fetch from NewsAPI + RSS,
    deduplicate, and store fresh stories in the database.
    """
    from backend.harvester.harvest import harvest_all

    stories = harvest_all()
    inserted = 0
    skipped = 0
    for story in stories:
        result = await insert_news(db, story)
        if result:
            inserted += 1
        else:
            skipped += 1

    await db.commit()
    logger.info("Manual harvest: %d inserted, %d skipped duplicates", inserted, skipped)
    return {"inserted": inserted, "skipped": skipped, "total_fetched": len(stories)}
