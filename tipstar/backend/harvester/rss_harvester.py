import feedparser
import logging
from datetime import datetime, timezone

from backend.config.settings import RSS_FEEDS

logger = logging.getLogger(__name__)


def fetch_rss_stories() -> list[dict]:
    """Fetch stories from configured RSS feeds published in the last 6 hours."""
    results = []
    cutoff = datetime.now(tz=timezone.utc).timestamp() - (6 * 3600)

    for feed_url in RSS_FEEDS:
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
                    "published_at": entry.get("published", ""),
                })
            logger.info(f"RSS [{feed_url}]: {len(feed.entries)} entries")
        except Exception as e:
            logger.error(f"RSS failed for {feed_url}: {e}")

    return results


def _parse_ts(entry) -> float | None:
    try:
        if getattr(entry, "published_parsed", None):
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).timestamp()
    except Exception:
        pass
    return None
