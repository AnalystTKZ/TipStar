"""
pgvector cosine similarity search functions.
Each function queries a specific table ordered by embedding <=> query_vector.
Requires the pgvector extension and VECTOR columns (created via migration).
"""
import json
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


def _vec_literal(embedding: list[float]) -> str:
    """Format a Python float list as a pgvector literal string."""
    return "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"


async def search_similar_news(
    session: AsyncSession,
    embedding: list[float],
    top_k: int = 5,
    exclude_id: Optional[str] = None,
) -> list[dict]:
    """Return the top_k most similar news items by cosine distance."""
    vec = _vec_literal(embedding)
    exclude_clause = "AND id != :exclude_id" if exclude_id else ""
    sql = text(f"""
        SELECT id, title, source, url, published_at, relevance_score, is_world_cup,
               1 - (embedding <=> :vec::vector) AS similarity
        FROM news
        WHERE embedding IS NOT NULL {exclude_clause}
        ORDER BY embedding <=> :vec::vector
        LIMIT :top_k
    """)

    params = {"vec": vec, "top_k": top_k}
    if exclude_id:
        params["exclude_id"] = exclude_id

    try:
        result = await session.execute(sql, params)
        rows = result.mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"similarity search (news) failed: {e}")
        return []


async def search_similar_players(
    session: AsyncSession,
    embedding: list[float],
    top_k: int = 3,
) -> list[dict]:
    """Return the top_k most relevant players by cosine distance."""
    vec = _vec_literal(embedding)
    sql = text("""
        SELECT id, name, nationality, current_club, position, tier,
               world_cup_appearances, world_cup_goals, status,
               world_cup_squad, market_value, content_angle, notes,
               1 - (embedding <=> :vec::vector) AS similarity
        FROM players
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> :vec::vector
        LIMIT :top_k
    """)
    try:
        result = await session.execute(sql, {"vec": vec, "top_k": top_k})
        return [dict(r) for r in result.mappings().all()]
    except Exception as e:
        logger.warning(f"similarity search (players) failed: {e}")
        return []


async def search_similar_drama(
    session: AsyncSession,
    embedding: list[float],
    top_k: int = 3,
) -> list[dict]:
    """Return the top_k most relevant drama entries by cosine distance."""
    vec = _vec_literal(embedding)
    sql = text("""
        SELECT id, title, players_involved, teams_involved,
               category, severity, summary, status,
               1 - (embedding <=> :vec::vector) AS similarity
        FROM drama
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> :vec::vector
        LIMIT :top_k
    """)
    try:
        result = await session.execute(sql, {"vec": vec, "top_k": top_k})
        return [dict(r) for r in result.mappings().all()]
    except Exception as e:
        logger.warning(f"similarity search (drama) failed: {e}")
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
    vec = _vec_literal(embedding)

    table_configs = {
        "players": "id, name, nationality, current_club, position, tier",
        "teams": "id, name, country, league, manager, world_cup_status",
        "drama": "id, title, severity, summary, status",
    }

    for table in tables:
        cols = table_configs.get(table)
        if not cols:
            continue
        sql = text(f"""
            SELECT {cols}, 1 - (embedding <=> :vec::vector) AS similarity
            FROM {table}
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> :vec::vector
            LIMIT :top_k
        """)
        try:
            result = await session.execute(sql, {"vec": vec, "top_k": top_k})
            results[table] = [dict(r) for r in result.mappings().all()]
        except Exception as e:
            logger.warning(f"Semantic search failed for {table}: {e}")
            results[table] = []

    return results
