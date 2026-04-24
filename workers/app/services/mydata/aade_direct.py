"""Connector direct AADE myDATA (utilisation fournisseur/OSPP — production stricte).

Endpoints AADE réels :
- Prod : https://mydatapi.aade.gr/myDATA/
- Test : https://mydataapidev.aade.gr/myDATA/
Auth : HTTP headers ``aade-user-id`` + ``Ocp-Apim-Subscription-Key``.
Payload : XML brut (pas JSON), POST /SendInvoices.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import requests

from app.services.mydata.base import (
    MyDataPermanentError,
    MyDataTransientError,
    StatusResult,
    SubmitResult,
)

_MARK_RE = re.compile(r"<invoiceMark>([^<]+)</invoiceMark>")
_UID_RE = re.compile(r"<invoiceUid>([^<]+)</invoiceUid>")
_STATUS_RE = re.compile(r"<statusCode>([^<]+)</statusCode>")


@dataclass
class AadeDirectConnector:
    base_url: str
    user_id: str
    subscription_key: str
    timeout: int = 30
    kind: str = "aade_direct"

    def _headers(self) -> dict[str, str]:
        return {
            "aade-user-id": self.user_id,
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Content-Type": "application/xml",
            "Accept": "application/xml",
        }

    def submit(self, xml_payload: bytes) -> SubmitResult:
        url = f"{self.base_url.rstrip('/')}/SendInvoices"
        try:
            resp = requests.post(url, data=xml_payload, headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            raise MyDataTransientError(f"network: {exc}") from exc

        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise MyDataTransientError(f"{resp.status_code}: {resp.text[:400]}")
        if resp.status_code >= 400:
            raise MyDataPermanentError(f"{resp.status_code}: {resp.text[:400]}")

        text = resp.text
        mark = _MARK_RE.search(text)
        uid = _UID_RE.search(text)
        status = _STATUS_RE.search(text)
        success = bool(status and status.group(1).lower() == "success")

        return SubmitResult(
            external_id=uid.group(1) if uid else None,
            aade_mark=mark.group(1) if mark else None,
            uid=uid.group(1) if uid else None,
            raw_response=text[:4000],
            success=success,
        )

    def get_status(self, external_id: str) -> StatusResult:
        url = f"{self.base_url.rstrip('/')}/RequestDocs"
        try:
            resp = requests.get(
                url,
                params={"mark": external_id},
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise MyDataTransientError(f"network: {exc}") from exc
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise MyDataTransientError(f"{resp.status_code}: {resp.text[:400]}")
        if resp.status_code >= 400:
            raise MyDataPermanentError(f"{resp.status_code}: {resp.text[:400]}")

        text = resp.text
        mark = _MARK_RE.search(text)
        return StatusResult(
            status="acknowledged" if mark else "pending",
            aade_mark=mark.group(1) if mark else None,
            raw_response=text[:4000],
        )
