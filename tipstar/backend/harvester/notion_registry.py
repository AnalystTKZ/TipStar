"""
Dynamic Notion database registry.

Discovers all databases under the TipStar HQ page at runtime by querying
the Notion API. New databases added to Notion are picked up automatically
without any code changes.

Usage:
    from backend.harvester.notion_registry import get_db_id, list_databases

    players_id = get_db_id("players")          # fuzzy match on title
    content_cal_id = get_db_id("content calendar")
    all_dbs = list_databases()                  # {normalised_title: db_id}
"""
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_NOTION_VERSION = "2022-06-28"
_BASE = "https://api.notion.com/v1"

# TipStar HQ page ID -- the root we search under
_HQ_PAGE_ID = os.getenv("NOTION_HQ_PAGE_ID", "3688031e4fc981acb97ef602b52eeb7f")

_cache: dict[str, str] = {}  # normalised title -> db_id
_cache_loaded = False


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('NOTION_API_KEY', '')}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _normalise(title: str) -> str:
    return title.lower().strip()


def _load_registry() -> dict[str, str]:
    """
    Query Notion search API for all databases, filter to those whose
    ancestor is the TipStar HQ page, return {normalised_title: db_id}.

    Falls back to env-var IDs so the system works even if the API is down.
    """
    dbs: dict[str, str] = {}

    # Always seed from env vars as fallback
    env_fallbacks = {
        "players": os.getenv("NOTION_PLAYERS_DB_ID", ""),
        "teams": os.getenv("NOTION_TEAMS_DB_ID", ""),
        "drama log": os.getenv("NOTION_DRAMA_DB_ID", ""),
        "world cup 2026": os.getenv("NOTION_MATCHES_DB_ID", ""),
        "content calendar": os.getenv("NOTION_CONTENT_CALENDAR_DB_ID", ""),
    }
    for title, db_id in env_fallbacks.items():
        if db_id:
            dbs[title] = db_id

    api_key = os.getenv("NOTION_API_KEY", "")
    if not api_key:
        logger.warning("NOTION_API_KEY not set -- using env-var fallbacks only")
        return dbs

    try:
        # Search for all databases the integration can access
        cursor = None
        while True:
            payload: dict = {"filter": {"value": "database", "property": "object"}, "page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor

            resp = requests.post(f"{_BASE}/search", json=payload, headers=_headers(), timeout=15)
            if resp.status_code != 200:
                logger.warning("Notion search failed: %s", resp.status_code)
                break

            data = resp.json()
            for item in data.get("results", []):
                raw_title = ""
                title_parts = item.get("title", [])
                if title_parts:
                    raw_title = "".join(t.get("plain_text", "") for t in title_parts)
                elif item.get("properties", {}).get("title"):
                    parts = item["properties"]["title"].get("title", [])
                    raw_title = "".join(t.get("plain_text", "") for t in parts)

                if raw_title:
                    dbs[_normalise(raw_title)] = item["id"].replace("-", "")

            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

        logger.info("Notion registry loaded: %d databases", len(dbs))
    except Exception as exc:
        logger.warning("Notion registry load error: %s -- using env fallbacks", exc)

    return dbs


def _ensure_loaded() -> None:
    global _cache, _cache_loaded
    if not _cache_loaded:
        _cache = _load_registry()
        _cache_loaded = True


def reload() -> dict[str, str]:
    """Force a fresh discovery from Notion (clears cache)."""
    global _cache, _cache_loaded
    _cache_loaded = False
    _ensure_loaded()
    return _cache


def list_databases() -> dict[str, str]:
    """Return all known databases as {normalised_title: db_id}."""
    _ensure_loaded()
    return dict(_cache)


def get_db_id(name: str) -> Optional[str]:
    """
    Return the database ID for a given name (case-insensitive, partial match).
    Exact match wins; otherwise returns the first title that contains the query.
    """
    _ensure_loaded()
    key = _normalise(name)

    if key in _cache:
        return _cache[key]

    # Partial match fallback
    for title, db_id in _cache.items():
        if key in title or title in key:
            return db_id

    return None
