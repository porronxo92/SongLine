"""Commercial permissions are enforced by the API and WS, including fake audio mode."""
from collections.abc import Callable
from contextlib import ExitStack
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.account import optional_account
from app.catalog.packs import PackDef
from app.game.models import Room
from app.services import Services
from tests.integration.test_ws import hdr, open_ws, tok

MakeApp = Callable[..., tuple[FastAPI, Services]]


@pytest.mark.parametrize(("settings", "reason"), [
    ({"team_count": 3}, "plan_team_limit"),
    ({"target_cards": 6}, "plan_card_limit"),
    ({"packs": ["rock-test"]}, "pack_not_owned"),
])
def test_free_cannot_create_paid_settings_even_with_fake_audio(make_app: MakeApp,
                                                              settings: dict[str, Any], reason: str) -> None:
    app, svc = make_app(enforce_plan_limits=True)
    svc.packs.append(PackDef(slug="rock-test", name="Rock"))
    with TestClient(app) as client:
        response = client.post("/api/rooms", json={"settings": settings}, headers=hdr(tok(client)))
        assert response.status_code == 403
        assert response.json()["detail"] == reason
        assert not svc.manager.rooms


def test_free_defaults_and_websocket_changes_are_guarded(make_app: MakeApp) -> None:
    app, svc = make_app(enforce_plan_limits=True)
    svc.packs.append(PackDef(slug="rock-test", name="Rock"))
    with TestClient(app) as client, ExitStack() as stack:
        token = tok(client)
        response = client.post("/api/rooms", json={}, headers=hdr(token))
        assert response.status_code == 200, response.text
        code = response.json()["code"]
        runtime = svc.manager.get(code)
        assert runtime is not None
        assert runtime.room.settings.target_cards == 5
        assert runtime.room.settings.initial_card_counts is True
        assert runtime.room.settings.team_count == 2
        assert runtime.room.settings.packs == ["mix"]
        host = open_ws(client, stack, code, token)
        host.state()
        for settings, reason in [({"team_count": 3}, "plan_team_limit"),
                                 ({"target_cards": 6}, "plan_card_limit"),
                                 ({"packs": ["rock-test"]}, "pack_not_owned")]:
            result = host.result(host.send("update_settings", **settings))
            assert result["type"] == "error", result
            assert result["payload"]["code"] == reason
        host.ok("update_settings", target_cards=4)
        assert host.state(lambda view: view["settings"]["targetCards"] == 4)
        assert runtime.room.settings.team_count == 2
        assert runtime.room.settings.packs == ["mix"]


def test_premium_owned_packs_and_room_access_snapshot(make_app: MakeApp) -> None:
    app, svc = make_app(enforce_plan_limits=True)
    svc.packs.append(PackDef(slug="rock-test", name="Rock"))

    async def premium() -> dict[str, Any]:
        return {"id": "premium-host", "email": "host@example.com", "display_name": "Host",
                "plan": "premium", "pack_slugs": ["mix", "rock-test"]}

    app.dependency_overrides[optional_account] = premium
    with TestClient(app) as client, ExitStack() as stack:
        token = tok(client)
        response = client.post("/api/rooms", json={"settings": {
            "team_count": 6, "target_cards": 45, "packs": ["rock-test"]}}, headers=hdr(token))
        assert response.status_code == 200, response.text
        runtime = svc.manager.get(response.json()["code"])
        assert runtime is not None
        restored = Room.model_validate_json(runtime.room.model_dump_json())
        assert restored.owner_account_id == "premium-host"
        assert restored.access_max_teams == 6
        assert restored.access_max_cards is None
        assert set(restored.access_pack_slugs) == {"mix", "rock-test"}
        assert len(restored.teams) == 6
        host = open_ws(client, stack, restored.code, token)
        host.state()
        host.ok("update_settings", target_cards=60)
        assert host.state(lambda view: view["settings"]["targetCards"] == 60)


def test_spotify_auth_mode_does_not_make_guest_a_songline_account(make_app: MakeApp) -> None:
    app, svc = make_app(enforce_plan_limits=True, auth_mode="spotify")
    with TestClient(app) as client:
        response = client.post("/api/rooms", json={}, headers=hdr(tok(client)))
        assert response.status_code == 401
        assert response.json()["detail"] == "account_required"
        assert not svc.manager.rooms


def test_client_cannot_supply_room_entitlements(make_app: MakeApp) -> None:
    app, svc = make_app(enforce_plan_limits=True)
    with TestClient(app) as client, ExitStack() as stack:
        token = tok(client)
        response = client.post("/api/rooms", json={
            "access_max_teams": 6, "access_max_cards": None, "plan": "premium",
            "access_pack_slugs": ["mix", "rock-test"]}, headers=hdr(token))
        assert response.status_code == 200
        runtime = svc.manager.get(response.json()["code"])
        assert runtime is not None
        assert runtime.room.access_max_teams == 2
        assert runtime.room.access_max_cards == 5
        assert runtime.room.access_pack_slugs == ["mix"]
        host = open_ws(client, stack, runtime.room.code, token)
        host.state()
        result = host.result(host.send("update_settings", access_max_teams=6, access_max_cards=None))
        assert result["type"] == "error"
        assert result["payload"]["code"] == "invalid_settings"
        assert runtime.room.access_max_teams == 2
        assert runtime.room.access_max_cards == 5


def test_access_guards_are_rechecked_at_start_and_rematch(make_app: MakeApp) -> None:
    app, svc = make_app(enforce_plan_limits=True)
    with TestClient(app) as client, ExitStack() as stack:
        token = tok(client)
        response = client.post("/api/rooms", json={}, headers=hdr(token))
        runtime = svc.manager.get(response.json()["code"])
        assert runtime is not None
        host = open_ws(client, stack, runtime.room.code, token)
        host.state()
        # Simulate restoring an older snapshot containing now-disallowed settings.
        runtime.room.settings.target_cards = 10
        for command in ("start_game", "rematch"):
            result = host.result(host.send(command))
            assert result["type"] == "error", result
            assert result["payload"]["code"] == "plan_card_limit"
