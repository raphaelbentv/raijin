from datetime import date
from decimal import Decimal

import pytest

from app.services.normalizer import (
    parse_amount,
    parse_currency,
    parse_date,
    parse_vat_id,
    parse_vat_rate,
)


class TestParseDate:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("2026-04-21", date(2026, 4, 21)),
            ("21/04/2026", date(2026, 4, 21)),
            ("21-04-2026", date(2026, 4, 21)),
            ("21.04.2026", date(2026, 4, 21)),
            ("01/01/2026", date(2026, 1, 1)),
            ("31/12/2025", date(2025, 12, 31)),
        ],
    )
    def test_numeric_eu_format(self, raw: str, expected: date) -> None:
        assert parse_date(raw) == expected

    def test_iso_short_year_expand(self) -> None:
        assert parse_date("21/04/26") == date(2026, 4, 21)
        assert parse_date("21/04/85") == date(1985, 4, 21)

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("21 avril 2026", date(2026, 4, 21)),
            ("21 Avril 2026", date(2026, 4, 21)),
            ("1 janvier 2026", date(2026, 1, 1)),
            ("15 août 2024", date(2024, 8, 15)),
        ],
    )
    def test_french_text(self, raw: str, expected: date) -> None:
        assert parse_date(raw) == expected

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("21 April 2026", date(2026, 4, 21)),
            ("21 Apr 2026", date(2026, 4, 21)),
            ("1 Jan 2026", date(2026, 1, 1)),
        ],
    )
    def test_english_text(self, raw: str, expected: date) -> None:
        assert parse_date(raw) == expected

    def test_greek_text(self) -> None:
        assert parse_date("21 Απριλίου 2026") == date(2026, 4, 21)
        assert parse_date("1 Ιανουαρίου 2026") == date(2026, 1, 1)

    def test_invalid_returns_none(self) -> None:
        assert parse_date("pas une date") is None
        assert parse_date("") is None
        assert parse_date(None) is None
        assert parse_date("45/13/2026") is None

    def test_datetime_passthrough(self) -> None:
        assert parse_date(date(2026, 4, 21)) == date(2026, 4, 21)


class TestParseAmount:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("1234.56", Decimal("1234.56")),
            ("1234,56", Decimal("1234.56")),
            ("1 234,56", Decimal("1234.56")),
            ("1 234,56", Decimal("1234.56")),
            ("1.234,56", Decimal("1234.56")),
            ("1,234.56", Decimal("1234.56")),
            ("1.234.567,89", Decimal("1234567.89")),
            ("1234", Decimal("1234")),
            ("0", Decimal("0")),
        ],
    )
    def test_various_formats(self, raw: str, expected: Decimal) -> None:
        assert parse_amount(raw) == expected

    def test_with_currency_symbol(self) -> None:
        assert parse_amount("€1.234,56") == Decimal("1234.56")
        assert parse_amount("1 234,56 €") == Decimal("1234.56")
        assert parse_amount("$1,234.56") == Decimal("1234.56")
        assert parse_amount("EUR 1234.56") == Decimal("1234.56")

    def test_negative(self) -> None:
        assert parse_amount("-1234,56") == Decimal("-1234.56")
        assert parse_amount("(1.234,56)") == Decimal("-1234.56")

    def test_passthrough(self) -> None:
        assert parse_amount(Decimal("10")) == Decimal("10")
        assert parse_amount(42) == Decimal("42")
        assert parse_amount(3.14) == Decimal("3.14")

    def test_invalid(self) -> None:
        assert parse_amount("abc") is None
        assert parse_amount("") is None
        assert parse_amount(None) is None


class TestParseVatId:
    def test_greek_vat_with_prefix(self) -> None:
        assert parse_vat_id("EL123456789") == "EL123456789"

    def test_greek_bare_digits_gets_prefix(self) -> None:
        assert parse_vat_id("123456789") == "EL123456789"

    def test_greek_with_spaces_and_dashes(self) -> None:
        assert parse_vat_id("EL 123 456 789") == "EL123456789"
        assert parse_vat_id("EL-123-456-789") == "EL123456789"

    def test_greek_with_greek_prefix_stripped(self) -> None:
        assert parse_vat_id("ΑΦΜ 123456789") == "EL123456789"

    def test_french_vat(self) -> None:
        assert parse_vat_id("FR12345678901") == "FR12345678901"
        assert parse_vat_id("FR 12 345 678 901") == "FR12345678901"

    def test_italian(self) -> None:
        assert parse_vat_id("IT12345678901") == "IT12345678901"

    def test_invalid_returns_none(self) -> None:
        assert parse_vat_id(None) is None
        assert parse_vat_id("") is None
        assert parse_vat_id("123") is None
        assert parse_vat_id("XX") is None


class TestParseCurrency:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("EUR", "EUR"),
            ("USD", "USD"),
            ("€", "EUR"),
            ("$", "USD"),
            ("£", "GBP"),
            ("eur", "EUR"),
            ("1.234 €", "EUR"),
            ("Total: $1,234", "USD"),
        ],
    )
    def test_valid(self, raw: str, expected: str) -> None:
        assert parse_currency(raw) == expected

    def test_unknown_returns_default(self) -> None:
        assert parse_currency(None) == "EUR"
        assert parse_currency("") == "EUR"
        assert parse_currency("XYZ", default="USD") == "XYZ"

    def test_default_override(self) -> None:
        assert parse_currency(None, default="USD") == "USD"


class TestParseVatRate:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("24%", Decimal("0.24")),
            ("24", Decimal("0.24")),
            ("0,24", Decimal("0.24")),
            ("0.24", Decimal("0.24")),
            ("13%", Decimal("0.13")),
        ],
    )
    def test_various(self, raw: str, expected: Decimal) -> None:
        assert parse_vat_rate(raw) == expected

    def test_zero(self) -> None:
        assert parse_vat_rate("0") == Decimal("0")
        assert parse_vat_rate("0%") == Decimal("0")

    def test_invalid(self) -> None:
        assert parse_vat_rate(None) is None
        assert parse_vat_rate("") is None
