"""
YouTube Data API v3 harvester.

Targets official club, league, and federation channels for press conferences,
interviews, and post-match content. These are the highest-trust source for
direct quotes, team news, and injury updates.

Requires YOUTUBE_API_KEY env var.
"""
import logging
import re
import requests
from datetime import datetime, timedelta, timezone
from typing import Iterable

from backend.config.settings import YOUTUBE_API_KEY
from backend.database.db import get_session_factory, youtube_video_exists

logger = logging.getLogger(__name__)
SEARCH_ENDPOINT = "https://www.googleapis.com/youtube/v3/search"
CHANNELS_ENDPOINT = "https://www.googleapis.com/youtube/v3/channels"
COMMENTS_ENDPOINT = "https://www.googleapis.com/youtube/v3/commentThreads"

# Channel refs use handles where possible. The earlier hard-coded IDs were
# unreliable, so IDs are resolved at runtime via the YouTube Data API.
CHANNEL_REGISTRY = [
    {"channel_ref": "@mancity", "channel_name": "Man City Official", "type": "press_conf", "priority": 1, "active": True},
    {"channel_ref": "@fifa", "channel_name": "FIFA", "type": "press_conf", "priority": 1, "active": True},
    {"channel_ref": "@uefa", "channel_name": "UEFA", "type": "press_conf", "priority": 1, "active": True},
    {"channel_ref": "@premierleague", "channel_name": "Premier League", "type": "press_conf", "priority": 1, "active": True},
    {"channel_ref": "@InterMiamiCF", "channel_name": "Inter Miami CF", "type": "press_conf", "priority": 1, "active": True},
    {"channel_ref": "@AFASeleccion", "channel_name": "Argentina FA", "type": "press_conf", "priority": 1, "active": True},
    {"channel_ref": "@SkySportsFootball", "channel_name": "Sky Sports Football", "type": "opinion", "priority": 2, "active": True},
    {"channel_ref": "@ESPNFC", "channel_name": "ESPN FC", "type": "opinion", "priority": 2, "active": True},
    {"channel_ref": "@talkSPORT", "channel_name": "talkSPORT", "type": "opinion", "priority": 2, "active": True},
    {"channel_ref": "@TheOverlap", "channel_name": "The Overlap", "type": "opinion", "priority": 2, "active": True},
    {"channel_ref": "@goal", "channel_name": "GOAL", "type": "opinion", "priority": 3, "active": True},
    {"channel_ref": "@Tifo", "channel_name": "Tifo Football", "type": "opinion", "priority": 3, "active": True},
    {"channel_ref": "@COPA90", "channel_name": "COPA90", "type": "opinion", "priority": 3, "active": True},
]

TRACKED_CHANNELS = [(c["channel_ref"], c["channel_name"]) for c in CHANNEL_REGISTRY if c.get("active")]

# Search keywords that signal press conference or interview content.
PRESS_CONF_KEYWORDS = [
    "press conference",
    "post match",
    "post-match",
    "pre-match",
    "pre match",
    "post-match",
    "reaction",
    "interview",
    "speaks",
    "tells media",
]
OPINION_KEYWORDS = [
    "debate",
    "hot take",
    "best",
    "worst",
    "goat",
    "ranked",
    " vs ",
    "better",
    "reaction",
    "review",
    "explained",
]


def fetch_youtube_stories() -> list[dict]:
    """
    Fetch recent press conference and interview videos from official channels.
    Returns normalised story dicts compatible with the harvester pipeline.
    """
    if not YOUTUBE_API_KEY:
        logger.debug("YOUTUBE_API_KEY not set -- skipping YouTube harvester")
        return []

    published_after = (datetime.now(timezone.utc) - timedelta(hours=6)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    results = []
    seen_ids: set[str] = set()

    for channel_ref, channel_name in TRACKED_CHANNELS:
        try:
            channel_id = _resolve_channel_id(channel_ref)
            if not channel_id:
                logger.warning("YouTube channel not resolved for %s (%s)", channel_name, channel_ref)
                continue
            params = {
                "part": "snippet",
                "channelId": channel_id,
                "type": "video",
                "order": "date",
                "publishedAfter": published_after,
                "maxResults": 10,
                "key": YOUTUBE_API_KEY,
            }
            resp = requests.get(SEARCH_ENDPOINT, params=params, timeout=15)
            resp.raise_for_status()
            items = resp.json().get("items", [])

            for item in items:
                video_id = item.get("id", {}).get("videoId", "")
                if not video_id or video_id in seen_ids:
                    continue

                snippet = item.get("snippet", {})
                title = snippet.get("title", "").strip()
                if not title:
                    continue

                # Only keep press conferences, interviews, and match coverage.
                title_lower = title.lower()
                description_lower = snippet.get("description", "").lower()
                combined = f"{title_lower} {description_lower}"
                is_relevant = _matches_keywords(combined, PRESS_CONF_KEYWORDS) or _is_match_coverage(combined)
                if not is_relevant:
                    continue

                seen_ids.add(video_id)
                results.append({
                    "title": title,
                    "description": snippet.get("description", "")[:500].strip(),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "source": channel_name,
                    "source_confidence": "official",
                    "published_at": snippet.get("publishedAt", ""),
                })

            logger.debug("YouTube [%s]: processed %d items", channel_name, len(items))
        except requests.RequestException as e:
            logger.error("YouTube fetch failed for channel %s: %s", channel_name, e)

    logger.info("YouTube: fetched %d relevant videos", len(results))
    return results


def search_recent_videos(channel: dict, hours: int = 6) -> list[dict]:
    """Search one channel for recent videos matching its configured type."""
    if not YOUTUBE_API_KEY:
        return []

    channel_id = _resolve_channel_id(channel["channel_ref"])
    if not channel_id:
        logger.warning("YouTube channel not resolved for %s", channel.get("channel_name"))
        return []

    published_after = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    params = {
        "part": "snippet",
        "channelId": channel_id,
        "type": "video",
        "order": "date",
        "publishedAfter": published_after,
        "maxResults": 10,
        "key": YOUTUBE_API_KEY,
    }
    resp = requests.get(SEARCH_ENDPOINT, params=params, timeout=15)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    keywords = PRESS_CONF_KEYWORDS if channel["type"] == "press_conf" else OPINION_KEYWORDS

    videos = []
    for item in items:
        video_id = item.get("id", {}).get("videoId", "")
        snippet = item.get("snippet", {})
        title = snippet.get("title", "").strip()
        description = snippet.get("description", "").strip()
        combined = f"{title.lower()} {description.lower()}"
        if not video_id or not title:
            continue
        if not (_matches_keywords(combined, keywords) or _is_match_coverage(combined)):
            continue
        videos.append({
            "video_id": video_id,
            "title": title,
            "published_at": snippet.get("publishedAt", ""),
            "description": description,
            "channel_name": channel["channel_name"],
            "channel_type": channel["type"],
            "priority": channel["priority"],
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "source_confidence": "official" if channel["type"] == "press_conf" else "trusted_opinion",
        })
    return videos


def get_video_comments(video_id: str, max_results: int = 30) -> list[str]:
    """Return cleaned top comments. Only spam and empty comments are removed."""
    if not YOUTUBE_API_KEY:
        return []
    try:
        resp = requests.get(
            COMMENTS_ENDPOINT,
            params={
                "part": "snippet",
                "videoId": video_id,
                "order": "relevance",
                "maxResults": min(max_results, 100),
                "textFormat": "plainText",
                "key": YOUTUBE_API_KEY,
            },
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("YouTube comments fetch failed for %s: %s", video_id, exc)
        return []

    comments = []
    for item in resp.json().get("items", []):
        text = (
            item.get("snippet", {})
            .get("topLevelComment", {})
            .get("snippet", {})
            .get("textDisplay", "")
            .strip()
        )
        if _is_spam_comment(text):
            continue
        comments.append(text)
        if len(comments) >= 20:
            break
    return comments


async def is_already_harvested(video_id: str) -> bool:
    factory = get_session_factory()
    async with factory() as session:
        return await youtube_video_exists(session, video_id)


async def run_harvester(hours: int = 6, priority_limit: int | None = None) -> list[dict]:
    """
    Return new YouTube videos to process. Storage happens after transcript
    extraction so videos with no usable transcript can be retried later.
    """
    videos = []
    for channel in _active_channels(priority_limit):
        try:
            batch = search_recent_videos(channel, hours=hours)
            skipped = 0
            for video in batch:
                if await is_already_harvested(video["video_id"]):
                    skipped += 1
                    continue
                videos.append(video)
            logger.info(
                "YouTube [%s]: found=%d skipped=%d",
                channel["channel_name"],
                len(batch),
                skipped,
            )
        except requests.RequestException as exc:
            logger.error("YouTube search failed for %s: %s", channel["channel_name"], exc)
    return videos


def _resolve_channel_id(channel_ref: str) -> str | None:
    if channel_ref.startswith("UC"):
        return channel_ref
    handle = channel_ref if channel_ref.startswith("@") else f"@{channel_ref}"
    try:
        resp = requests.get(
            CHANNELS_ENDPOINT,
            params={"part": "id", "forHandle": handle, "key": YOUTUBE_API_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return items[0].get("id") if items else None
    except requests.RequestException as exc:
        logger.warning("YouTube channel resolve failed for %s: %s", handle, exc)
        return None


def _is_match_coverage(text: str) -> bool:
    match_signals = ["match highlights", "full match", "goal", "full-time", "kick off", "kickoff"]
    return any(s in text for s in match_signals)


def _matches_keywords(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _active_channels(priority_limit: int | None = None) -> list[dict]:
    channels = [c for c in CHANNEL_REGISTRY if c.get("active")]
    if priority_limit is not None:
        channels = [c for c in channels if int(c.get("priority", 3)) <= priority_limit]
    return channels


def _is_spam_comment(text: str) -> bool:
    if len(text.strip()) < 10:
        return True
    without_symbols = re.sub(r"[\W_]+", "", text, flags=re.UNICODE)
    return not without_symbols
