"""Normalisation des champs extraits par Azure DI.

Les formats européens et grecs divergent fortement des standards US. Les tests
dans tests/test_normalizer.py couvrent les variantes réelles rencontrées.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

_MONTHS_FR = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
    "juin": 6, "juillet": 7, "août": 8, "aout": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}
_MONTHS_EN = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
    "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTHS_GR = {
    "ιανουαριου": 1, "φεβρουαριου": 2, "μαρτιου": 3, "απριλιου": 4,
    "μαιου": 5, "ιουνιου": 6, "ιουλιου": 7, "αυγουστου": 8,
    "σεπτεμβριου": 9, "οκτωβριου": 10, "νοεμβριου": 11, "δεκεμβριου": 12,
}

_NUMERIC_DATE_RE = re.compile(r"^\s*(\d{1,4})\D(\d{1,2})\D(\d{1,4})\s*$")
_TEXT_DATE_RE = re.compile(
    r"^\s*(\d{1,2})[\s\-/]+([^\s\d\-/]+)[\s\-/]+(\d{2,4})\s*$",
    re.IGNORECASE,
)


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def _month_from_name(raw: str) -> int | None:
    key = _strip_accents(raw).lower().rstrip(".")
    return _MONTHS_FR.get(key) or _MONTHS_EN.get(key) or _MONTHS_GR.get(key)


def _normalize_year(year_int: int) -> int:
    if year_int < 100:
        # heuristique : 00-79 = 20xx, 80-99 = 19xx
        return 2000 + year_int if year_int < 80 else 1900 + year_int
    return year_int


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(_normalize_year(year), month, day)
    except ValueError:
        return None


def parse_date(raw: str | date | None) -> date | None:
    """Parse une date dans les formats fréquents EU/GR.

    Priorité : ISO → DD/MM/YYYY → "DD Month YYYY" → tentative flexible.
    """
    if raw is None:
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()

    text = str(raw).strip()
    if not text:
        return None

    # ISO
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        pass

    match = _NUMERIC_DATE_RE.match(text)
    if match:
        a, b, c = (int(x) for x in match.groups())
        if a > 31:
            # YYYY-MM-DD ou YYYY/MM/DD
            candidate = _safe_date(a, b, c)
            if candidate:
                return candidate
        # DD/MM/YYYY — format EU/GR par défaut
        candidate = _safe_date(c, b, a)
        if candidate:
            return candidate
        # fallback MM/DD/YYYY uniquement si DD/MM impossible
        return _safe_date(c, a, b)

    match = _TEXT_DATE_RE.match(text)
    if match:
        day_str, month_str, year_str = match.groups()
        month = _month_from_name(month_str)
        if month is None:
            return None
        return _safe_date(int(year_str), month, int(day_str))

    return None


_SPACES_RE = re.compile(r"[\s ]")


def parse_amount(raw: str | int | float | Decimal | None) -> Decimal | None:
    """Parse un montant monétaire en gérant les formats EU et US.

    - ``"1 234,56"``  → ``Decimal("1234.56")``
    - ``"1.234,56"`` → ``Decimal("1234.56")``
    - ``"1,234.56"`` → ``Decimal("1234.56")``
    - ``"1234"``      → ``Decimal("1234")``
    - ``"(1.234,56)"``→ ``Decimal("-1234.56")``
    """
    if raw is None:
        return None
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, (int, float)):
        try:
            return Decimal(str(raw))
        except InvalidOperation:
            return None

    text = str(raw).strip()
    if not text:
        return None

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1].strip()
    if text.startswith("-"):
        negative = True
        text = text[1:].strip()

    text = re.sub(r"[€$£¥₺\sEUR|USD|GBP]+", "", text, flags=re.IGNORECASE)
    text = _SPACES_RE.sub("", text)

    if not text:
        return None

    last_dot = text.rfind(".")
    last_comma = text.rfind(",")

    if last_dot == -1 and last_comma == -1:
        cleaned = text
    elif last_dot == -1:
        # only comma
        parts = text.split(",")
        if len(parts) == 2 and len(parts[1]) in (2, 3):
            cleaned = parts[0] + "." + parts[1]
        else:
            cleaned = text.replace(",", "")
    elif last_comma == -1:
        parts = text.split(".")
        if len(parts) > 2:
            # "1.234.567" — point utilisé comme séparateur de milliers
            cleaned = "".join(parts)
        elif len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) <= 3:
            cleaned = "".join(parts)
        else:
            cleaned = text
    else:
        if last_dot > last_comma:
            # "1,234.56" : virgule = milliers, point = décimale
            cleaned = text.replace(",", "")
        else:
            # "1.234,56" : point = milliers, virgule = décimale
            cleaned = text.replace(".", "").replace(",", ".")

    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    return -value if negative else value


_VAT_COUNTRY_PATTERNS: dict[str, re.Pattern[str]] = {
    "EL": re.compile(r"^EL\d{9}$"),
    "FR": re.compile(r"^FR[A-Z0-9]{2}\d{9}$"),
    "DE": re.compile(r"^DE\d{9}$"),
    "IT": re.compile(r"^IT\d{11}$"),
    "ES": re.compile(r"^ES[A-Z0-9]{1}\d{7}[A-Z0-9]{1}$"),
    "BE": re.compile(r"^BE0\d{9}$"),
    "NL": re.compile(r"^NL\d{9}B\d{2}$"),
    "PT": re.compile(r"^PT\d{9}$"),
}


def parse_vat_id(raw: str | None) -> str | None:
    """Normalise un numéro de TVA intracommunautaire.

    - supprime espaces, tirets, ponctuation
    - ajoute le préfixe ``EL`` si 9 chiffres nus (contexte client grec)
    - valide le format pays connu
    """
    if not raw:
        return None

    text = str(raw).upper()
    text = re.sub(r"[\s\-.·:]+", "", text)
    text = text.replace("ΑΦΜ", "").replace("ΦΠΑ", "")
    text = re.sub(r"[^A-Z0-9]", "", text)
    if not text:
        return None

    if text.isdigit() and len(text) == 9:
        text = "EL" + text

    if len(text) < 3:
        return None

    country = text[:2]
    pattern = _VAT_COUNTRY_PATTERNS.get(country)
    if pattern and pattern.match(text):
        return text

    # fallback : accepte les formats inconnus si >= 8 chars alphanum
    if len(text) >= 8 and re.fullmatch(r"[A-Z]{2}[A-Z0-9]+", text):
        return text

    return None


_CURRENCY_SYMBOLS = {
    "€": "EUR",
    "$": "USD",
    "US$": "USD",
    "£": "GBP",
    "¥": "JPY",
    "₺": "TRY",
    "CHF": "CHF",
}
_CURRENCY_CODE_RE = re.compile(r"^[A-Z]{3}$")


def parse_currency(raw: str | None, default: str = "EUR") -> str:
    """Retourne un code devise ISO 4217. Fallback sur ``default`` (EUR par défaut)."""
    if not raw:
        return default

    text = str(raw).strip().upper()
    if not text:
        return default

    if text in _CURRENCY_SYMBOLS:
        return _CURRENCY_SYMBOLS[text]

    if _CURRENCY_CODE_RE.match(text):
        return text

    for symbol, code in _CURRENCY_SYMBOLS.items():
        if symbol in text:
            return code

    return default


def parse_vat_rate(raw: str | None) -> Decimal | None:
    """Parse un taux TVA ("24%", "0.24", "24,00"). Retourne un ratio entre 0 et 1."""
    if raw is None:
        return None
    text = str(raw).strip().replace("%", "").strip()
    if not text:
        return None
    value = parse_amount(text)
    if value is None:
        return None
    # si >1, on suppose que c'est un pourcentage (24 → 0.24)
    return value / Decimal(100) if value > 1 else value
