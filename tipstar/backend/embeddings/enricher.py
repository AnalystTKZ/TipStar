"""
Story enricher: combines MiniLM embeddings with pgvector similarity search
to build a context dict that is injected into the Groq prompt.
"""
import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.embeddings.miniLM import encode
from backend.embeddings.similarity import (
    search_similar_news,
    search_similar_players,
    search_similar_drama,
    search_relevant_opinions,
    search_relevant_quotes,
)

logger = logging.getLogger(__name__)


async def enrich_story(
    session: AsyncSession,
    news_item: dict,
    editorial_notes: str = "",
) -> dict:
    """
    Enrich a news story with full DB context for use in the Groq prompt.

    Steps:
      1. Encode title + description with MiniLM
      2. Find semantically similar past news (avoid repeating those angles)
      3. Find semantically related players (inject their tier + WC stats)
      4. Find semantically related teams
      5. Pull all active/upcoming tournaments for current context
      6. Find related ongoing drama
    """
    text_to_embed = f"{news_item.get('title', '')} {news_item.get('description', '')}"
    embedding = encode(text_to_embed)
    news_item["embedding"] = embedding
    news_id = news_item.get("id")

    similar_news = await search_similar_news(
        session, embedding, top_k=5, exclude_id=str(news_id) if news_id else None
    )
    related_players = await search_similar_players(session, embedding, top_k=5)
    related_teams = await _search_similar_teams(session, embedding, top_k=3)
    related_drama = await search_similar_drama(session, embedding, top_k=3)
    relevant_quotes = await search_relevant_quotes(session, embedding, top_k=3)
    relevant_opinions = await search_relevant_opinions(session, embedding, top_k=3)
    active_tournaments = await _get_active_tournaments(session)

    return {
        "embedding": embedding,
        "similar_news": _format_news(similar_news),
        "related_players": _format_players(related_players),
        "related_teams": _format_teams(related_teams),
        "active_tournaments": _format_tournaments(active_tournaments),
        "related_drama": _format_drama(related_drama),
        "relevant_quotes": _format_quotes(relevant_quotes),
        "relevant_opinions": _format_opinions(relevant_opinions),
        "editorial_notes": editorial_notes or "",
    }


async def _search_similar_teams(session: AsyncSession, embedding: list[float], top_k: int = 3) -> list[dict]:
    from backend.embeddings.similarity import _rank_rows
    sql = text("""
        SELECT id, name, country, league, manager, world_cup_group, world_cup_status,
               playing_style, priority, notes, embedding
        FROM teams
        WHERE embedding IS NOT NULL
    """)
    try:
        result = await session.execute(sql)
        return _rank_rows([dict(r) for r in result.mappings().all()], embedding, top_k)
    except Exception as e:
        logger.warning("similarity search (teams) failed: %s", e)
        return []


async def _get_active_tournaments(session: AsyncSession) -> list[dict]:
    """Fetch Active and Upcoming tournaments for current-context injection."""
    try:
        from backend.database.models import Tournament
        result = await session.execute(
            select(Tournament).where(
                Tournament.status.in_(["Active", "Upcoming"])
            ).order_by(Tournament.status.asc(), Tournament.name.asc())
        )
        rows = result.scalars().all()
        return [r.to_dict() for r in rows]
    except Exception as e:
        logger.warning("active tournaments fetch failed: %s", e)
        return []


def _format_news(rows: list[dict]) -> str:
    if not rows:
        return "No similar past coverage found."
    lines = []
    for r in rows:
        sim = r.get("similarity", 0)
        if sim < 0.5:
            continue
        source = r.get("source", "")
        confidence = r.get("source_confidence", "trusted_news")
        lines.append(f"- [{confidence.upper()}] [{source}] {r.get('title', '')} (sim: {sim:.2f})")
    return "\n".join(lines) if lines else "No similar past coverage found."


def _format_players(rows: list[dict]) -> str:
    if not rows:
        return "No related players found."
    lines = []
    for r in rows:
        name = r.get("name", "")
        club = r.get("current_club", "") or "unknown club"
        tier = r.get("tier", "")
        apps = r.get("world_cup_appearances", 0) or 0
        goals = r.get("world_cup_goals", 0) or 0
        pos = r.get("position", "")
        nat = r.get("nationality", "")
        in_squad = r.get("world_cup_squad", False)
        market_val = r.get("market_value", "")
        content_angle = r.get("content_angle", "") or ""
        notes = r.get("notes", "") or ""

        # Club and age can be stale; tier/nationality/position are stable editorial facts.
        parts = [f"{name} [DB_HISTORICAL]"]
        if tier:
            parts.append(f"tier: {tier} [NOTION_EDITORIAL]")
        if club:
            parts.append(f"club: {club} [DB_HISTORICAL]")
        if pos:
            parts.append(pos)
        if nat:
            parts.append(nat)
        if apps:
            parts.append(f"{apps} WC apps [DB_HISTORICAL]")
        if goals:
            parts.append(f"{goals} WC goals [DB_HISTORICAL]")
        if in_squad:
            parts.append("in WC 2026 squad [DB_HISTORICAL]")
        if market_val:
            parts.append(f"value: {market_val} [DB_HISTORICAL]")
        if content_angle:
            parts.append(f"angles: {content_angle} [NOTION_EDITORIAL]")
        if notes:
            parts.append(f"notes: {notes[:100]} [NOTION_EDITORIAL]")
        lines.append("- " + " | ".join(parts))
    return "\n".join(lines)


def _format_teams(rows: list[dict]) -> str:
    if not rows:
        return "No related teams found."
    lines = []
    for r in rows:
        name = r.get("name", "")
        league = r.get("league", "")
        priority = r.get("priority", "")
        wc_status = r.get("world_cup_status", "")
        wc_group = r.get("world_cup_group", "")
        playing_style = r.get("playing_style", "") or ""
        notes = r.get("notes", "") or ""
        # Manager can change; WC group is stable once drawn.
        parts = [f"{name} [DB_HISTORICAL]"]
        if league:
            parts.append(f"league: {league}")
        if priority:
            parts.append(f"{priority} priority [NOTION_EDITORIAL]")
        if wc_group:
            parts.append(f"WC Group {wc_group} [DB_HISTORICAL]")
        if wc_status and wc_status != "TBC":
            parts.append(f"WC: {wc_status} [DB_HISTORICAL]")
        if playing_style:
            parts.append(f"style: {playing_style} [NOTION_EDITORIAL]")
        if notes:
            parts.append(f"notes: {notes[:100]} [NOTION_EDITORIAL]")
        lines.append("- " + " | ".join(parts))
    return "\n".join(lines)


def _format_tournaments(rows: list[dict]) -> str:
    if not rows:
        return ""
    lines = []
    for r in rows:
        name = r.get("name", "")
        status = r.get("status", "")
        stage = r.get("current_stage", "")
        leader = r.get("current_leader", "")
        top_scorer = r.get("top_scorer", "")
        defending = r.get("defending_champion", "")
        favourite = r.get("favourite_to_win", "")
        key_teams = r.get("key_teams", "") or ""
        key_players = r.get("key_players", "") or ""
        content_angles = r.get("content_angles", "") or ""
        matches_played = r.get("matches_played") or 0
        updated_at = r.get("updated_at", "")

        # Determine confidence for live data fields.
        # Notion editorial fields (defending champ, favourite, key teams) = NOTION_EDITORIAL.
        # Live-synced fields (stage, leader, top scorer) = LIVE_API if recently updated, else DB_HISTORICAL.
        live_confidence = "LIVE_API" if matches_played > 0 else "DB_HISTORICAL"

        parts = [f"{name} ({status})"]
        if stage:
            parts.append(f"Stage [{live_confidence}]: {stage}")
        if leader and (matches_played > 0 or status != "Upcoming"):
            parts.append(f"Leader [{live_confidence}]: {leader}")
        if matches_played:
            parts.append(f"Matches played [{live_confidence}]: {matches_played}")
        if top_scorer:
            parts.append(f"Top scorer [{live_confidence}]: {top_scorer}")
        if defending:
            parts.append(f"Defending champion [NOTION_EDITORIAL]: {defending}")
        if favourite:
            parts.append(f"Favourite [NOTION_EDITORIAL]: {favourite}")
        if key_teams:
            parts.append(f"Key teams [NOTION_EDITORIAL]: {key_teams}")
        if key_players:
            parts.append(f"Key players [NOTION_EDITORIAL]: {key_players}")
        if content_angles:
            parts.append(f"Content angles [NOTION_EDITORIAL]: {content_angles}")
        if updated_at:
            parts.append(f"DB updated: {updated_at}")
        lines.append("- " + " | ".join(parts))
    return "\n".join(lines)


def _format_drama(rows: list[dict]) -> str:
    if not rows:
        return "No related drama entries found."
    lines = []
    for r in rows:
        severity = (r.get("severity") or "").upper()
        title = r.get("title", "")
        status = r.get("status", "")
        summary = (r.get("summary") or "")[:100]
        # Drama is NOTION_EDITORIAL - manually curated background context, may be stale.
        line = f"- [{severity}] {title} ({status}) [NOTION_EDITORIAL]"
        if summary:
            line += f" - {summary}"
        lines.append(line)
    return "\n".join(lines)


def _format_quotes(rows: list[dict]) -> str:
    if not rows:
        return "No relevant press conference quotes found."
    lines = []
    for r in rows:
        sim = r.get("similarity", 0)
        if sim < 0.35:
            continue
        speaker = r.get("speaker") or "Unknown"
        score = r.get("controversy_score") or 0
        quote = r.get("exact_quote") or ""
        context = r.get("match_context") or ""
        comments = _summarise_comments(r.get("top_comments"))
        line = f"- [OFFICIAL_QUOTE] score {score} | {speaker}: \"{quote}\""
        if context:
            line += f" | context: {context}"
        if comments:
            line += f" | fan comments: {comments}"
        lines.append(line)
    return "\n".join(lines) if lines else "No relevant press conference quotes found."


def _format_opinions(rows: list[dict]) -> str:
    if not rows:
        return "No relevant pundit opinions found."
    lines = []
    for r in rows:
        sim = r.get("similarity", 0)
        if sim < 0.35:
            continue
        speaker = r.get("original_speaker") or "Unknown"
        score = r.get("controversy_score") or 0
        opinion = r.get("opinion_text") or ""
        tags = r.get("topic_tags") or ""
        stance = r.get("stance") or ""
        comments = _summarise_comments(r.get("top_comments"))
        line = f"- [TRUSTED_OPINION] score {score} | {speaker}: {opinion}"
        if stance:
            line += f" | stance: {stance}"
        if tags:
            line += f" | tags: {tags}"
        if comments:
            line += f" | fan comments: {comments}"
        lines.append(line)
    return "\n".join(lines) if lines else "No relevant pundit opinions found."


def _summarise_comments(raw) -> str:
    if not raw:
        return ""
    try:
        import json
        comments = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(comments, list):
            return " || ".join(str(c)[:120] for c in comments[:3] if c)
    except Exception:
        return str(raw)[:180]
    return ""
