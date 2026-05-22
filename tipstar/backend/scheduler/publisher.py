"""
Approved post publisher: reads approved posts from DB and posts them to X.
Runs every 15 minutes via GitHub Actions or cron.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path
import tweepy

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from backend.config.settings import (
    TWITTER_API_KEY, TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET,
    TWITTER_BEARER_TOKEN,
)
from backend.database.db import (
    get_session_factory,
    get_approved_unposted,
    set_post_image_path,
    update_post_status,
)

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
_twitter_api = None
PROJECT_ROOT = Path(__file__).resolve().parents[2]


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


def _get_twitter_api():
    global _twitter_api
    if _twitter_api is None:
        auth = tweepy.OAuth1UserHandler(
            TWITTER_API_KEY,
            TWITTER_API_SECRET,
            TWITTER_ACCESS_TOKEN,
            TWITTER_ACCESS_SECRET,
        )
        _twitter_api = tweepy.API(auth, wait_on_rate_limit=True)
    return _twitter_api


def _resolve_image_path(image_path: str | None) -> Path | None:
    if not image_path:
        return None
    path = Path(image_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path if path.exists() else None


def _post_tweet(content: str, image_path: str | None = None) -> tuple[bool, str]:
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        return False, "Missing Twitter credentials"
    if len(content) > 280:
        content = content[:277] + "..."
    try:
        client = _get_twitter()
        media_ids = None
        resolved_image = _resolve_image_path(image_path)
        if resolved_image:
            media = _get_twitter_api().media_upload(filename=str(resolved_image))
            media_ids = [media.media_id]
        if media_ids:
            response = client.create_tweet(text=content, media_ids=media_ids)
        else:
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

            image_path = post.get("image_path")
            if not image_path:
                try:
                    from backend.visuals.post_renderer import render_post_visual
                    image_path = render_post_visual(post)
                    await set_post_image_path(session, post_id, image_path)
                    await session.commit()
                except Exception as exc:
                    logger.warning("Could not render image for post %s before publish: %s", post_id, exc)

            success, result = _post_tweet(content, image_path=image_path)
            if success:
                await update_post_status(session, post_id, "posted")
                await session.commit()
                logger.info(f"Posted tweet {result}: {title}")
            else:
                logger.error(f"Failed to post {post_id}: {result}")

    logger.info("=== Publish pipeline complete ===")


if __name__ == "__main__":
    asyncio.run(run_publish_pipeline())
