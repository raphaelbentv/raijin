from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class ErpConnectorError(Exception):
    pass


class ErpTransientError(ErpConnectorError):
    """Réseau, 5xx, rate limit → retry."""


class ErpPermanentError(ErpConnectorError):
    """4xx, validation métier → pas de retry."""


@dataclass
class ExportResult:
    external_id: str | None
    raw_response: str
    success: bool


@runtime_checkable
class ErpConnector(Protocol):
    kind: str
    base_url: str

    def export_invoice(self, payload: dict[str, Any]) -> ExportResult: ...

    def find_supplier_by_vat(self, vat_number: str) -> str | None: ...
