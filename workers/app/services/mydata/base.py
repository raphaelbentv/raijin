from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class MyDataConnectorError(Exception):
    pass


class MyDataTransientError(MyDataConnectorError):
    """Réseau / 5xx / rate limit → retry."""


class MyDataPermanentError(MyDataConnectorError):
    """Erreur métier ou 4xx → pas de retry."""


@dataclass
class SubmitResult:
    external_id: str | None
    aade_mark: str | None
    uid: str | None
    raw_response: str
    success: bool


@dataclass
class StatusResult:
    status: str
    aade_mark: str | None
    raw_response: str


@runtime_checkable
class MyDataConnector(Protocol):
    """Contrat partagé entre Epsilon, SoftOne et AADE direct."""

    kind: str
    base_url: str

    def submit(self, xml_payload: bytes) -> SubmitResult: ...

    def get_status(self, external_id: str) -> StatusResult: ...
