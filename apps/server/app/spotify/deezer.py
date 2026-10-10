"""Deezer 30 s preview lookup (D7 fallback). Ids are cached in memory."""

from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)
API = "https://api.deezer.com"


class DeezerPreview:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http
        self._ids: dict[str, int] = {}

    @staticmethod
    def _key(isrc: str, title: str, artist: str) -> str:
        return f"isrc:{isrc}" if isrc else f"q:{title.lower()}|{artist.lower()}"

    async def _find_id(self, isrc: str, title: str, artist: str) -> int | None:
        key = self._key(isrc, title, artist)
        if key in self._ids:
            return self._ids[key]
        found: int | None = None
        if isrc:
            r = await self.http.get(f"{API}/track/isrc:{isrc}")
            if r.status_code == 200 and isinstance(r.json().get("id"), int):
                found = int(r.json()["id"])
        if found is None:
            q = f'track:"{title}" artist:"{artist}"'
            r = await self.http.get(f"{API}/search", params={"q": q, "limit": 1})
            if r.status_code == 200:
                data = r.json().get("data") or []
                if data:
                    found = int(data[0]["id"])
        if found is not None:
            self._ids[key] = found
        return found

    async def preview_url(self, isrc: str, title: str, artist: str) -> str | None:
        """Preview URLs are short-lived, so only the track id is cached."""
        tid = await self._find_id(isrc, title, artist)
        if tid is None:
            return None
        r = await self.http.get(f"{API}/track/{tid}")
        if r.status_code != 200:
            return None
        url = r.json().get("preview")
        return str(url) if url else None
