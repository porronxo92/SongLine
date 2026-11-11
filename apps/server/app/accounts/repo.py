"""Durable accounts and hashed, revocable sessions in PostgreSQL."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


class PostgresAccounts:
    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, pool_pre_ping=True)

    async def find_email(self, email: str) -> dict[str, Any] | None:
        async with self.engine.connect() as conn:
            row = (await conn.execute(text("SELECT * FROM accounts WHERE email = :email"), {"email": email})).mappings().first()
        return dict(row) if row else None

    async def create(self, email: str, display_name: str, password_hash: str) -> dict[str, Any] | None:
        async with self.engine.begin() as conn:
            row = (await conn.execute(text(
                "INSERT INTO accounts (id, email, display_name, password_hash) "
                "VALUES (:id, :email, :display_name, :password_hash) ON CONFLICT (email) DO NOTHING RETURNING *"
            ), {"id": uuid4(), "email": email, "display_name": display_name, "password_hash": password_hash})).mappings().first()
        return dict(row) if row else None

    async def add_session(self, account_id: str, digest: str) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text("DELETE FROM account_sessions WHERE expires_at <= now()"))
            await conn.execute(text(
                "INSERT INTO account_sessions (token_hash, account_id, expires_at) VALUES (:hash, :id, :expires)"
            ), {"hash": digest, "id": account_id, "expires": datetime.now(UTC) + timedelta(days=30)})

    async def session_user(self, digest: str) -> dict[str, Any] | None:
        async with self.engine.connect() as conn:
            row = (await conn.execute(text(
                "SELECT a.* FROM accounts a JOIN account_sessions s ON a.id = s.account_id "
                "WHERE s.token_hash = :hash AND s.expires_at > now()"
            ), {"hash": digest})).mappings().first()
        return dict(row) if row else None

    async def delete_session(self, digest: str) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text("DELETE FROM account_sessions WHERE token_hash = :hash"), {"hash": digest})

    async def close(self) -> None:
        await self.engine.dispose()

    async def save_reset(self, account_id: str, digest: str) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text("DELETE FROM account_password_resets WHERE expires_at <= now()"))
            await conn.execute(text(
                "INSERT INTO account_password_resets (token_hash, account_id, expires_at) "
                "VALUES (:hash, :id, :expires) ON CONFLICT (account_id) DO UPDATE "
                "SET token_hash = EXCLUDED.token_hash, expires_at = EXCLUDED.expires_at"
            ), {"hash": digest, "id": account_id, "expires": datetime.now(UTC) + timedelta(minutes=30)})

    async def consume_reset(self, digest: str, password_hash: str) -> bool:
        async with self.engine.begin() as conn:
            account_id = (await conn.execute(text(
                "DELETE FROM account_password_resets WHERE token_hash = :hash AND expires_at > now() "
                "RETURNING account_id"
            ), {"hash": digest})).scalar_one_or_none()
            if account_id is None:
                return False
            await conn.execute(text("UPDATE accounts SET password_hash = :password WHERE id = :id"),
                               {"password": password_hash, "id": account_id})
            await conn.execute(text("DELETE FROM account_sessions WHERE account_id = :id"), {"id": account_id})
            return True
