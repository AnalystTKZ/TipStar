import asyncio
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import (
    get_db,
    get_posts,
    get_posts_by_status,
    get_post_history,
    update_post_status,
    delete_post,
    get_news_page,
    insert_posts,
    set_post_image_path,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/posts", tags=["posts"])
_generation_jobs: dict[str, dict] = {}


class EditBody(BaseModel):
    content: str


def _set_job(job_id: str, **updates) -> None:
    job = _generation_jobs.setdefault(job_id, {})
    job.update(updates)
    job["updated_at"] = time.time()


def _new_generation_job(limit: int, min_score: int) -> str:
    # Keep the in-memory registry bounded during dev sessions.
    if len(_generation_jobs) > 25:
        oldest = sorted(_generation_jobs, key=lambda jid: _generation_jobs[jid].get("updated_at", 0))[:10]
        for jid in oldest:
            _generation_jobs.pop(jid, None)

    job_id = uuid.uuid4().hex
    now = time.time()
    _generation_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "phase": "queued",
        "message": "Queued generation job.",
        "limit": limit,
        "min_score": min_score,
        "total": 0,
        "processed": 0,
        "generated_posts": 0,
        "generated_stories": 0,
        "skipped": 0,
        "errors": 0,
        "current_story": None,
        "last_story": None,
        "created_at": now,
        "updated_at": now,
    }
    return job_id


@router.get("/pending")
async def pending_posts(db: AsyncSession = Depends(get_db)):
    return await get_posts_by_status(db, "pending")


@router.get("/approved")
async def approved_posts(db: AsyncSession = Depends(get_db)):
    return await get_posts_by_status(db, "approved")


@router.get("/history")
async def post_history(db: AsyncSession = Depends(get_db)):
    return await get_post_history(db)


@router.get("")
async def all_posts(status: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    if status and status not in {"pending", "approved", "rejected", "posted"}:
        raise HTTPException(status_code=400, detail="Invalid status")
    return await get_posts(db, status=status)


async def _render_visual_for_post(db: AsyncSession, post: dict) -> dict:
    """Render the post image and persist its path. Approval should still work if rendering fails."""
    try:
        from backend.visuals.post_renderer import render_post_visual
        image_path = await asyncio.to_thread(render_post_visual, post)
        updated = await set_post_image_path(db, post["id"], image_path)
        return updated or {**post, "image_path": image_path, "image_url": f"/{image_path}"}
    except Exception as exc:
        logger.warning("Could not render image preview for post %s: %s", post.get("id"), exc)
        return post


@router.patch("/{post_id}/approve")
async def approve_post(post_id: str, db: AsyncSession = Depends(get_db)):
    result = await update_post_status(db, post_id, "approved")
    if not result:
        raise HTTPException(status_code=404, detail="Post not found")
    result = await _render_visual_for_post(db, result)
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
    result = await _render_visual_for_post(db, result)
    await db.commit()
    return result


@router.delete("/{post_id}")
async def remove_post(post_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await delete_post(db, post_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Post not found")
    await db.commit()
    return {"deleted": post_id}


async def _run_generate(job_id: str, limit: int, min_score: int):
    """Background task: process recent unprocessed news through the LLM."""
    from backend.config.settings import FACT_EXTRACTION_ENABLED
    from backend.database.db import get_session_factory, insert_posts, set_news_embedding
    from backend.embeddings.enricher import enrich_story
    from backend.generator.groq_generator import generate_posts
    from backend.harvester.fact_extractor import extract_and_store_facts
    from backend.harvester.notion_harvester import fetch_config, write_back_from_story
    from backend.harvester.notion_sync import sync_notion_knowledge
    from sqlalchemy import text

    factory = get_session_factory()
    generated_count = 0
    generated_stories = 0
    skipped_count = 0

    _set_job(job_id, status="running", phase="context", message="Loading editorial notes and Notion context.")

    # Pull editorial notes from Notion once per run (not per story)
    editorial_notes = ""
    try:
        config = fetch_config()
        editorial_notes = config.get("editorial_notes", "")
    except Exception as exc:
        logger.warning("Could not fetch Notion editorial config: %s", exc)

    async with factory() as session:
        try:
            _set_job(job_id, phase="notion_sync", message="Refreshing Notion and database context.")
            sync_results = await sync_notion_knowledge(session, with_embeddings=True)
            logger.info("Refreshed Notion knowledge before generation: %s", sync_results)
        except Exception as exc:
            await session.rollback()
            logger.warning("Notion knowledge refresh failed; continuing with existing DB context: %s", exc)

        # Fetch recent news that hasn't had posts generated yet
        _set_job(job_id, phase="loading_news", message="Finding recent news without generated posts.")
        result = await session.execute(
            text("""
                SELECT n.id, n.title, n.content, n.source, n.source_confidence, n.url, n.published_at
                FROM news n
                LEFT JOIN posts p ON p.news_id = n.id
                WHERE p.id IS NULL
                ORDER BY n.created_at DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )
        rows = result.mappings().all()
        _set_job(
            job_id,
            total=len(rows),
            phase="generating" if rows else "complete",
            message=f"Found {len(rows)} eligible stories." if rows else "No eligible unprocessed news found.",
        )

        for index, row in enumerate(rows, start=1):
            news_item = {
                "id": str(row["id"]),
                "title": row["title"] or "",
                "description": row["content"] or "",
                "source": row["source"] or "",
                "source_confidence": row["source_confidence"] or "trusted_news",
                "url": row["url"],
                "published_at": row["published_at"].isoformat() if row["published_at"] else "",
            }
            title = news_item["title"]
            _set_job(
                job_id,
                phase="generating",
                current_story=title,
                message=f"Generating story {index}/{len(rows)}: {title[:90]}",
            )
            try:
                context = await enrich_story(session, news_item, editorial_notes=editorial_notes)
                if context.get("embedding"):
                    await set_news_embedding(session, str(row["id"]), context["embedding"])
                generated = await asyncio.to_thread(generate_posts, news_item, context)
                if generated is None or generated.get("relevance_score", 0) < min_score:
                    skipped_count += 1
                    _set_job(job_id, skipped=skipped_count, last_story=title, message=f"Skipped story {index}/{len(rows)}.")
                    continue
                if FACT_EXTRACTION_ENABLED:
                    await extract_and_store_facts(session, news_item, str(row["id"]))
                count = await insert_posts(session, generated, news_id=row["id"])
                await session.commit()
                generated_count += count
                generated_stories += 1
                logger.info("Generated %d posts for: %s (score %s)", count, news_item["title"], generated.get("relevance_score"))
                _set_job(
                    job_id,
                    generated_posts=generated_count,
                    generated_stories=generated_stories,
                    last_story=title,
                    message=f"Generated {count} posts from story {index}/{len(rows)}.",
                )
                # Write detected players, drama, matches back to Notion
                await asyncio.to_thread(write_back_from_story, news_item, generated)
            except Exception as exc:
                await session.rollback()
                logger.error("Generate failed for '%s': %s", news_item.get("title"), exc)
                skipped_count += 1
                job = _generation_jobs.get(job_id, {})
                _set_job(
                    job_id,
                    errors=int(job.get("errors", 0)) + 1,
                    skipped=skipped_count,
                    last_story=title,
                    message=f"Error on story {index}/{len(rows)}. Continuing.",
                )
            finally:
                _set_job(job_id, processed=index, current_story=None)

    logger.info("Generation complete: %d posts created, %d stories skipped", generated_count, skipped_count)
    _set_job(
        job_id,
        status="complete",
        phase="complete",
        generated_posts=generated_count,
        generated_stories=generated_stories,
        skipped=skipped_count,
        current_story=None,
        message=f"Generation complete: {generated_count} posts from {generated_stories} stories, {skipped_count} skipped.",
    )


@router.post("/generate")
async def generate_from_news(limit: int = 20, min_score: int = 5):
    """
    Run recent unprocessed news through Groq and push to approval queue.
    Fire-and-forget - returns immediately, generation runs in background.
    """
    job_id = _new_generation_job(limit=limit, min_score=min_score)
    task = asyncio.create_task(_run_generate(job_id=job_id, limit=limit, min_score=min_score))

    def _mark_failed(done_task: asyncio.Task) -> None:
        exc = done_task.exception()
        if exc:
            logger.exception("Generation job %s failed", job_id, exc_info=exc)
            _set_job(job_id, status="failed", phase="failed", current_story=None, message=str(exc))

    task.add_done_callback(_mark_failed)
    return {
        "job_id": job_id,
        "status": "started",
        "message": f"Generating posts from up to {limit} recent news items (min score {min_score}). Check the Approval Inbox in ~30 seconds.",
    }


@router.get("/generate/status/{job_id}")
async def generation_status(job_id: str):
    job = _generation_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found")
    return job


@router.post("/publish")
async def publish_approved():
    """
    Post all approved (unposted) posts to X.
    Returns counts of successes and failures.
    """
    from backend.scheduler.publisher import run_publish_pipeline
    try:
        await run_publish_pipeline()
        return {"status": "ok", "message": "Publish pipeline complete - check logs for details."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
