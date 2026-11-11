"""Opt-in integration check against a disposable, migrated PostgreSQL database.

TEST_DATABASE_URL=postgresql+asyncpg://... pytest tests/test_accounts_postgres.py
Never point this test at production: it creates and deletes its own account.
"""

import os
import secrets
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.accounts.repo import PostgresAccounts
from app.accounts.security import hash_password, token_hash, verify_password


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="requires disposable PostgreSQL")
async def test_durable_sessions_atomic_reset_and_expiry():
    repo = PostgresAccounts(os.environ["TEST_DATABASE_URL"])
    email = f"test-{uuid4()}@example.com"
    try:
        user = await repo.create(email, "Test", hash_password("long-test-password"))
        assert user["plan"] == "free"
        assert await repo.create(email, "Other", "unused") is None
        session = token_hash(secrets.token_urlsafe(32))
        await repo.add_session(user["id"], session)
        # New repository/connection simulates a restarted service.
        other = PostgresAccounts(os.environ["TEST_DATABASE_URL"])
        try:
            assert (await other.session_user(session))["email"] == email
            digest = token_hash(secrets.token_urlsafe(32))
            await repo.save_reset(user["id"], digest)
            new_hash = hash_password("a-new-test-password")
            assert await other.consume_reset(digest, new_hash)
            assert not await repo.consume_reset(digest, new_hash)
            assert await repo.session_user(session) is None
            assert verify_password("a-new-test-password", (await repo.find_email(email))["password_hash"])
            await repo.add_session(user["id"], session)
            async with repo.engine.begin() as conn:
                await conn.execute(text("UPDATE account_sessions SET expires_at = now() - interval '1 second' WHERE token_hash = :hash"), {"hash": session})
            assert await repo.session_user(session) is None
            await repo.save_reset(user["id"], digest)
            async with repo.engine.begin() as conn:
                await conn.execute(text("UPDATE account_password_resets SET expires_at = now() - interval '1 second' WHERE token_hash = :hash"), {"hash": digest})
            assert not await repo.consume_reset(digest, new_hash)
        finally:
            await other.close()
    finally:
        async with repo.engine.begin() as conn:
            await conn.execute(text("DELETE FROM accounts WHERE email = :email"), {"email": email})
        await repo.close()
