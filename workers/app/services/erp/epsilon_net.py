"""Epsilon Net ERP connector (Pylon / Hypersoft / Digital Accounting).

**Stub — URLs et payload exacts à valider avec la doc éditeur quand contrat signé.**
Hypothèse : API REST JSON moderne, auth Bearer + subscription header.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from app.services.erp.base import (
    ErpPermanentError,
    ErpTransientError,
    ExportResult,
)


@dataclass
class EpsilonNetConnector:
    base_url: str
    api_key: str
    subscription_id: str
    company_id: str | None = None
    timeout: int = 30
    kind: str = "epsilon_net"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Subscription-Id": self.subscription_id,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.company_id:
            headers["X-Company-Id"] = self.company_id
        return headers

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}{path}"
        try:
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            raise ErpTransientError(f"network: {exc}") from exc

        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise ErpTransientError(f"{resp.status_code}: {resp.text[:400]}")
        if resp.status_code >= 400:
            raise ErpPermanentError(f"{resp.status_code}: {resp.text[:400]}")

        try:
            return resp.json()
        except ValueError as exc:
            raise ErpPermanentError(f"invalid_json: {exc}") from exc

    def export_invoice(self, payload: dict[str, Any]) -> ExportResult:
        data = self._post("/api/v1/documents", payload)
        success = bool(data.get("success", True))
        external_id = (
            data.get("documentId")
            or data.get("id")
            or (data.get("document") or {}).get("id")
        )
        return ExportResult(
            external_id=str(external_id) if external_id else None,
            raw_response=str(data)[:4000],
            success=success,
        )

    def find_supplier_by_vat(self, vat_number: str) -> str | None:
        url = f"{self.base_url.rstrip('/')}/api/v1/suppliers"
        try:
            resp = requests.get(
                url,
                headers=self._headers(),
                params={"vat": vat_number, "limit": 1},
                timeout=self.timeout,
            )
        except requests.RequestException:
            return None
        if resp.status_code >= 400:
            return None
        data = resp.json()
        items = data.get("items") or data.get("data") or []
        if not items:
            return None
        first = items[0]
        return str(first.get("id") or first.get("supplierId") or "") or None
