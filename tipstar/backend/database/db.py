"""
Async SQLAlchemy session management and all database operations.
Uses asyncpg driver for async I/O compatible with FastAPI.
"""
import json
import logging
import os
from email.utils import parsedate_to_datetime
from datetime import datetime, date
from typing import Optional

from sqlalchemy import func, and_, select, update, delete, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.database.models import (
    Base,
    Drama,
    Match,
    News,
    Opinion,
    Player,
    Post,
    PostStatus,
    PostType,
    PressConference,
    Team,
    Tournament,
)

logger = logging.getLogger(__name__)

_engine = None
_AsyncSessionLocal = None

# Maps Groq JSON keys to PostType enum values
_POST_TYPE_MAP = {
    "post_a": PostType.hot_take,
    "post_b": PostType.data_stats,
    "post_c": PostType.tactical,
    "post_d": PostType.wc_narrative,
}


def _build_async_url(sync_url: str) -> str:
    """Convert psycopg2 URL to asyncpg URL."""
    return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)


def get_engine():
    global _engine
    if _engine is not None:
        return _engine

    from dotenv import load_dotenv
    load_dotenv()

    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL is not set")

    async_url = _build_async_url(db_url)
    _engine = create_async_engine(
        async_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=False,
    )
    return _engine


def get_session_factory() -> async_sessionmaker:
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _AsyncSessionLocal = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _AsyncSessionLocal


async def get_db():
    """FastAPI dependency: yields an async DB session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Create all tables and apply additive schema fixes."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_runtime_schema(conn)
    logger.info("Database tables initialised")


async def _ensure_runtime_schema(conn) -> None:
    """
    Supabase already has production tables, and create_all() will not add new
    columns to them. Keep this additive only: no drops, rewrites, or type
    changes that could damage existing data.
    """
    statements = [
        "ALTER TABLE posts ADD COLUMN IF NOT EXISTS source_url VARCHAR(500)",
        "ALTER TABLE posts ADD COLUMN IF NOT EXISTS source_name VARCHAR(200)",
        "ALTER TABLE posts ADD COLUMN IF NOT EXISTS published_at VARCHAR(100)",
        "ALTER TABLE posts ADD COLUMN IF NOT EXISTS image_path VARCHAR(500)",
        "ALTER TABLE news ADD COLUMN IF NOT EXISTS source_confidence VARCHAR(50) DEFAULT 'trusted_news'",
        "ALTER TABLE players ADD COLUMN IF NOT EXISTS world_cup_squad BOOLEAN DEFAULT false",
        "ALTER TABLE players ADD COLUMN IF NOT EXISTS market_value VARCHAR(50)",
        "ALTER TABLE players ADD COLUMN IF NOT EXISTS instagram_followers VARCHAR(50)",
        "ALTER TABLE players ADD COLUMN IF NOT EXISTS content_angle TEXT",
        """
        CREATE TABLE IF NOT EXISTS tournaments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL UNIQUE,
            type VARCHAR(100),
            status VARCHAR(50),
            host_country VARCHAR(200),
            start_date DATE,
            end_date DATE,
            total_teams INTEGER,
            total_matches INTEGER,
            matches_played INTEGER,
            current_stage VARCHAR(100),
            defending_champion VARCHAR(200),
            current_leader VARCHAR(200),
            favourite_to_win VARCHAR(200),
            top_scorer VARCHAR(200),
            key_teams TEXT,
            key_players TEXT,
            coverage_priority VARCHAR(50),
            content_angles TEXT,
            notes TEXT,
            updated_at TIMESTAMP DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS opinions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_channel TEXT,
            video_title TEXT,
            video_id TEXT,
            opinion_text TEXT NOT NULL,
            original_speaker VARCHAR(200),
            stance VARCHAR(50),
            controversy_score INTEGER,
            topic_tags TEXT,
            players_mentioned TEXT,
            top_comments TEXT,
            embedding TEXT,
            created_at TIMESTAMP DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_opinions_video_id ON opinions(video_id)",
        """
        CREATE TABLE IF NOT EXISTS press_conferences (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_channel TEXT,
            video_title TEXT,
            video_id TEXT,
            speaker VARCHAR(200),
            speaker_role VARCHAR(100),
            club_or_nation VARCHAR(200),
            exact_quote TEXT NOT NULL,
            quote_category VARCHAR(100),
            controversy_score INTEGER,
            top_comments TEXT,
            match_context TEXT,
            tournament VARCHAR(200),
            embedding TEXT,
            created_at TIMESTAMP DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_press_conferences_video_id ON press_conferences(video_id)",
    ]
    for statement in statements:
        await conn.execute(text(statement))


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

async def insert_news(session: AsyncSession, item: dict) -> Optional[News]:
    """Insert a harvested news item. Returns None if URL already exists."""
    existing = await session.scalar(select(News).where(News.url == item.get("url")))
    if existing:
        return None

    news = News(
        title=item.get("title", ""),
        content=item.get("description", ""),
        source=item.get("source", ""),
        source_confidence=item.get("source_confidence", "trusted_news"),
        url=item.get("url"),
        published_at=_parse_dt(item.get("published_at")),
        relevance_score=item.get("relevance_score"),
        is_world_cup=item.get("is_world_cup", False),
        embedding=json.dumps(item.get("embedding")) if item.get("embedding") else None,
    )
    session.add(news)
    await session.flush()
    return news


async def get_news_page(session: AsyncSession, page: int = 1, size: int = 20) -> list[dict]:
    offset = (page - 1) * size
    result = await session.execute(
        select(News).order_by(News.created_at.desc()).offset(offset).limit(size)
    )
    return [r.to_dict() for r in result.scalars().all()]


async def get_news_by_id(session: AsyncSession, news_id: str) -> Optional[dict]:
    result = await session.get(News, news_id)
    return result.to_dict() if result else None


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------

async def insert_posts(session: AsyncSession, generated: dict, news_id=None) -> int:
    """Insert all post variants from a Groq-generated bundle. Returns count inserted."""
    story_title = generated.get("story_title", "")
    relevance_score = int(generated.get("relevance_score", 0))
    is_world_cup = bool(generated.get("is_world_cup", False))

    rows = []
    for key, post_type in _POST_TYPE_MAP.items():
        post_data = generated.get(key)
        if not post_data:
            continue
        content = (post_data.get("content") or "").strip()
        if not content:
            continue
        hashtags_raw = post_data.get("hashtags", [])
        hashtags = ", ".join(hashtags_raw) if isinstance(hashtags_raw, list) else (hashtags_raw or "")
        emb = post_data.get("embedding")
        rows.append(Post(
            news_id=news_id,
            story_title=story_title,
            relevance_score=relevance_score,
            is_world_cup=is_world_cup,
            post_type=post_type,
            content=content,
            hashtags=hashtags,
            best_time=post_data.get("best_time", ""),
            status=PostStatus.pending,
            embedding=json.dumps(emb) if emb else None,
        ))

    if not rows:
        return 0

    session.add_all(rows)
    await session.flush()
    logger.info(f"Inserted {len(rows)} posts for: {story_title}")
    return len(rows)


async def get_posts_by_status(session: AsyncSession, status: str) -> list[dict]:
    result = await session.execute(
        select(Post)
        .where(Post.status == PostStatus(status))
        .order_by(Post.relevance_score.desc(), Post.created_at.desc())
    )
    return [r.to_dict() for r in result.scalars().all()]


async def get_posts(session: AsyncSession, status: Optional[str] = None) -> list[dict]:
    query = select(Post)
    if status:
        query = query.where(Post.status == PostStatus(status))
    query = query.order_by(Post.created_at.desc())
    result = await session.execute(query)
    return [r.to_dict() for r in result.scalars().all()]


async def get_post_history(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        select(Post).where(Post.status == PostStatus.posted).order_by(Post.posted_at.desc())
    )
    return [r.to_dict() for r in result.scalars().all()]


async def update_post_status(
    session: AsyncSession,
    post_id: str,
    status: str,
    content: Optional[str] = None,
) -> Optional[dict]:
    result = await session.execute(select(Post).where(Post.id == int(post_id)))
    post = result.scalar_one_or_none()
    if not post:
        return None
    post.status = PostStatus(status)
    if content is not None:
        post.content = content
    if status == "posted":
        post.posted_at = datetime.utcnow()
    await session.flush()
    return post.to_dict()


async def set_post_image_path(session: AsyncSession, post_id: str, image_path: str) -> Optional[dict]:
    result = await session.execute(select(Post).where(Post.id == int(post_id)))
    post = result.scalar_one_or_none()
    if not post:
        return None
    post.image_path = image_path
    await session.flush()
    return post.to_dict()


async def delete_post(session: AsyncSession, post_id: str) -> bool:
    result = await session.execute(select(Post).where(Post.id == int(post_id)))
    post = result.scalar_one_or_none()
    if not post:
        return False
    await session.delete(post)
    await session.flush()
    return True


async def get_approved_unposted(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        select(Post).where(
            and_(Post.status == PostStatus.approved, Post.posted_at.is_(None))
        ).order_by(Post.created_at.asc())
    )
    return [r.to_dict() for r in result.scalars().all()]


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------

async def upsert_player(session: AsyncSession, data: dict) -> Player:
    """Insert or update a player by name."""
    result = await session.execute(select(Player).where(Player.name == data.get("name")))
    player = result.scalar_one_or_none()
    if not player:
        player = Player()
        session.add(player)
    for field in ["name", "nationality", "current_club", "position", "tier",
                  "age", "world_cup_appearances", "world_cup_goals", "status",
                  "world_cup_squad", "market_value", "instagram_followers",
                  "content_angle", "notes"]:
        if field in data:
            # content_angle may come in as a list from Notion multi-select
            val = data[field]
            if field == "content_angle" and isinstance(val, list):
                val = ", ".join(str(v) for v in val if v)
            setattr(player, field, val)
    if data.get("embedding"):
        player.embedding = json.dumps(data["embedding"])
    player.updated_at = datetime.utcnow()
    await session.flush()
    return player


async def get_all_players(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(Player).order_by(Player.name))
    return [r.to_dict() for r in result.scalars().all()]


async def get_player_by_id(session: AsyncSession, player_id: str) -> Optional[dict]:
    result = await session.get(Player, player_id)
    return result.to_dict() if result else None


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

async def upsert_team(session: AsyncSession, data: dict) -> Team:
    result = await session.execute(select(Team).where(Team.name == data.get("name")))
    team = result.scalar_one_or_none()
    if not team:
        team = Team()
        session.add(team)
    for field in ["name", "country", "league", "manager", "world_cup_group",
                  "world_cup_status", "playing_style", "priority", "notes"]:
        if field in data:
            setattr(team, field, data[field])
    if data.get("embedding"):
        team.embedding = json.dumps(data["embedding"])
    team.updated_at = datetime.utcnow()
    await session.flush()
    return team


async def get_all_teams(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(Team).order_by(Team.name))
    return [r.to_dict() for r in result.scalars().all()]


async def get_team_by_id(session: AsyncSession, team_id: str) -> Optional[dict]:
    result = await session.get(Team, team_id)
    return result.to_dict() if result else None


async def delete_player(session: AsyncSession, player_id: str) -> bool:
    result = await session.execute(select(Player).where(Player.id == player_id))
    player = result.scalar_one_or_none()
    if not player:
        return False
    await session.delete(player)
    await session.flush()
    return True


async def delete_team(session: AsyncSession, team_id: str) -> bool:
    result = await session.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        return False
    await session.delete(team)
    await session.flush()
    return True


# ---------------------------------------------------------------------------
# Tournaments
# ---------------------------------------------------------------------------

def _parse_date(value) -> Optional[date]:
    """Convert ISO string or date/datetime to a date object."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


async def upsert_tournament(session: AsyncSession, data: dict) -> Tournament:
    result = await session.execute(select(Tournament).where(Tournament.name == data.get("name")))
    tournament = result.scalar_one_or_none()
    if not tournament:
        tournament = Tournament()
        session.add(tournament)
    for field in [
        "name", "type", "status", "host_country",
        "total_teams", "total_matches", "matches_played", "current_stage",
        "defending_champion", "current_leader", "favourite_to_win", "top_scorer",
        "key_teams", "key_players", "coverage_priority", "content_angles", "notes",
    ]:
        if field in data and data[field] is not None:
            setattr(tournament, field, data[field])
    # Date fields need explicit parsing from ISO strings
    if data.get("start_date") is not None:
        tournament.start_date = _parse_date(data["start_date"])
    if data.get("end_date") is not None:
        tournament.end_date = _parse_date(data["end_date"])
    tournament.updated_at = datetime.utcnow()
    await session.flush()
    return tournament


async def get_all_tournaments(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(Tournament).order_by(Tournament.name))
    return [r.to_dict() for r in result.scalars().all()]


async def delete_tournament(session: AsyncSession, tournament_id: str) -> bool:
    result = await session.execute(select(Tournament).where(Tournament.id == tournament_id))
    t = result.scalar_one_or_none()
    if not t:
        return False
    await session.delete(t)
    await session.flush()
    return True


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------

async def insert_match(session: AsyncSession, data: dict) -> Match:
    match = Match(
        home_team=data.get("home_team"),
        away_team=data.get("away_team"),
        home_score=data.get("home_score"),
        away_score=data.get("away_score"),
        stage=data.get("stage"),
        tournament=data.get("tournament"),
        venue=data.get("venue"),
        match_date=_parse_dt(data.get("match_date")),
        scorers=data.get("scorers"),
        key_events=data.get("key_events"),
        coverage_status=data.get("coverage_status", "Not Covered"),
    )
    if data.get("embedding"):
        match.embedding = json.dumps(data["embedding"])
    session.add(match)
    await session.flush()
    return match


async def get_all_matches(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(Match).order_by(Match.match_date.desc()))
    return [r.to_dict() for r in result.scalars().all()]


async def get_match_by_id(session: AsyncSession, match_id: str) -> Optional[dict]:
    result = await session.get(Match, match_id)
    return result.to_dict() if result else None


# ---------------------------------------------------------------------------
# Drama
# ---------------------------------------------------------------------------

async def insert_drama(session: AsyncSession, data: dict) -> Drama:
    drama = Drama(
        title=data.get("title"),
        players_involved=data.get("players_involved"),
        teams_involved=data.get("teams_involved"),
        category=data.get("category"),
        severity=data.get("severity"),
        summary=data.get("summary"),
        status=data.get("status", "Ongoing"),
        source=data.get("source"),
        drama_date=_parse_date(data.get("drama_date")),
    )
    if data.get("embedding"):
        drama.embedding = json.dumps(data["embedding"])
    session.add(drama)
    await session.flush()
    return drama


async def upsert_drama(session: AsyncSession, data: dict) -> Drama:
    """Insert or update a drama row by title."""
    result = await session.execute(select(Drama).where(Drama.title == data.get("title")))
    drama = result.scalar_one_or_none()
    if not drama:
        drama = Drama()
        session.add(drama)
    for field in [
        "title", "players_involved", "teams_involved", "category",
        "severity", "summary", "status", "source",
    ]:
        if field in data:
            setattr(drama, field, data[field])
    if "drama_date" in data:
        drama.drama_date = _parse_date(data.get("drama_date"))
    if data.get("embedding"):
        drama.embedding = json.dumps(data["embedding"])
    await session.flush()
    return drama


async def get_all_drama(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(Drama).order_by(Drama.created_at.desc()))
    return [r.to_dict() for r in result.scalars().all()]


async def get_drama_by_id(session: AsyncSession, drama_id: str) -> Optional[dict]:
    result = await session.get(Drama, drama_id)
    return result.to_dict() if result else None


# ---------------------------------------------------------------------------
# YouTube Intelligence
# ---------------------------------------------------------------------------

async def youtube_video_exists(session: AsyncSession, video_id: str) -> bool:
    opinion_count = await session.scalar(
        select(func.count(Opinion.id)).where(Opinion.video_id == video_id)
    )
    quote_count = await session.scalar(
        select(func.count(PressConference.id)).where(PressConference.video_id == video_id)
    )
    return bool((opinion_count or 0) + (quote_count or 0))


async def insert_opinion(session: AsyncSession, data: dict) -> Opinion:
    opinion = Opinion(
        source_channel=data.get("source_channel"),
        video_title=data.get("video_title"),
        video_id=data.get("video_id"),
        opinion_text=data.get("opinion_text", ""),
        original_speaker=data.get("original_speaker"),
        stance=data.get("stance"),
        controversy_score=data.get("controversy_score"),
        topic_tags=data.get("topic_tags"),
        players_mentioned=data.get("players_mentioned"),
        top_comments=json.dumps(data.get("top_comments", []), ensure_ascii=False),
        embedding=json.dumps(data.get("embedding")) if data.get("embedding") else None,
    )
    session.add(opinion)
    await session.flush()
    return opinion


async def insert_press_conference_quote(session: AsyncSession, data: dict) -> PressConference:
    quote = PressConference(
        source_channel=data.get("source_channel"),
        video_title=data.get("video_title"),
        video_id=data.get("video_id"),
        speaker=data.get("speaker"),
        speaker_role=data.get("speaker_role"),
        club_or_nation=data.get("club_or_nation"),
        exact_quote=data.get("exact_quote", ""),
        quote_category=data.get("quote_category"),
        controversy_score=data.get("controversy_score"),
        top_comments=json.dumps(data.get("top_comments", []), ensure_ascii=False),
        match_context=data.get("match_context"),
        tournament=data.get("tournament"),
        embedding=json.dumps(data.get("embedding")) if data.get("embedding") else None,
    )
    session.add(quote)
    await session.flush()
    return quote


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

async def get_analytics_summary(session: AsyncSession) -> dict:
    today = date.today()

    total_today = await session.scalar(
        select(func.count(Post.id)).where(func.date(Post.created_at) == today)
    )
    approved = await session.scalar(
        select(func.count(Post.id)).where(Post.status.in_([PostStatus.approved, PostStatus.posted]))
    )
    rejected = await session.scalar(
        select(func.count(Post.id)).where(Post.status == PostStatus.rejected)
    )
    wc_total = await session.scalar(
        select(func.count(Post.id)).where(Post.is_world_cup == True)
    )
    regular_total = await session.scalar(
        select(func.count(Post.id)).where(Post.is_world_cup == False)
    )
    top_type_row = (await session.execute(
        select(Post.post_type, func.count(Post.id).label("cnt"))
        .where(Post.status.in_([PostStatus.approved, PostStatus.posted]))
        .group_by(Post.post_type)
        .order_by(func.count(Post.id).desc())
        .limit(1)
    )).first()

    return {
        "total_today": total_today or 0,
        "approved": approved or 0,
        "rejected": rejected or 0,
        "world_cup": wc_total or 0,
        "regular": regular_total or 0,
        "top_post_type": (top_type_row[0].value if isinstance(top_type_row[0], PostType) else top_type_row[0]) if top_type_row else "N/A",
    }


async def get_post_type_breakdown(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        select(Post.post_type, func.count(Post.id).label("count"))
        .group_by(Post.post_type)
    )
    return [{"type": row[0].value if row[0] else row[0], "count": row[1]} for row in result.all()]


async def get_posts_over_time(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        select(func.date(Post.created_at).label("day"), func.count(Post.id).label("count"))
        .group_by(func.date(Post.created_at))
        .order_by(func.date(Post.created_at))
    )
    return [{"date": str(row[0]), "count": row[1]} for row in result.all()]


async def get_coverage_ratio(session: AsyncSession) -> dict:
    wc = await session.scalar(select(func.count(Post.id)).where(Post.is_world_cup == True))
    reg = await session.scalar(select(func.count(Post.id)).where(Post.is_world_cup == False))
    return {"world_cup": wc or 0, "regular": reg or 0}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        pass
    try:
        return parsedate_to_datetime(str(value))
    except Exception:
        return None


def _parse_date(value):
    if not value:
        return None
    try:
        from datetime import date as date_type
        if isinstance(value, date_type):
            return value
        return date.fromisoformat(str(value))
    except Exception:
        return None
