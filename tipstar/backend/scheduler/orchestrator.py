"""
Harvest -> Embed -> Enrich -> Generate -> Persist pipeline.
Runs every 30 minutes via GitHub Actions or cron.
"""
import asyncio
import logging
import os
import sys
from datetime import date, datetime, time as dt_time, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from backend.config.settings import FACT_EXTRACTION_ENABLED, MIN_RELEVANCE_SCORE
from backend.database.db import get_session_factory, init_db, insert_news, insert_posts, set_news_embedding
from backend.embeddings.enricher import enrich_story
from backend.generator.groq_generator import generate_posts
from backend.harvester.deduplicator import mark_seen
from backend.harvester.fact_extractor import extract_and_store_facts
from backend.harvester.harvest import harvest_all
from backend.harvester.notion_harvester import (
    fetch_config,
    write_back_from_story,
)
from backend.harvester.notion_sync import sync_notion_knowledge
from backend.sync.sync_logger import log_sync_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/tipstar.log"),
    ],
)
logger = logging.getLogger("orchestrator")


async def sync_notion(session):
    """Sync Notion knowledge base into Supabase."""
    logger.info("Syncing Notion knowledge base...")
    results = await sync_notion_knowledge(session, with_embeddings=True)
    logger.info("Notion sync complete: %s", results)


async def run_harvest_pipeline():
    """Main pipeline: harvest -> embed -> enrich -> generate -> persist."""
    logger.info("=== TipStar harvest pipeline starting ===")
    await init_db()

    factory = get_session_factory()
    async with factory() as session:
        # Sync Notion knowledge base first
        await sync_notion(session)

        # Load editorial config
        config = fetch_config()
        editorial_notes = config.get("editorial_notes", "")

        # Harvest fresh stories
        stories = harvest_all()
        if not stories:
            logger.info("No new stories. Pipeline complete.")
            return

        pushed = 0
        skipped = 0

        for story in stories:
            title = story.get("title", "untitled")
            try:
                # Insert news item and get its ID
                news_row = await insert_news(session, story)
                if news_row:
                    await session.flush()
                    news_id = news_row.id
                    story["id"] = str(news_id)
                else:
                    news_id = None

                # Enrich with semantic context
                context = await enrich_story(session, story, editorial_notes)
                if news_id and context.get("embedding"):
                    await set_news_embedding(session, str(news_id), context["embedding"])

                # Generate post variants via LLM
                generated = generate_posts(story, enriched_context=context)
                if generated is None:
                    logger.info(f"Skipped (low relevance): {title}")
                    mark_seen(story)
                    skipped += 1
                    continue

                if FACT_EXTRACTION_ENABLED:
                    await extract_and_store_facts(session, story, str(news_id) if news_id else None)

                # Persist posts
                count = await insert_posts(session, generated, news_id=news_id)
                await session.commit()
                mark_seen(story)
                logger.info(f"Score {generated.get('relevance_score')}/10 -- {count} posts: {title}")

                # Write new players, drama, and match results back to Notion
                write_back_from_story(story, generated)

                pushed += 1

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed for '{title}': {e}")
                skipped += 1

    logger.info(f"=== Pipeline complete: {pushed} stories, {skipped} skipped ===")


async def run_youtube_harvest(hours: int = 6) -> dict:
    """Harvest YouTube videos, extract transcripts, and store quote/opinion intelligence."""
    logger.info("=== TipStar YouTube intelligence harvest starting ===")
    await init_db()

    from backend.harvester.opinion_extractor import extract_opinions
    from backend.harvester.pressconf_extractor import extract_quotes
    from backend.harvester.transcript_extractor import get_transcript
    from backend.harvester.youtube_harvester import get_video_comments, run_harvester

    factory = get_session_factory()
    videos = await run_harvester(hours=hours)
    quotes_count = 0
    opinions_count = 0
    errors = 0

    async with factory() as session:
        for video in videos:
            try:
                transcript = get_transcript(video["video_id"])
                if not transcript:
                    errors += 1
                    continue

                comments = get_video_comments(video["video_id"])
                if video.get("channel_type") == "press_conf":
                    quotes = await extract_quotes(session, transcript, video, comments)
                    quotes_count += len(quotes)
                else:
                    opinions = await extract_opinions(session, transcript, video, comments)
                    opinions_count += len(opinions)
                await session.commit()
            except Exception as exc:
                await session.rollback()
                errors += 1
                logger.error("YouTube processing failed for %s: %s", video.get("title"), exc)

        total = quotes_count + opinions_count
        await log_sync_run(
            sync_type="youtube_harvest",
            api_used="youtube+groq",
            records_updated=total,
            errors=errors,
            notes=f"videos={len(videos)} quotes={quotes_count} opinions={opinions_count}",
        )

    result = {
        "videos": len(videos),
        "quotes": quotes_count,
        "opinions": opinions_count,
        "errors": errors,
    }
    logger.info("=== YouTube intelligence harvest complete: %s ===", result)
    return result


def should_run_youtube_harvest_now() -> bool:
    """Regular cadence is 6am to midnight UTC, World Cup cadence is 24 hours."""
    today = datetime.now(timezone.utc).date()
    if date(2026, 6, 11) <= today <= date(2026, 7, 19):
        return True
    now = datetime.now(timezone.utc).time()
    return dt_time(6, 0) <= now <= dt_time(23, 59)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "youtube":
        if "--scheduled" in sys.argv and not should_run_youtube_harvest_now():
            logger.info("Outside YouTube harvest window, skipping.")
        else:
            asyncio.run(run_youtube_harvest())
    else:
        asyncio.run(run_harvest_pipeline())
