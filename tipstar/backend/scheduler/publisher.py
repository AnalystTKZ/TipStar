"""
Approved post publisher: reads approved posts from DB and posts them to X.
Runs every 15 minutes via GitHub Actions or cron.
"""
import asyncio
import logging
import os
import sys
import tweepy

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from backend.config.settings import (
    TWITTER_API_KEY, TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET,
    TWITTER_BEARER_TOKEN,
)
from backend.database.db import get_session_factory, get_approved_unposted, update_post_status

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/tipstar.log"),
    ],
)
logger = logging.getLogger("publisher")

_twitter_client = None


def _get_twitter():
    global _twitter_client
    if _twitter_client is None:
        _twitter_client = tweepy.Client(
            bearer_token=TWITTER_BEARER_TOKEN,
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_SECRET,
            wait_on_rate_limit=True,
        )
    return _twitter_client


def _post_tweet(content: str) -> tuple[bool, str]:
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        return False, "Missing Twitter credentials"
    if len(content) > 280:
        content = content[:277] + "..."
    try:
        client = _get_twitter()
        response = client.create_tweet(text=content)
        return True, str(response.data["id"])
    except tweepy.TweepyException as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)


async def run_publish_pipeline():
    logger.info("=== TipStar publish pipeline starting ===")
    factory = get_session_factory()

    async with factory() as session:
        posts = await get_approved_unposted(session)
        if not posts:
            logger.info("No approved posts to publish.")
            return

        for post in posts:
            post_id = post["id"]
            content = (post.get("content") or "").strip()
            title = post.get("story_title", "")

            if not content:
                logger.warning(f"Post {post_id} is empty -- skipping")
                continue

            success, result = _post_tweet(content)
            if success:
                await update_post_status(session, post_id, "posted")
                await session.commit()
                logger.info(f"Posted tweet {result}: {title}")
            else:
                logger.error(f"Failed to post {post_id}: {result}")

    logger.info("=== Publish pipeline complete ===")


if __name__ == "__main__":
    asyncio.run(run_publish_pipeline())
