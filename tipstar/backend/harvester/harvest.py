import logging

from backend.harvester.newsapi_harvester import fetch_newsapi_stories
from backend.harvester.rss_harvester import fetch_rss_stories
from backend.harvester.guardian_harvester import fetch_guardian_stories
from backend.harvester.youtube_harvester import fetch_youtube_stories
from backend.harvester.deduplicator import deduplicate

logger = logging.getLogger(__name__)

# Source priority order: official > trusted_news > scraped/unknown.
# Stories harvested earlier in this list win deduplication when titles collide.
_SOURCE_ORDER = [
    fetch_youtube_stories,    # official channels - press conferences, interviews
    fetch_rss_stories,        # official + trusted RSS (BBC, Sky, ESPN, Man City, UEFA, FIFA)
    fetch_guardian_stories,   # Guardian Open Platform - trusted longform
    fetch_newsapi_stories,    # NewsAPI broad sweep - lowest trust, highest volume
]


def harvest_all() -> list[dict]:
    """
    Aggregate all sources in priority order, deduplicate, and return fresh stories.
    source_confidence is set per story by each harvester:
      official       - YouTube official channels, official RSS feeds
      trusted_news   - BBC, Sky Sports, ESPN, Guardian, NewsAPI
    """
    stories = []
    for fetch_fn in _SOURCE_ORDER:
        try:
            batch = fetch_fn()
            stories.extend(batch)
        except Exception as e:
            logger.error("Harvester %s failed: %s", fetch_fn.__name__, e)

    fresh = deduplicate(stories)
    logger.info("Harvest complete: %d fresh stories from %d total", len(fresh), len(stories))
    return fresh
