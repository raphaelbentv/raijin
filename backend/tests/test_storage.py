import uuid

from app.core.storage import build_object_key


def test_build_object_key_structure() -> None:
    tid = uuid.uuid4()
    key = build_object_key(tid, "facture-2026-04.pdf")
    assert key.startswith(f"tenants/{tid}/invoices/")
    assert key.endswith(".pdf")


def test_build_object_key_handles_missing_extension() -> None:
    key = build_object_key(uuid.uuid4(), "no-extension")
    assert key.endswith(".bin")


def test_build_object_key_lowercases_extension() -> None:
    key = build_object_key(uuid.uuid4(), "SCAN.PDF")
    assert key.endswith(".pdf")
