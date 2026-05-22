import logging
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

from backend.config.settings import GUARDIAN_API_KEY

logger = logging.getLogger(__name__)
ENDPOINT = "https://content.guardianapis.com/search"

_FOOTBALL_SECTIONS = "football"
_FOOTBALL_QUERIES = [
    "football",
    "Champions League",
    "World Cup 2026",
    "Premier League",
    "Manchester City",
    "Messi",
    "transfer",
]


def fetch_guardian_stories() -> list[dict]:
    """Fetch football stories from The Guardian Open Platform (last 6 hours)."""
    if not GUARDIAN_API_KEY:
        logger.debug("GUARDIAN_API_KEY not set -- skipping Guardian harvester")
        return []

    cutoff = datetime.utcnow() - timedelta(hours=6)
    from_time = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    results = []
    seen_ids: set[str] = set()

    for query in _FOOTBALL_QUERIES:
        try:
            params = {
                "q": query,
                "section": _FOOTBALL_SECTIONS,
                "from-date": from_time[:10],
                "order-by": "newest",
                "page-size": 10,
                "show-fields": "trailText,byline",
                "api-key": GUARDIAN_API_KEY,
            }
            resp = requests.get(ENDPOINT, params=params, timeout=15)
            resp.raise_for_status()
            articles = resp.json().get("response", {}).get("results", [])
            for a in articles:
                published_at = a.get("webPublicationDate", "")
                if not _is_recent(published_at, cutoff):
                    continue
                article_id = a.get("id", "")
                if article_id in seen_ids:
                    continue
                seen_ids.add(article_id)
                title = a.get("webTitle", "").strip()
                if not title:
                    continue
                fields = a.get("fields", {})
                results.append({
                    "title": title,
                    "description": _clean_text(fields.get("trailText") or ""),
                    "url": a.get("webUrl", ""),
                    "source": "The Guardian",
                    "source_confidence": "trusted_news",
                    "published_at": published_at,
                })
        except requests.RequestException as e:
            logger.error("Guardian fetch failed for query '%s': %s", query, e)

    logger.info("Guardian: fetched %d articles", len(results))
    return results


def _is_recent(value: str, cutoff: datetime) -> bool:
    try:
        published = datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        return published >= cutoff
    except Exception:
        return True


def _clean_text(value: str) -> str:
    if not value:
        return ""
    return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
