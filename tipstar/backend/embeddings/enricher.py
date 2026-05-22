"""
Story enricher: combines MiniLM embeddings with pgvector similarity search
to build a context dict that is injected into the Groq prompt.
"""
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.embeddings.miniLM import encode
from backend.embeddings.similarity import (
    search_similar_news,
    search_similar_players,
    search_similar_drama,
)

logger = logging.getLogger(__name__)


async def enrich_story(
    session: AsyncSession,
    news_item: dict,
    editorial_notes: str = "",
) -> dict:
    """
    Enrich a news story with semantic context for use in the Groq prompt.

    Steps:
      1. Encode the story title + description with MiniLM
      2. Find top 5 similar past news stories
      3. Find top 3 related players
      4. Find top 3 related drama entries
      5. Return structured context dict
    """
    text_to_embed = f"{news_item.get('title', '')} {news_item.get('description', '')}"
    embedding = encode(text_to_embed)

    # Store the embedding on the news item for later DB insertion
    news_item["embedding"] = embedding
    news_id = news_item.get("id")

    similar_news = await search_similar_news(
        session, embedding, top_k=5, exclude_id=str(news_id) if news_id else None
    )
    related_players = await search_similar_players(session, embedding, top_k=3)
    related_drama = await search_similar_drama(session, embedding, top_k=3)

    return {
        "embedding": embedding,
        "similar_news": _format_news(similar_news),
        "related_players": _format_players(related_players),
        "related_drama": _format_drama(related_drama),
        "editorial_notes": editorial_notes or "",
    }


def _format_news(rows: list[dict]) -> str:
    if not rows:
        return "No similar past coverage found."
    lines = []
    for r in rows:
        title = r.get("title", "")
        source = r.get("source", "")
        sim = r.get("similarity", 0)
        lines.append(f"- [{source}] {title} (similarity: {sim:.2f})")
    return "\n".join(lines)


def _format_players(rows: list[dict]) -> str:
    if not rows:
        return "No related players found."
    lines = []
    for r in rows:
        name = r.get("name", "")
        club = r.get("current_club", "")
        tier = r.get("tier", "")
        wc_goals = r.get("world_cup_goals", 0)
        lines.append(f"- {name} ({club}, {tier}, {wc_goals} WC goals)")
    return "\n".join(lines)


def _format_drama(rows: list[dict]) -> str:
    if not rows:
        return "No related drama entries found."
    lines = []
    for r in rows:
        title = r.get("title", "")
        severity = r.get("severity", "")
        status = r.get("status", "")
        lines.append(f"- [{severity.upper()}] {title} (Status: {status})")
    return "\n".join(lines)
