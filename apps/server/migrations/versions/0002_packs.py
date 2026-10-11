"""genre packs: table packs, songs.pack, year range 1900..2100

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE packs (
          slug        TEXT PRIMARY KEY,
          name        TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          icon        TEXT NOT NULL DEFAULT 'music',
          sort        INTEGER NOT NULL DEFAULT 100
        )
        """
    )
    op.execute("ALTER TABLE songs ADD COLUMN pack TEXT NOT NULL DEFAULT 'mix'")
    op.execute("CREATE INDEX songs_pack_idx ON songs (pack)")
    op.execute("ALTER TABLE songs DROP CONSTRAINT songs_year_check")
    op.execute("ALTER TABLE songs ADD CONSTRAINT songs_year_check CHECK (year BETWEEN 1900 AND 2100)")


def downgrade() -> None:
    # Songs older than 1950 (Disney classics) would violate the old CHECK: they are removed.
    op.execute("DELETE FROM songs WHERE year < 1950")
    op.execute("ALTER TABLE songs DROP CONSTRAINT songs_year_check")
    op.execute("ALTER TABLE songs ADD CONSTRAINT songs_year_check CHECK (year BETWEEN 1950 AND 2100)")
    op.execute("DROP INDEX IF EXISTS songs_pack_idx")
    op.execute("ALTER TABLE songs DROP COLUMN pack")
    op.execute("DROP TABLE IF EXISTS packs")
