"""Server-issued, HMAC-signed session tokens: base64url(random32) + "." + base64url(HMAC-SHA256)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets

log = logging.getLogger(__name__)

MAX_TOKEN_LEN = 200


class SessionSigner:
    def __init__(self, secret: str) -> None:
        if secret:
            self._key = secret.encode()
            self.ephemeral = False
        else:
            self._key = secrets.token_bytes(32)
            self.ephemeral = True
            log.warning(
                "SESSION_SECRET is not set: using an ephemeral key. "
                "Every session token is invalidated on restart. Set SESSION_SECRET in production."
            )

    def _sig(self, body: str) -> str:
        mac = hmac.new(self._key, body.encode(), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(mac).rstrip(b"=").decode()

    def issue(self) -> str:
        body = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
        return f"{body}.{self._sig(body)}"

    def verify(self, token: str) -> bool:
        if not token or len(token) > MAX_TOKEN_LEN:
            return False
        body, dot, sig = token.partition(".")
        if not dot or not body or not sig:
            return False
        # compare as bytes: compare_digest raises TypeError on non-ASCII str
        return hmac.compare_digest(sig.encode("utf-8", "surrogatepass"), self._sig(body).encode())
