"""
002_sync_tables

Adds four tables required by the API sync layer:
  - world_cup_groups   (group standings per nation)
  - world_cup_squads   (squad lists per nation)
  - settings           (key/value flags, e.g. match_day)
  - sync_logs          (per-run audit trail)
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "world_cup_groups",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("group_name", sa.Text(), nullable=False),
        sa.Column("team", sa.Text(), nullable=False),
        sa.Column("played", sa.Integer(), default=0),
        sa.Column("won", sa.Integer(), default=0),
        sa.Column("drawn", sa.Integer(), default=0),
        sa.Column("lost", sa.Integer(), default=0),
        sa.Column("goals_for", sa.Integer(), default=0),
        sa.Column("goals_against", sa.Integer(), default=0),
        sa.Column("goal_difference", sa.Integer(), default=0),
        sa.Column("points", sa.Integer(), default=0),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_wc_groups_team", "world_cup_groups", ["team"])

    op.create_table(
        "world_cup_squads",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("nation", sa.Text(), nullable=False),
        sa.Column("player_name", sa.Text(), nullable=False),
        sa.Column("club", sa.Text()),
        sa.Column("position", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_wc_squads_nation", "world_cup_squads", ["nation"])

    op.create_table(
        "settings",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    op.create_table(
        "sync_logs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("sync_type", sa.Text()),
        sa.Column("api_used", sa.Text()),
        sa.Column("records_updated", sa.Integer()),
        sa.Column("errors", sa.Integer()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_sync_logs_type", "sync_logs", ["sync_type"])
    op.create_index("idx_sync_logs_created", "sync_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("sync_logs")
    op.drop_table("settings")
    op.drop_table("world_cup_squads")
    op.drop_table("world_cup_groups")
