"""
SQLAlchemy ORM models for the TipStar football intelligence platform.
All tables mirror the Supabase schema defined in the Alembic migration.
pgvector columns are stored as Text (JSON-serialised) when pgvector extension
is not available locally; the migration creates the proper VECTOR columns in Supabase.
"""
import enum
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey,
    Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship
import uuid


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PostStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    posted = "posted"


class PostType(str, enum.Enum):
    hot_take = "hot_take"
    data_stats = "data_stats"
    tactical = "tactical"
    wc_narrative = "wc_narrative"


class PlayerTier(str, enum.Enum):
    tier1 = "tier1"
    tier2 = "tier2"
    tier3 = "tier3"


class DramaSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

class News(Base):
    __tablename__ = "news"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text, nullable=False)
    content = Column(Text)
    source = Column(String(200))
    url = Column(Text, unique=True)
    published_at = Column(DateTime)
    relevance_score = Column(Integer)
    is_world_cup = Column(Boolean, default=False)
    embedding = Column(Text)  # JSON-serialised float list; VECTOR(384) in Supabase
    created_at = Column(DateTime, default=datetime.utcnow)

    posts = relationship("Post", back_populates="news_item")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "relevance_score": self.relevance_score,
            "is_world_cup": self.is_world_cup,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------

class Post(Base):
    __tablename__ = "posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    news_id = Column(UUID(as_uuid=True), ForeignKey("news.id"), nullable=True)
    story_title = Column(Text)
    relevance_score = Column(Integer)
    is_world_cup = Column(Boolean, default=False)
    post_type = Column(
        Enum(PostType, name="post_type_enum", create_constraint=True),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    hashtags = Column(String(500))
    best_time = Column(String(200))
    status = Column(
        Enum(PostStatus, name="post_status_enum", create_constraint=True),
        default=PostStatus.pending,
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    posted_at = Column(DateTime, nullable=True)
    embedding = Column(Text)  # JSON-serialised; VECTOR(384) in Supabase

    news_item = relationship("News", back_populates="posts")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "news_id": str(self.news_id) if self.news_id else None,
            "story_title": self.story_title,
            "relevance_score": self.relevance_score,
            "is_world_cup": self.is_world_cup,
            "post_type": self.post_type.value if isinstance(self.post_type, PostType) else self.post_type,
            "content": self.content,
            "hashtags": self.hashtags,
            "best_time": self.best_time,
            "status": self.status.value if isinstance(self.status, PostStatus) else self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
        }


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------

class Player(Base):
    __tablename__ = "players"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    nationality = Column(String(100))
    current_club = Column(String(200))
    position = Column(String(100))
    tier = Column(String(50))
    age = Column(Integer)
    world_cup_appearances = Column(Integer, default=0)
    world_cup_goals = Column(Integer, default=0)
    status = Column(String(50), default="Active")
    notes = Column(Text)
    embedding = Column(Text)  # VECTOR(384) in Supabase
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "nationality": self.nationality,
            "current_club": self.current_club,
            "position": self.position,
            "tier": self.tier,
            "age": self.age,
            "world_cup_appearances": self.world_cup_appearances,
            "world_cup_goals": self.world_cup_goals,
            "status": self.status,
            "notes": self.notes,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

class Team(Base):
    __tablename__ = "teams"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    country = Column(String(100))
    league = Column(String(200))
    manager = Column(String(200))
    world_cup_group = Column(String(10))
    world_cup_status = Column(String(100), default="TBC")
    playing_style = Column(Text)
    priority = Column(String(50))
    notes = Column(Text)
    embedding = Column(Text)  # VECTOR(384) in Supabase
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "country": self.country,
            "league": self.league,
            "manager": self.manager,
            "world_cup_group": self.world_cup_group,
            "world_cup_status": self.world_cup_status,
            "playing_style": self.playing_style,
            "priority": self.priority,
            "notes": self.notes,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------

class Match(Base):
    __tablename__ = "matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    home_team = Column(String(200))
    away_team = Column(String(200))
    home_score = Column(Integer)
    away_score = Column(Integer)
    stage = Column(String(100))
    tournament = Column(String(200))
    venue = Column(String(200))
    match_date = Column(DateTime)
    scorers = Column(Text)
    key_events = Column(Text)
    coverage_status = Column(String(50), default="Not Covered")
    embedding = Column(Text)  # VECTOR(384) in Supabase
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "home_team": self.home_team,
            "away_team": self.away_team,
            "home_score": self.home_score,
            "away_score": self.away_score,
            "stage": self.stage,
            "tournament": self.tournament,
            "venue": self.venue,
            "match_date": self.match_date.isoformat() if self.match_date else None,
            "scorers": self.scorers,
            "key_events": self.key_events,
            "coverage_status": self.coverage_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Drama
# ---------------------------------------------------------------------------

class Drama(Base):
    __tablename__ = "drama"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text, nullable=False)
    players_involved = Column(Text)
    teams_involved = Column(Text)
    category = Column(String(100))
    severity = Column(String(50))
    summary = Column(Text)
    status = Column(String(50), default="Ongoing")
    source = Column(Text)
    drama_date = Column(Date)
    embedding = Column(Text)  # VECTOR(384) in Supabase
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "title": self.title,
            "players_involved": self.players_involved,
            "teams_involved": self.teams_involved,
            "category": self.category,
            "severity": self.severity,
            "summary": self.summary,
            "status": self.status,
            "source": self.source,
            "drama_date": self.drama_date.isoformat() if self.drama_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
