from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import (
    get_db,
    get_analytics_summary,
    get_post_type_breakdown,
    get_posts_over_time,
    get_coverage_ratio,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary")
async def analytics_summary(db: AsyncSession = Depends(get_db)):
    return await get_analytics_summary(db)


@router.get("/posts")
async def posts_over_time(db: AsyncSession = Depends(get_db)):
    return await get_posts_over_time(db)


@router.get("/coverage")
async def coverage_ratio(db: AsyncSession = Depends(get_db)):
    return await get_coverage_ratio(db)


@router.get("/types")
async def post_type_breakdown(db: AsyncSession = Depends(get_db)):
    return await get_post_type_breakdown(db)


@router.get("/players")
async def top_players(db: AsyncSession = Depends(get_db)):
    """Most mentioned players derived from post story titles."""
    from sqlalchemy import select, func, text
    from backend.database.models import Post, Player, PostStatus

    session = db
    result = await session.execute(
        select(Player.name, func.count(Post.id).label("mentions"))
        .join(Post, Post.story_title.ilike("%" + Player.name + "%"), isouter=True)
        .where(Post.status.in_([PostStatus.approved, PostStatus.posted]))
        .group_by(Player.name)
        .order_by(func.count(Post.id).desc())
        .limit(10)
    )
    return [{"player": row[0], "mentions": row[1]} for row in result.all()]
