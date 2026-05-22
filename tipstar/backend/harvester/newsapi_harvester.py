import logging
import requests
from datetime import datetime, timedelta

from backend.config.settings import NEWS_API_KEY, NEWSAPI_FOOTBALL_QUERY, NEWSAPI_PAGE_SIZE, NEWSAPI_LANGUAGE

logger = logging.getLogger(__name__)
ENDPOINT = "https://newsapi.org/v2/everything"


def fetch_newsapi_stories() -> list[dict]:
    """Fetch football stories from NewsAPI published in the last 6 hours."""
    if not NEWS_API_KEY:
        logger.warning("NEWS_API_KEY not set -- skipping NewsAPI")
        return []

    from_time = (datetime.utcnow() - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "q": NEWSAPI_FOOTBALL_QUERY,
        "language": NEWSAPI_LANGUAGE,
        "sortBy": "publishedAt",
        "pageSize": NEWSAPI_PAGE_SIZE,
        "from": from_time,
        "apiKey": NEWS_API_KEY,
    }

    try:
        resp = requests.get(ENDPOINT, params=params, timeout=15)
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
        logger.info(f"NewsAPI: fetched {len(articles)} articles")
        return [_normalise(a) for a in articles if _normalise(a)]
    except requests.RequestException as e:
        logger.error(f"NewsAPI fetch failed: {e}")
        return []


def _normalise(a: dict) -> dict | None:
    title = (a.get("title") or "").strip()
    if not title or title == "[Removed]":
        return None
    return {
        "title": title,
        "description": (a.get("description") or "").strip(),
        "url": a.get("url", ""),
        "source": a.get("source", {}).get("name", "NewsAPI"),
        "source_confidence": "trusted_news",
        "published_at": a.get("publishedAt", ""),
    }
