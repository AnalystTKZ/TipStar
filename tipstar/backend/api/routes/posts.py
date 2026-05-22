import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import (
    get_db,
    get_posts_by_status,
    get_post_history,
    update_post_status,
    delete_post,
    get_news_page,
    insert_posts,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/posts", tags=["posts"])


class EditBody(BaseModel):
    content: str


@router.get("/pending")
async def pending_posts(db: AsyncSession = Depends(get_db)):
    return await get_posts_by_status(db, "pending")


@router.get("/approved")
async def approved_posts(db: AsyncSession = Depends(get_db)):
    return await get_posts_by_status(db, "approved")


@router.get("/history")
async def post_history(db: AsyncSession = Depends(get_db)):
    return await get_post_history(db)


@router.patch("/{post_id}/approve")
async def approve_post(post_id: str, db: AsyncSession = Depends(get_db)):
    result = await update_post_status(db, post_id, "approved")
    if not result:
        raise HTTPException(status_code=404, detail="Post not found")
    await db.commit()
    return result


@router.patch("/{post_id}/reject")
async def reject_post(post_id: str, db: AsyncSession = Depends(get_db)):
    result = await update_post_status(db, post_id, "rejected")
    if not result:
        raise HTTPException(status_code=404, detail="Post not found")
    await db.commit()
    return result


@router.patch("/{post_id}/edit")
async def edit_and_approve(post_id: str, body: EditBody, db: AsyncSession = Depends(get_db)):
    """Edit post content and approve in one step."""
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty")
    result = await update_post_status(db, post_id, "approved", content=body.content)
    if not result:
        raise HTTPException(status_code=404, detail="Post not found")
    await db.commit()
    return result


@router.delete("/{post_id}")
async def remove_post(post_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await delete_post(db, post_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Post not found")
    await db.commit()
    return {"deleted": post_id}


async def _run_generate(limit: int, min_score: int):
    """Background task: process recent unprocessed news through Groq."""
    from backend.database.db import get_session_factory, get_news_page, insert_posts, insert_news
    from backend.embeddings.enricher import enrich_story
    from backend.generator.groq_generator import generate_posts
    from backend.harvester.notion_harvester import fetch_config, write_back_from_story
    from sqlalchemy import select, text

    factory = get_session_factory()
    generated_count = 0
    skipped_count = 0

    # Pull editorial notes from Notion once per run (not per story)
    editorial_notes = ""
    try:
        config = fetch_config()
        editorial_notes = config.get("editorial_notes", "")
    except Exception as exc:
        logger.warning("Could not fetch Notion editorial config: %s", exc)

    async with factory() as session:
        # Fetch recent news that hasn't had posts generated yet
        result = await session.execute(
            text("""
                SELECT n.id, n.title, n.content, n.source, n.url, n.published_at
                FROM news n
                LEFT JOIN posts p ON p.news_id = n.id
                WHERE p.id IS NULL
                ORDER BY n.created_at DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )
        rows = result.mappings().all()

        for row in rows:
            news_item = {
                "id": str(row["id"]),
                "title": row["title"] or "",
                "description": row["content"] or "",
                "source": row["source"] or "",
                "url": row["url"],
                "published_at": row["published_at"].isoformat() if row["published_at"] else "",
            }
            try:
                context = await enrich_story(session, news_item, editorial_notes=editorial_notes)
                generated = generate_posts(news_item, enriched_context=context)
                if generated is None or generated.get("relevance_score", 0) < min_score:
                    skipped_count += 1
                    continue
                count = await insert_posts(session, generated, news_id=row["id"])
                await session.commit()
                generated_count += count
                logger.info("Generated %d posts for: %s (score %s)", count, news_item["title"], generated.get("relevance_score"))
                # Write detected players, drama, matches back to Notion
                write_back_from_story(news_item, generated)
            except Exception as exc:
                await session.rollback()
                logger.error("Generate failed for '%s': %s", news_item.get("title"), exc)
                skipped_count += 1

    logger.info("Generation complete: %d posts created, %d stories skipped", generated_count, skipped_count)


@router.post("/generate")
async def generate_from_news(limit: int = 20, min_score: int = 5):
    """
    Run recent unprocessed news through Groq and push to approval queue.
    Fire-and-forget — returns immediately, generation runs in background.
    """
    asyncio.create_task(_run_generate(limit=limit, min_score=min_score))
    return {
        "status": "started",
        "message": f"Generating posts from up to {limit} recent news items (min score {min_score}). Check the Approval Inbox in ~30 seconds.",
    }


@router.post("/publish")
async def publish_approved():
    """
    Post all approved (unposted) posts to X.
    Returns counts of successes and failures.
    """
    from backend.scheduler.publisher import run_publish_pipeline
    try:
        await run_publish_pipeline()
        return {"status": "ok", "message": "Publish pipeline complete — check logs for details."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
