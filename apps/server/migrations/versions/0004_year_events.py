"""Historical clues, including the initial sourced event catalog.

Revision ID: 0004
Revises: 0003
"""

import json
from datetime import date
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "year_events",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("year BETWEEN 1900 AND 2100", name="year_events_year_range"),
        sa.CheckConstraint("EXTRACT(YEAR FROM occurred_on) = year", name="year_events_date_matches_year"),
        sa.CheckConstraint("category IN ('sport','politics','music','conflict','science','culture','society')", name="year_events_category"),
        sa.CheckConstraint("length(text) BETWEEN 10 AND 240 AND text !~ '\\m[0-9]{4}\\M'", name="year_events_hint_text"),
        sa.CheckConstraint("source_url LIKE 'https://%'", name="year_events_source_https"),
    )
    op.create_index("year_events_enabled_year_idx", "year_events", ["enabled", "year"])
    # Alembic's revision transaction runs this once; redeploying does not overwrite curated edits.
    path = Path(__file__).resolve().parents[4] / "catalog" / "year_events.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    for row in rows:
        row["occurred_on"] = date.fromisoformat(row["occurred_on"])
    events = sa.table(
        "year_events", sa.column("id", sa.Text()), sa.column("year", sa.SmallInteger()),
        sa.column("category", sa.Text()), sa.column("text", sa.Text()),
        sa.column("source_url", sa.Text()), sa.column("occurred_on", sa.Date()),
    )
    op.bulk_insert(events, rows)


def downgrade() -> None:
    op.drop_index("year_events_enabled_year_idx", table_name="year_events")
    op.drop_table("year_events")
