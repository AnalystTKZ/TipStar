"""YouTube transcript extraction helpers."""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

NOISE_PATTERNS = [
    r"\[music\]",
    r"\[applause\]",
    r"\[laughter\]",
    r"\(music\)",
    r"\(applause\)",
    r"\(laughter\)",
]


def get_transcript(video_id: str) -> str | None:
    """Return a clean transcript string, or None if captions are unavailable."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        logger.warning("youtube-transcript-api is not installed")
        return None

    try:
        try:
            segments = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
        except AttributeError:
            api = YouTubeTranscriptApi()
            segments = api.fetch(video_id, languages=["en"])
            segments = [{"text": item.text} for item in segments]
        text = " ".join((segment.get("text") or "").strip() for segment in segments)
        return _clean_transcript(text)
    except Exception as exc:
        logger.warning("Transcript unavailable for %s: %s", video_id, exc)
        return None


def chunk_transcript(transcript: str, chunk_size: int = 2000, overlap: int = 200) -> list[str]:
    """Split a transcript into overlapping chunks for LLM extraction."""
    if not transcript:
        return []
    transcript = transcript.strip()
    if len(transcript) <= chunk_size:
        return [transcript]

    chunks = []
    start = 0
    while start < len(transcript):
        end = min(len(transcript), start + chunk_size)
        chunks.append(transcript[start:end].strip())
        if end == len(transcript):
            break
        start = max(0, end - overlap)
    return chunks


def _clean_transcript(text: str) -> str:
    cleaned = text.replace("\n", " ")
    for pattern in NOISE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned
