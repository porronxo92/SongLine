"""Account API security boundaries, independently of game/Spotify sessions."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.accounts.security import hash_password, token_hash, verify_password


class MemoryAccounts:
    """Test repository with the same expiry and uniqueness semantics as PostgreSQL."""
    def __init__(self):
        self.users = {}
        self.sessions = {}
        self.resets = {}

    async def create(self, email, display_name, password_hash):
        if email in self.users:
            return None
        user = dict(id=uuid4(), email=email, display_name=display_name,
                    password_hash=password_hash, plan="free", pack_slugs=["mix"])
        self.users[email] = user
        return user

    async def find_email(self, email):
        return self.users.get(email)

    async def add_session(self, account_id, digest):
        self.sessions[digest] = (account_id, datetime.now(UTC) + timedelta(days=30))

    async def session_user(self, digest):
        pair = self.sessions.get(digest)
        if not pair or pair[1] <= datetime.now(UTC):
            return None
        return next((u for u in self.users.values() if u["id"] == pair[0]), None)

    async def delete_session(self, digest):
        self.sessions.pop(digest, None)

    async def save_reset(self, account_id, digest):
        self.resets = {k: v for k, v in self.resets.items() if v[0] != account_id}
        self.resets[digest] = (account_id, datetime.now(UTC) + timedelta(minutes=30))

    async def consume_reset(self, digest, password_hash):
        pair = self.resets.get(digest)
        if pair is None or pair[1] <= datetime.now(UTC):
            return False
        self.resets.pop(digest)
        user = next(u for u in self.users.values() if u["id"] == pair[0])
        user["password_hash"] = password_hash
        self.sessions = {k: v for k, v in self.sessions.items() if v[0] != user["id"]}
        return True

    async def close(self):
        pass


def client_repo(make_app):
    app, svc = make_app()
    repo = MemoryAccounts()
    svc.accounts = repo
    return TestClient(app), svc, repo


CREDS = {"email": "host@example.com", "password": "a-long-password-123"}


def test_password_hashes_are_salted_and_verified():
    first = hash_password(CREDS["password"])
    assert first != hash_password(CREDS["password"])
    assert verify_password(CREDS["password"], first)
    assert not verify_password("wrong", first)
    assert not verify_password("wrong", "bad-format")


def test_register_normalizes_and_session_revocation(make_app):
    client, _, repo = client_repo(make_app)
    response = client.post("/api/account/register", json={**CREDS, "email": " HOST@example.com ", "display_name": " Ana "})
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert payload["user"]["email"] == "host@example.com"
    assert payload["user"]["display_name"] == "Ana"
    assert payload["user"]["plan"] == "free"
    assert payload["user"]["max_cards"] == 5
    assert "password_hash" not in payload["user"]
    token = payload["token"]
    assert token not in repo.sessions
    assert token_hash(token) in repo.sessions
    assert repo.users[CREDS["email"]]["password_hash"] != CREDS["password"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/account/me", headers=headers).status_code == 200
    assert client.post("/api/account/logout", headers=headers).status_code == 204
    assert client.get("/api/account/me", headers=headers).status_code == 401


def test_login_does_not_upgrade_fake_auth_or_accept_game_session(make_app):
    client, svc, repo = client_repo(make_app)
    client.post("/api/account/register", json={**CREDS, "plan": "premium"})
    assert client.post("/api/account/register", json=CREDS).status_code == 409
    bad = client.post("/api/account/login", json={**CREDS, "password": "wrong"})
    missing = client.post("/api/account/login", json={**CREDS, "email": "unknown@example.com"})
    assert bad.status_code == missing.status_code == 401
    assert bad.json() == missing.json()
    result = client.post("/api/account/login", json=CREDS).json()
    assert result["user"]["plan"] == "free"
    assert result["user"]["pack_slugs"] == ["mix"]
    game_token = svc.signer.issue()
    assert client.get("/api/account/me", headers={"Authorization": f"Bearer {game_token}"}).status_code == 401
    token = result["token"]
    digest = token_hash(token)
    repo.sessions[digest] = (repo.sessions[digest][0], datetime.now(UTC) - timedelta(seconds=1))
    assert client.get("/api/account/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_registration_validation_and_auth_throttle(make_app):
    client, _, _ = client_repo(make_app)
    assert client.post("/api/account/register", json={**CREDS, "password": "short"}).status_code == 422
    assert client.post("/api/account/register", json={**CREDS, "email": "not-email"}).status_code == 422
    for _ in range(10):
        assert client.post("/api/account/login", json={**CREDS, "password": "wrong"}).status_code == 401
    assert client.post("/api/account/login", json=CREDS).status_code == 429


def test_recovery_is_single_use_revokes_sessions_and_hides_account_existence(make_app, monkeypatch):
    client, svc, repo = client_repo(make_app)
    first = client.post("/api/account/register", json=CREDS).json()
    assert client.post("/api/account/forgot", json={"email": CREDS["email"]}).status_code == 503
    svc.config.smtp_host = "smtp.example.com"
    svc.config.smtp_from = "support@example.com"
    deliveries = []
    monkeypatch.setattr("app.api.account.send_reset", lambda config, email, url: deliveries.append((email, url)))
    known = client.post("/api/account/forgot", json={"email": CREDS["email"]})
    unknown = client.post("/api/account/forgot", json={"email": "unknown@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json() == {"accepted": True}
    assert "token" not in known.json()
    assert len(deliveries) == 1
    reset_token = deliveries[0][1].split("token=")[1]
    assert reset_token not in repo.resets
    assert token_hash(reset_token) in repo.resets
    reset_body = {"token": reset_token, "password": "my-new-password-123"}
    assert client.post("/api/account/reset", json=reset_body).status_code == 204
    assert client.get("/api/account/me", headers={"Authorization": f"Bearer {first['token']}"}).status_code == 401
    assert client.post("/api/account/reset", json=reset_body).status_code == 400
    assert client.post("/api/account/login", json=CREDS).status_code == 401
    assert client.post("/api/account/login", json={**CREDS, "password": reset_body["password"]}).status_code == 200


def test_reset_expiry_and_replaced_links(make_app, monkeypatch):
    client, svc, repo = client_repo(make_app)
    client.post("/api/account/register", json=CREDS)
    svc.config.smtp_host = "smtp.example.com"
    svc.config.smtp_from = "support@example.com"
    links = []
    monkeypatch.setattr("app.api.account.send_reset", lambda config, email, url: links.append(url))
    for _ in range(2):
        client.post("/api/account/forgot", json={"email": CREDS["email"]})
    token1, token2 = (link.split("token=")[1] for link in links)
    assert token_hash(token1) not in repo.resets
    body = {"password": "my-new-password-123"}
    assert client.post("/api/account/reset", json={**body, "token": token1}).status_code == 400
    digest = token_hash(token2)
    repo.resets[digest] = (repo.resets[digest][0], datetime.now(UTC) - timedelta(seconds=1))
    assert client.post("/api/account/reset", json={**body, "token": token2}).status_code == 400
