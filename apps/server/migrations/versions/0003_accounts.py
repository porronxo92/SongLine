"""Persistent SongLine accounts, independent of Spotify.

Revision ID: 0003
Revises: 0002
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE accounts (
            id UUID PRIMARY KEY,
            email TEXT NOT NULL UNIQUE CHECK (email = lower(email)),
            display_name TEXT NOT NULL DEFAULT '',
            password_hash TEXT NOT NULL,
            plan TEXT NOT NULL DEFAULT 'free' CHECK (plan IN ('free', 'premium')),
            pack_slugs TEXT[] NOT NULL DEFAULT '{mix}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE account_sessions (
            token_hash TEXT PRIMARY KEY,
            account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE account_password_resets (
            token_hash TEXT PRIMARY KEY,
            account_id UUID NOT NULL UNIQUE REFERENCES accounts(id) ON DELETE CASCADE,
            expires_at TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute("CREATE INDEX account_sessions_account_idx ON account_sessions (account_id)")
    op.execute("CREATE INDEX account_sessions_expiry_idx ON account_sessions (expires_at)")


def downgrade() -> None:
    op.execute("DROP TABLE account_password_resets")
    op.execute("DROP TABLE account_sessions")
    op.execute("DROP TABLE accounts")
