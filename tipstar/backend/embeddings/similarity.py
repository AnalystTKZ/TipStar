"""
Cosine similarity search functions.

The production Supabase schema currently stores embeddings as JSON/text. These
helpers compute cosine similarity in Python so generation still gets context
without requiring pgvector columns.
"""
import json
import logging
import math
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


def _vec_literal(embedding: list[float]) -> str:
    """Format a Python float list as a pgvector literal string."""
    return "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"


def _parse_embedding(value) -> list[float] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [float(v) for v in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [float(v) for v in parsed]
        except json.JSONDecodeError:
            try:
                stripped = value.strip().strip("[]")
                return [float(v) for v in stripped.split(",") if v.strip()]
            except ValueError:
                return None
    return None


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _rank_rows(rows: list[dict], embedding: list[float], top_k: int) -> list[dict]:
    ranked = []
    for row in rows:
        row_embedding = _parse_embedding(row.get("embedding"))
        if not row_embedding:
            continue
        item = {k: v for k, v in row.items() if k != "embedding"}
        item["similarity"] = _cosine(embedding, row_embedding)
        ranked.append(item)
    ranked.sort(key=lambda r: r.get("similarity", 0), reverse=True)
    return ranked[:top_k]


async def search_similar_news(
    session: AsyncSession,
    embedding: list[float],
    top_k: int = 5,
    exclude_id: Optional[str] = None,
) -> list[dict]:
    """Return the top_k most similar news items by cosine distance."""
    sql = text("""
        SELECT id, title, source, source_confidence, url, published_at, relevance_score, is_world_cup, embedding
        FROM news
        WHERE embedding IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 500
    """)

    try:
        result = await session.execute(sql)
        rows = [dict(r) for r in result.mappings().all()]
        if exclude_id:
            rows = [r for r in rows if str(r.get("id")) != str(exclude_id)]
        return _rank_rows(rows, embedding, top_k)
    except Exception as e:
        logger.warning(f"similarity search (news) failed: {e}")
        return []


async def search_similar_players(
    session: AsyncSession,
    embedding: list[float],
    top_k: int = 3,
) -> list[dict]:
    """Return the top_k most relevant players by cosine distance."""
    sql = text("""
        SELECT id, name, nationality, current_club, position, tier,
               world_cup_appearances, world_cup_goals, status,
               world_cup_squad, market_value, content_angle, notes, embedding
        FROM players
        WHERE embedding IS NOT NULL
    """)
    try:
        result = await session.execute(sql)
        return _rank_rows([dict(r) for r in result.mappings().all()], embedding, top_k)
    except Exception as e:
        logger.warning(f"similarity search (players) failed: {e}")
        return []


async def search_similar_drama(
    session: AsyncSession,
    embedding: list[float],
    top_k: int = 3,
) -> list[dict]:
    """Return the top_k most relevant drama entries by cosine distance."""
    sql = text("""
        SELECT id, title, players_involved, teams_involved,
               category, severity, summary, status, embedding
        FROM drama
        WHERE embedding IS NOT NULL
    """)
    try:
        result = await session.execute(sql)
        return _rank_rows([dict(r) for r in result.mappings().all()], embedding, top_k)
    except Exception as e:
        logger.warning(f"similarity search (drama) failed: {e}")
        return []


async def search_relevant_quotes(
    session: AsyncSession,
    embedding: list[float],
    top_k: int = 3,
) -> list[dict]:
    sql = text("""
        SELECT id, source_channel, video_title, video_id, speaker, speaker_role,
               club_or_nation, exact_quote, quote_category, controversy_score,
               top_comments, match_context, tournament, embedding
        FROM press_conferences
        WHERE embedding IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 500
    """)
    try:
        result = await session.execute(sql)
        return _rank_rows([dict(r) for r in result.mappings().all()], embedding, top_k)
    except Exception as e:
        logger.warning("similarity search (press_conferences) failed: %s", e)
        return []


async def search_relevant_opinions(
    session: AsyncSession,
    embedding: list[float],
    top_k: int = 3,
) -> list[dict]:
    sql = text("""
        SELECT id, source_channel, video_title, video_id, opinion_text,
               original_speaker, stance, controversy_score, topic_tags,
               players_mentioned, top_comments, embedding
        FROM opinions
        WHERE embedding IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 500
    """)
    try:
        result = await session.execute(sql)
        return _rank_rows([dict(r) for r in result.mappings().all()], embedding, top_k)
    except Exception as e:
        logger.warning("similarity search (opinions) failed: %s", e)
        return []


async def search_relevant_facts(
    session: AsyncSession,
    embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    sql = text("""
        SELECT id, claim_text, claim_type, entity_type, entities, temporal_scope,
               source, source_confidence, status, confidence_score, evidence_count,
               evidence_urls, last_seen_at, embedding
        FROM fact_claims
        WHERE embedding IS NOT NULL
          AND status = 'verified'
        ORDER BY last_seen_at DESC
        LIMIT 500
    """)
    try:
        result = await session.execute(sql)
        return _rank_rows([dict(r) for r in result.mappings().all()], embedding, top_k)
    except Exception as e:
        logger.warning("similarity search (fact_claims) failed: %s", e)
        return []


async def semantic_search_knowledge(
    session: AsyncSession,
    embedding: list[float],
    tables: list[str] = None,
    top_k: int = 5,
) -> dict:
    """
    Multi-table semantic search for the KnowledgeBase search bar.
    Returns results grouped by table.
    """
    if tables is None:
        tables = ["players", "teams", "drama"]

    results = {}
    table_configs = {
        "players": "id, name, nationality, current_club, position, tier, embedding",
        "teams": "id, name, country, league, manager, world_cup_status, embedding",
        "drama": "id, title, severity, summary, status, embedding",
    }

    for table in tables:
        cols = table_configs.get(table)
        if not cols:
            continue
        sql = text(f"""
            SELECT {cols}
            FROM {table}
            WHERE embedding IS NOT NULL
        """)
        try:
            result = await session.execute(sql)
            results[table] = _rank_rows([dict(r) for r in result.mappings().all()], embedding, top_k)
        except Exception as e:
            logger.warning(f"Semantic search failed for {table}: {e}")
            results[table] = []

    return results
