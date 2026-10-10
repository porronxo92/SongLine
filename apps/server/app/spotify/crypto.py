"""Fernet helpers for Spotify tokens at rest."""

from __future__ import annotations

import logging

from cryptography.fernet import Fernet

log = logging.getLogger(__name__)


class TokenCipher:
    def __init__(self, key: str = "") -> None:
        if not key:
            key = Fernet.generate_key().decode()
            log.warning("TOKEN_ENC_KEY is empty: using an ephemeral key (tokens die on restart)")
        self._f = Fernet(key.encode())

    def encrypt(self, value: str) -> bytes:
        return self._f.encrypt(value.encode())

    def decrypt(self, blob: bytes) -> str:
        return self._f.decrypt(blob).decode()
