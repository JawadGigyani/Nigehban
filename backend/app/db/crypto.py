"""Protect subscriber contact details.

Addresses are encrypted with Fernet so the alert engine can still send to
them, and hashed with a keyed HMAC so we can look them up (for unsubscribe and
duplicate checks) without decrypting every row.
"""

from __future__ import annotations

import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken

from backend.app.config import Settings


class ContactCipherError(RuntimeError):
    pass


class ContactCipher:
    def __init__(self, encryption_key: str, hash_key: str) -> None:
        if not encryption_key or not hash_key:
            raise ContactCipherError("Both contact encryption and hash keys are required.")
        self._fernet = Fernet(encryption_key.encode())
        self._hash_key = hash_key.encode()

    @classmethod
    def from_settings(cls, settings: Settings) -> ContactCipher:
        if settings.contact_encryption_key is None or settings.contact_hash_key is None:
            raise ContactCipherError(
                "Set NIGEHBAN_CONTACT_ENCRYPTION_KEY and NIGEHBAN_CONTACT_HASH_KEY."
            )
        return cls(
            settings.contact_encryption_key.get_secret_value(),
            settings.contact_hash_key.get_secret_value(),
        )

    @staticmethod
    def normalise(address: str) -> str:
        """Phone numbers and ids: no spaces, lower case. Web-push JSON keeps its case (keys are base64)."""

        compact = "".join(address.split())
        return compact if compact.startswith("{") else compact.lower()

    def encrypt(self, address: str) -> str:
        return self._fernet.encrypt(self.normalise(address).encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as exc:
            raise ContactCipherError("Could not decrypt contact address.") from exc

    def hash(self, address: str) -> str:
        return hmac.new(
            self._hash_key, self.normalise(address).encode(), hashlib.sha256
        ).hexdigest()


def generate_keys() -> tuple[str, str]:
    """Return a new (encryption_key, hash_key) pair for `.env`."""

    import secrets

    return Fernet.generate_key().decode(), secrets.token_urlsafe(32)
