"""Initial schema with pgvector support.

Revision ID: 001
Revises:
Create Date: 2026-05-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "news",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("content", sa.Text),
        sa.Column("source", sa.String(200)),
        sa.Column("url", sa.Text, unique=True),
        sa.Column("published_at", sa.DateTime),
        sa.Column("relevance_score", sa.Integer),
        sa.Column("is_world_cup", sa.Boolean, server_default="false"),
        sa.Column("embedding", sa.Text),  # populated as VECTOR below
        sa.Column("created_at", sa.DateTime, server_default=sa.text("NOW()")),
    )
    op.execute("ALTER TABLE news ALTER COLUMN embedding TYPE vector(384) USING embedding::vector")

    op.create_table(
        "posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("news_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("news.id")),
        sa.Column("story_title", sa.Text),
        sa.Column("relevance_score", sa.Integer),
        sa.Column("is_world_cup", sa.Boolean, server_default="false"),
        sa.Column("post_type", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("hashtags", sa.String(500)),
        sa.Column("best_time", sa.String(200)),
        sa.Column("status", sa.Text, server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("NOW()")),
        sa.Column("posted_at", sa.DateTime),
        sa.Column("embedding", sa.Text),
    )
    op.execute("ALTER TABLE posts ALTER COLUMN embedding TYPE vector(384) USING embedding::vector")

    op.create_table(
        "players",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("nationality", sa.String(100)),
        sa.Column("current_club", sa.String(200)),
        sa.Column("position", sa.String(100)),
        sa.Column("tier", sa.String(50)),
        sa.Column("age", sa.Integer),
        sa.Column("world_cup_appearances", sa.Integer, server_default="0"),
        sa.Column("world_cup_goals", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(50), server_default="Active"),
        sa.Column("notes", sa.Text),
        sa.Column("embedding", sa.Text),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("NOW()")),
    )
    op.execute("ALTER TABLE players ALTER COLUMN embedding TYPE vector(384) USING embedding::vector")

    op.create_table(
        "teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("country", sa.String(100)),
        sa.Column("league", sa.String(200)),
        sa.Column("manager", sa.String(200)),
        sa.Column("world_cup_group", sa.String(10)),
        sa.Column("world_cup_status", sa.String(100), server_default="TBC"),
        sa.Column("playing_style", sa.Text),
        sa.Column("priority", sa.String(50)),
        sa.Column("notes", sa.Text),
        sa.Column("embedding", sa.Text),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("NOW()")),
    )
    op.execute("ALTER TABLE teams ALTER COLUMN embedding TYPE vector(384) USING embedding::vector")

    op.create_table(
        "matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("home_team", sa.String(200)),
        sa.Column("away_team", sa.String(200)),
        sa.Column("home_score", sa.Integer),
        sa.Column("away_score", sa.Integer),
        sa.Column("stage", sa.String(100)),
        sa.Column("tournament", sa.String(200)),
        sa.Column("venue", sa.String(200)),
        sa.Column("match_date", sa.DateTime),
        sa.Column("scorers", sa.Text),
        sa.Column("key_events", sa.Text),
        sa.Column("coverage_status", sa.String(50), server_default="Not Covered"),
        sa.Column("embedding", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("NOW()")),
    )
    op.execute("ALTER TABLE matches ALTER COLUMN embedding TYPE vector(384) USING embedding::vector")

    op.create_table(
        "drama",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("players_involved", sa.Text),
        sa.Column("teams_involved", sa.Text),
        sa.Column("category", sa.String(100)),
        sa.Column("severity", sa.String(50)),
        sa.Column("summary", sa.Text),
        sa.Column("status", sa.String(50), server_default="Ongoing"),
        sa.Column("source", sa.Text),
        sa.Column("drama_date", sa.Date),
        sa.Column("embedding", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("NOW()")),
    )
    op.execute("ALTER TABLE drama ALTER COLUMN embedding TYPE vector(384) USING embedding::vector")

    # Indexes for similarity search (cosine)
    op.execute("CREATE INDEX IF NOT EXISTS idx_news_embedding ON news USING ivfflat (embedding vector_cosine_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_players_embedding ON players USING ivfflat (embedding vector_cosine_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_drama_embedding ON drama USING ivfflat (embedding vector_cosine_ops)")


def downgrade() -> None:
    op.drop_table("drama")
    op.drop_table("matches")
    op.drop_table("teams")
    op.drop_table("players")
    op.drop_table("posts")
    op.drop_table("news")
