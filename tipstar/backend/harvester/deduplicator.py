import hashlib
import json
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
SEEN_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "seen_stories.json")


def _load() -> dict:
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(seen: dict):
    os.makedirs(os.path.dirname(SEEN_FILE), exist_ok=True)
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f)


def _hash(story: dict) -> str:
    key = story.get("title", "").lower().strip()
    return hashlib.md5(key.encode()).hexdigest()


def deduplicate(stories: list[dict]) -> list[dict]:
    """Return only stories not seen in the last 24 hours.

    This function is intentionally read-only. Call mark_seen() after a story is
    inserted or intentionally skipped so failed inserts can be retried.
    """
    seen = _load()
    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    seen = {k: v for k, v in seen.items() if v >= cutoff}

    fresh = []
    for story in stories:
        h = _hash(story)
        if h not in seen:
            fresh.append(story)

    logger.info(f"Deduplicator: {len(fresh)} new out of {len(stories)}")
    return fresh


def mark_seen(story: dict) -> None:
    """Mark one successfully processed story as seen."""
    seen = _load()
    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    seen[_hash(story)] = datetime.utcnow().isoformat()
    _save(seen)
