from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db, get_news_page, get_news_by_id
from backend.embeddings.similarity import search_similar_news
from backend.embeddings.miniLM import encode

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
