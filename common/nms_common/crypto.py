import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet
from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def _normalize_fernet_key(raw_key: str) -> bytes:
    """Allow any secret string in config while still handing Fernet a valid 32-byte urlsafe-base64 key."""
    try:
        Fernet(raw_key.encode())
        return raw_key.encode()
    except (ValueError, TypeError):
        digest = hashlib.sha256(raw_key.encode()).digest()
        return base64.urlsafe_b64encode(digest)


class CredentialCipher:
    """Encrypts/decrypts device credential payloads (SNMP community strings, HTTP basic auth, etc).

    Only the monitoring worker ever calls decrypt(); the API only ever calls encrypt()
    when accepting new/updated credentials from an admin, and never returns plaintext.
    """

    def __init__(self, key: str):
        self._fernet = Fernet(_normalize_fernet_key(key))

    def encrypt_json(self, payload: dict[str, Any]) -> bytes:
        return self._fernet.encrypt(json.dumps(payload).encode())

    def decrypt_json(self, token: bytes) -> dict[str, Any]:
        return json.loads(self._fernet.decrypt(token).decode())
