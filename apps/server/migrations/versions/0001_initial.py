"""songs, room_snapshots, spotify_sessions

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE songs (
          id              SERIAL PRIMARY KEY,
          csv_id          TEXT UNIQUE NOT NULL,
          title           TEXT NOT NULL,
          artist          TEXT NOT NULL,
          year            SMALLINT NOT NULL CHECK (year BETWEEN 1950 AND 2100),
          year_status     TEXT NOT NULL DEFAULT 'pending'
                          CHECK (year_status IN ('pending','verified','ambiguous','disputed')),
          year_note       TEXT,
          title_aliases   TEXT[] NOT NULL DEFAULT '{}',
          artist_aliases  TEXT[] NOT NULL DEFAULT '{}',
          genre           TEXT,
          origin          TEXT CHECK (origin IN ('es','intl')),
          spotify_track_id TEXT,
          spotify_album_date TEXT,
          isrc            TEXT,
          mb_first_release TEXT,
          match_confidence REAL,
          match_flags     TEXT[] NOT NULL DEFAULT '{}',
          enabled         BOOLEAN NOT NULL DEFAULT false,
          fallback_preview_ref TEXT,
          updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX songs_enabled_year_idx ON songs (enabled, year)")
    op.execute(
        """
        CREATE TABLE room_snapshots (
          code TEXT PRIMARY KEY,
          state JSONB NOT NULL,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE spotify_sessions (
          session_id UUID PRIMARY KEY,
          spotify_user_id TEXT,
          access_token BYTEA,
          refresh_token BYTEA,
          expires_at TIMESTAMPTZ,
          premium_verified BOOLEAN DEFAULT false,
          created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS spotify_sessions")
    op.execute("DROP TABLE IF EXISTS room_snapshots")
    op.execute("DROP TABLE IF EXISTS songs")
