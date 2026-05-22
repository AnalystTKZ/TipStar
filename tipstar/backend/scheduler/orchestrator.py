"""
Harvest -> Embed -> Enrich -> Generate -> Persist pipeline.
Runs every 30 minutes via GitHub Actions or cron.
"""
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from backend.config.settings import MIN_RELEVANCE_SCORE
from backend.database.db import get_session_factory, init_db, insert_news, insert_posts
from backend.embeddings.enricher import enrich_story
from backend.generator.groq_generator import generate_posts
from backend.harvester.harvest import harvest_all
from backend.harvester.notion_harvester import (
    fetch_players, fetch_teams, fetch_drama, fetch_config,
    write_back_from_story,
)

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
    from backend.database.db import upsert_player, upsert_team, insert_drama
    from backend.embeddings.miniLM import encode

    logger.info("Syncing Notion knowledge base...")

    players = fetch_players()
    for p in players:
        p["embedding"] = encode(f"{p['name']} {p.get('current_club','')} {p.get('position','')}")
        await upsert_player(session, p)
    logger.info(f"Synced {len(players)} players from Notion")

    teams = fetch_teams()
    for t in teams:
        t["embedding"] = encode(f"{t['name']} {t.get('league','')} {t.get('playing_style','')}")
        await upsert_team(session, t)
    logger.info(f"Synced {len(teams)} teams from Notion")

    drama_items = fetch_drama()
    for d in drama_items:
        d["embedding"] = encode(f"{d['title']} {d.get('summary','')}")
        await insert_drama(session, d)
    logger.info(f"Synced {len(drama_items)} drama entries from Notion")

    await session.commit()


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
                else:
                    news_id = None

                # Enrich with semantic context
                context = await enrich_story(session, story, editorial_notes)

                # Generate post variants via Groq
                generated = generate_posts(story, enriched_context=context)
                if generated is None:
                    logger.info(f"Skipped (low relevance): {title}")
                    skipped += 1
                    continue

                # Persist posts
                count = await insert_posts(session, generated, news_id=news_id)
                await session.commit()
                logger.info(f"Score {generated.get('relevance_score')}/10 -- {count} posts: {title}")

                # Write new players, drama, and match results back to Notion
                write_back_from_story(story, generated)

                pushed += 1

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed for '{title}': {e}")
                skipped += 1

    logger.info(f"=== Pipeline complete: {pushed} stories, {skipped} skipped ===")


if __name__ == "__main__":
    asyncio.run(run_harvest_pipeline())
