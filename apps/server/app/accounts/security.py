"""Versioned password hashes and random account credentials."""

import hashlib
import hmac
import secrets

ITERATIONS = 600_000


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${key.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or int(rounds) != ITERATIONS:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


# Unknown accounts pay the same password verification cost as known accounts.
DUMMY_HASH = hash_password("unusable-dummy-password", salt=b"songline-dummy-01")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
