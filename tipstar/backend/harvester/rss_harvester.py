import feedparser
import logging
from datetime import datetime, timezone

from backend.config.settings import RSS_FEEDS_OFFICIAL, RSS_FEEDS_TRUSTED

logger = logging.getLogger(__name__)


def fetch_rss_stories() -> list[dict]:
    """Fetch stories from configured RSS feeds published in the last 6 hours."""
    results = []
    cutoff = datetime.now(tz=timezone.utc).timestamp() - (6 * 3600)

    feed_sources = (
        [(url, "official") for url in RSS_FEEDS_OFFICIAL]
        + [(url, "trusted_news") for url in RSS_FEEDS_TRUSTED]
    )

    for feed_url, confidence in feed_sources:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                ts = _parse_ts(entry)
                if ts and ts < cutoff:
                    continue
                title = entry.get("title", "").strip()
                if not title:
                    continue
                results.append({
                    "title": title,
                    "description": entry.get("summary", "").strip(),
                    "url": entry.get("link", ""),
                    "source": feed.feed.get("title", feed_url),
                    "source_confidence": confidence,
                    "published_at": entry.get("published", ""),
                })
            logger.info("RSS [%s]: %d entries", feed_url, len(feed.entries))
        except Exception as e:
            logger.error("RSS failed for %s: %s", feed_url, e)

    return results


def _parse_ts(entry) -> float | None:
    try:
        if getattr(entry, "published_parsed", None):
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).timestamp()
    except Exception:
        pass
    return None
