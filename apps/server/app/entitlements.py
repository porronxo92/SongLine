"""Pure server-side access checks, independent from Spotify Premium."""
from app.game.models import Settings


def check_access(settings: Settings, max_teams: int, max_cards: int | None,
                 pack_slugs: list[str]) -> str | None:
    if settings.team_count > max_teams:
        return "plan_team_limit"
    if max_cards is not None and settings.target_cards > max_cards:
        return "plan_card_limit"
    if set(settings.packs) - set(pack_slugs):
        return "pack_not_owned"
    return None
