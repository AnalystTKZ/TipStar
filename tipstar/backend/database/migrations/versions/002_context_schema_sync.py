"""Add context fields used by Notion and generation.

Revision ID: 003_context_schema_sync
Revises: 002
Create Date: 2026-05-22
"""
from alembic import op

revision = "003_context_schema_sync"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS source_url VARCHAR(500)")
    op.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS source_name VARCHAR(200)")
    op.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS published_at VARCHAR(100)")
    op.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS image_path VARCHAR(500)")
    op.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS caption TEXT")
    op.execute("ALTER TABLE news ADD COLUMN IF NOT EXISTS source_confidence VARCHAR(50) DEFAULT 'trusted_news'")

    op.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS world_cup_squad BOOLEAN DEFAULT false")
    op.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS market_value VARCHAR(50)")
    op.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS instagram_followers VARCHAR(50)")
    op.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS content_angle TEXT")

    op.execute("""
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
    """)
    op.execute("""
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
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_opinions_video_id ON opinions(video_id)")
    op.execute("""
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
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_press_conferences_video_id ON press_conferences(video_id)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS fact_claims (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            news_id UUID REFERENCES news(id) ON DELETE SET NULL,
            claim_text TEXT NOT NULL,
            normalized_claim TEXT NOT NULL UNIQUE,
            claim_type VARCHAR(100),
            entity_type VARCHAR(100),
            entities TEXT,
            temporal_scope VARCHAR(50),
            source VARCHAR(200),
            source_confidence VARCHAR(50),
            source_url TEXT,
            status VARCHAR(50) DEFAULT 'candidate',
            confidence_score INTEGER DEFAULT 0,
            evidence_count INTEGER DEFAULT 1,
            evidence_urls TEXT,
            embedding TEXT,
            first_seen_at TIMESTAMP DEFAULT now(),
            last_seen_at TIMESTAMP DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_fact_claims_status ON fact_claims(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_fact_claims_claim_type ON fact_claims(claim_type)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tournaments")
    op.execute("DROP TABLE IF EXISTS fact_claims")
    op.execute("DROP TABLE IF EXISTS press_conferences")
    op.execute("DROP TABLE IF EXISTS opinions")
    op.execute("ALTER TABLE players DROP COLUMN IF EXISTS content_angle")
    op.execute("ALTER TABLE players DROP COLUMN IF EXISTS instagram_followers")
    op.execute("ALTER TABLE players DROP COLUMN IF EXISTS market_value")
    op.execute("ALTER TABLE players DROP COLUMN IF EXISTS world_cup_squad")
    op.execute("ALTER TABLE posts DROP COLUMN IF EXISTS image_path")
    op.execute("ALTER TABLE posts DROP COLUMN IF EXISTS caption")
    op.execute("ALTER TABLE news DROP COLUMN IF EXISTS source_confidence")
    op.execute("ALTER TABLE posts DROP COLUMN IF EXISTS published_at")
    op.execute("ALTER TABLE posts DROP COLUMN IF EXISTS source_name")
    op.execute("ALTER TABLE posts DROP COLUMN IF EXISTS source_url")
