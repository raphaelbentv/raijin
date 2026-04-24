"""Connector Epsilon Digital (stub — URLs/routes à confirmer avec doc éditeur).

Hypothèse : API REST JSON, auth Bearer, payload = XML base64 dans un envelope.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import requests

from app.services.mydata.base import (
    MyDataPermanentError,
    MyDataTransientError,
    StatusResult,
    SubmitResult,
)


@dataclass
class EpsilonConnector:
    base_url: str
    api_key: str
    timeout: int = 30
    kind: str = "epsilon_digital"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}{path}"
        try:
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            raise MyDataTransientError(f"network: {exc}") from exc

        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise MyDataTransientError(f"{resp.status_code}: {resp.text[:400]}")
        if resp.status_code >= 400:
            raise MyDataPermanentError(f"{resp.status_code}: {resp.text[:400]}")

        try:
            return resp.json()
        except ValueError as exc:
            raise MyDataPermanentError(f"invalid_json: {exc}") from exc

    def submit(self, xml_payload: bytes) -> SubmitResult:
        data = self._post(
            "/api/v1/mydata/invoices",
            {
                "format": "xml",
                "payload_b64": base64.b64encode(xml_payload).decode("ascii"),
            },
        )

        # Le mapping exact dépend de la doc Epsilon — hypothèse défensive ici.
        success = bool(data.get("success", True))
        mark = data.get("mark") or data.get("aadeMark")
        external_id = data.get("id") or data.get("externalId")
        uid = data.get("uid")

        return SubmitResult(
            external_id=str(external_id) if external_id is not None else None,
            aade_mark=str(mark) if mark is not None else None,
            uid=str(uid) if uid is not None else None,
            raw_response=str(data)[:4000],
            success=success,
        )

    def get_status(self, external_id: str) -> StatusResult:
        url = f"{self.base_url.rstrip('/')}/api/v1/mydata/invoices/{external_id}"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            raise MyDataTransientError(f"network: {exc}") from exc

        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise MyDataTransientError(f"{resp.status_code}: {resp.text[:400]}")
        if resp.status_code == 404:
            return StatusResult(status="unknown", aade_mark=None, raw_response=resp.text[:400])
        if resp.status_code >= 400:
            raise MyDataPermanentError(f"{resp.status_code}: {resp.text[:400]}")

        data = resp.json()
        return StatusResult(
            status=str(data.get("status", "unknown")),
            aade_mark=data.get("mark") or data.get("aadeMark"),
            raw_response=str(data)[:4000],
        )
