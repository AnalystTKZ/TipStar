"""Extract significant press conference quotes from YouTube transcripts."""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import insert_press_conference_quote
from backend.embeddings.miniLM import encode
from backend.harvester.extraction_utils import extract_json_array
from backend.harvester.transcript_extractor import chunk_transcript

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a football press conference analyst.
Extract significant quotes from this press conference transcript.

Return a JSON array. Each object must include:
- exact_quote: word for word, no changes. Preserve exactly as spoken.
- speaker: full name if identifiable, else Unknown.
- speaker_role: manager, player, captain, assistant manager, spokesperson, or unknown.
- club_or_nation: their team or country if identifiable.
- quote_category: deflection, praise, self_praise, criticism, prediction, complaint, excuse, tribute, announcement, tactical, or emotional.
- controversy_score: integer 1 to 10.
- match_context: one sentence on the context.
- tournament: competition name if mentioned.

Only return quotes scoring 5 and above.
Return only JSON, no markdown."""


async def extract_quotes(
    session: AsyncSession,
    transcript: str,
    video_metadata: dict,
    top_comments: list[str],
) -> list[dict]:
    """Extract, embed, and store press conference quotes."""
    stored = []
    for chunk in chunk_transcript(transcript):
        user_prompt = _build_user_prompt(chunk, video_metadata)
        rows = await extract_json_array(SYSTEM_PROMPT, user_prompt)
        for row in rows:
            score = _as_int(row.get("controversy_score"))
            quote = str(row.get("exact_quote") or "").strip()
            if score < 5 or not quote:
                continue
            data = {
                "source_channel": video_metadata.get("channel_name"),
                "video_title": video_metadata.get("title"),
                "video_id": video_metadata.get("video_id"),
                "speaker": row.get("speaker") or "Unknown",
                "speaker_role": row.get("speaker_role") or "unknown",
                "club_or_nation": row.get("club_or_nation"),
                "exact_quote": quote,
                "quote_category": row.get("quote_category"),
                "controversy_score": score,
                "top_comments": top_comments,
                "match_context": row.get("match_context"),
                "tournament": row.get("tournament"),
                "embedding": encode(quote),
            }
            saved = await insert_press_conference_quote(session, data)
            stored.append(saved.to_dict())

    if stored:
        avg = sum(q.get("controversy_score") or 0 for q in stored) / len(stored)
        logger.info(
            "Press conference extracted: %s quotes=%d avg_score=%.1f",
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
