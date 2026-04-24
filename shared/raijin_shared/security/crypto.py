"""Symmetric encryption for secrets at rest.

Usage:
    from raijin_shared.security import encrypt, decrypt
    ciphertext = encrypt("oauth_refresh_token")
    plaintext = decrypt(ciphertext)

Requires ENCRYPTION_KEY env var (Fernet key, 32 url-safe base64 bytes).
Generate with: python -c "from raijin_shared.security import generate_key; print(generate_key())"
"""
from __future__ import annotations

import os
from functools import lru_cache

from cryptography.fernet import Fernet


class CryptoConfigurationError(RuntimeError):
    pass


@lru_cache
def _fernet() -> Fernet:
    key = os.environ.get("ENCRYPTION_KEY", "").strip()
    if not key:
        raise CryptoConfigurationError("ENCRYPTION_KEY not set")
    try:
        return Fernet(key.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise CryptoConfigurationError(f"invalid ENCRYPTION_KEY: {exc}") from exc


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def generate_key() -> str:
    return Fernet.generate_key().decode("utf-8")
