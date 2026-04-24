import uuid

import pytest

from app.core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    password_fingerprint_matches,
    verify_password,
)


def test_hash_verify_roundtrip() -> None:
    h = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", h) is True
    assert verify_password("wrong", h) is False


def test_access_token_roundtrip() -> None:
    uid = uuid.uuid4()
    tid = uuid.uuid4()
    token = create_access_token(user_id=uid, tenant_id=tid, role="admin")
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == str(uid)
    assert payload["tid"] == str(tid)
    assert payload["role"] == "admin"
    assert payload["type"] == "access"


def test_refresh_token_type_enforced() -> None:
    uid = uuid.uuid4()
    tid = uuid.uuid4()
    refresh = create_refresh_token(user_id=uid, tenant_id=tid, role="user")
    with pytest.raises(ValueError):
        decode_token(refresh, expected_type="access")


def test_garbage_token_rejected() -> None:
    with pytest.raises(ValueError):
        decode_token("not.a.jwt", expected_type="access")


def test_password_reset_token_carries_password_fingerprint() -> None:
    uid = uuid.uuid4()
    tid = uuid.uuid4()
    password_hash = hash_password("old-password-2026")
    token = create_password_reset_token(
        user_id=uid, tenant_id=tid, password_hash=password_hash
    )

    payload = decode_token(token, expected_type="password_reset")

    assert payload["sub"] == str(uid)
    assert payload["tid"] == str(tid)
    assert payload["type"] == "password_reset"
    assert password_fingerprint_matches(password_hash, payload["pwd"]) is True
    assert password_fingerprint_matches(hash_password("new-password-2026"), payload["pwd"]) is False
