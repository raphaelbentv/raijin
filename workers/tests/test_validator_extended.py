import uuid
from datetime import date, timedelta

from raijin_shared.validation import (
    ValidationReport,
    validate_dates,
    validate_duplicate,
)


def test_dates_coherent() -> None:
    r = ValidationReport()
    validate_dates(date(2026, 1, 1), date(2026, 2, 1), r)
    assert r.issues == []


def test_issue_after_due_flags_error() -> None:
    r = ValidationReport()
    validate_dates(date(2026, 2, 1), date(2026, 1, 1), r)
    assert r.has_errors
    assert any(i.code == "issue_after_due" for i in r.issues)


def test_issue_date_in_future_flags_warning() -> None:
    r = ValidationReport()
    validate_dates(date.today() + timedelta(days=30), None, r)
    assert not r.has_errors
    assert any(i.code == "issue_date_future" for i in r.issues)


def test_issue_date_reasonable_future_ok() -> None:
    r = ValidationReport()
    validate_dates(date.today() + timedelta(days=3), None, r)
    assert r.issues == []


def test_duplicate_flagged_as_warning() -> None:
    r = ValidationReport()
    existing = uuid.uuid4()
    validate_duplicate(True, existing, r)
    assert not r.has_errors
    assert any(i.code == "possible_duplicate" for i in r.issues)


def test_no_duplicate_no_issue() -> None:
    r = ValidationReport()
    validate_duplicate(False, None, r)
    assert r.issues == []
