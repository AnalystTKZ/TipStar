"""Extract pundit opinions and debate angles from YouTube transcripts."""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import insert_opinion
from backend.embeddings.miniLM import encode
from backend.harvester.extraction_utils import extract_json_array
from backend.harvester.transcript_extractor import chunk_transcript

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a football content analyst.
Extract the strongest opinions, hot takes, and debate angles from this football transcript.

Return a JSON array. Each object must include:
- opinion_text: the opinion clearly stated in one or two sentences, in third person.
- original_speaker: pundit or presenter name if identifiable, else Unknown.
- controversy_score: integer 1 to 10.
- topic_tags: comma separated list of topics.
- players_mentioned: comma separated player names.
- stance: pro, anti, or neutral toward the subject.

Only return strong, debatable opinions scoring 6 and above.
No bland takes.
Return only JSON, no markdown."""


async def extract_opinions(
    session: AsyncSession,
    transcript: str,
    video_metadata: dict,
    top_comments: list[str],
) -> list[dict]:
    """Extract, embed, and store opinion records."""
    stored = []
    for chunk in chunk_transcript(transcript):
        user_prompt = _build_user_prompt(chunk, video_metadata)
        rows = await extract_json_array(SYSTEM_PROMPT, user_prompt)
        for row in rows:
            score = _as_int(row.get("controversy_score"))
            opinion_text = str(row.get("opinion_text") or "").strip()
            if score < 6 or not opinion_text:
                continue
            data = {
                "source_channel": video_metadata.get("channel_name"),
                "video_title": video_metadata.get("title"),
                "video_id": video_metadata.get("video_id"),
                "opinion_text": opinion_text,
                "original_speaker": row.get("original_speaker") or "Unknown",
                "stance": row.get("stance"),
                "controversy_score": score,
                "topic_tags": row.get("topic_tags"),
                "players_mentioned": row.get("players_mentioned"),
                "top_comments": top_comments,
                "embedding": encode(opinion_text),
            }
            saved = await insert_opinion(session, data)
            stored.append(saved.to_dict())

    if stored:
        avg = sum(o.get("controversy_score") or 0 for o in stored) / len(stored)
        logger.info(
            "Opinions extracted: %s opinions=%d avg_score=%.1f",
            video_metadata.get("title"),
            len(stored),
            avg,
        )
    return stored


def _build_user_prompt(chunk: str, video_metadata: dict) -> str:
    return "\n".join([
        f"VIDEO TITLE: {video_metadata.get('title', '')}",
        f"SOURCE CHANNEL: {video_metadata.get('channel_name', '')}",
        f"PUBLISHED: {video_metadata.get('published_at', '')}",
        "TRANSCRIPT CHUNK:",
        chunk,
    ])


def _as_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
