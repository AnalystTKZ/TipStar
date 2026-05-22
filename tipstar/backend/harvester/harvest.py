import logging

from backend.harvester.newsapi_harvester import fetch_newsapi_stories
from backend.harvester.rss_harvester import fetch_rss_stories
from backend.harvester.deduplicator import deduplicate

logger = logging.getLogger(__name__)


def harvest_all() -> list[dict]:
    """Aggregate all sources, deduplicate, and return fresh stories."""
    stories = []
    stories.extend(fetch_newsapi_stories())
    stories.extend(fetch_rss_stories())
    fresh = deduplicate(stories)
    logger.info(f"Harvest complete: {len(fresh)} fresh stories")
    return fresh
