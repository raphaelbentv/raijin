"""Connector SoftOne myDATA (stub — remplace URLs/schema avec doc officielle).

Hypothèse : API JSON, auth par clientID + subscription key, wrap XML dans champ.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass

import requests

from app.services.mydata.base import (
    MyDataPermanentError,
    MyDataTransientError,
    StatusResult,
    SubmitResult,
)


@dataclass
class SoftOneConnector:
    base_url: str
    client_id: str
    client_secret: str
    subscription_id: str
    timeout: int = 30
    kind: str = "softone_mydata"

    def _headers(self) -> dict[str, str]:
        return {
            "X-Client-Id": self.client_id,
            "X-Client-Secret": self.client_secret,
            "X-Subscription": self.subscription_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def submit(self, xml_payload: bytes) -> SubmitResult:
        url = f"{self.base_url.rstrip('/')}/mydata/send"
        body = {"xml_base64": base64.b64encode(xml_payload).decode("ascii")}
        try:
            resp = requests.post(url, json=body, headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            raise MyDataTransientError(f"network: {exc}") from exc

        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise MyDataTransientError(f"{resp.status_code}: {resp.text[:400]}")
        if resp.status_code >= 400:
            raise MyDataPermanentError(f"{resp.status_code}: {resp.text[:400]}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise MyDataPermanentError(f"invalid_json: {exc}") from exc

        response = data.get("response") or data
        success = str(response.get("statusCode", "Success")).lower() in ("success", "ok")
        mark = response.get("invoiceMark") or response.get("mark")
        external_id = response.get("transactionId") or response.get("id")
        uid = response.get("invoiceUid") or response.get("uid")

        return SubmitResult(
            external_id=str(external_id) if external_id else None,
            aade_mark=str(mark) if mark else None,
            uid=str(uid) if uid else None,
            raw_response=str(data)[:4000],
            success=success,
        )

    def get_status(self, external_id: str) -> StatusResult:
        url = f"{self.base_url.rstrip('/')}/mydata/status/{external_id}"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            raise MyDataTransientError(f"network: {exc}") from exc
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise MyDataTransientError(f"{resp.status_code}: {resp.text[:400]}")
        if resp.status_code >= 400:
            raise MyDataPermanentError(f"{resp.status_code}: {resp.text[:400]}")

        data = resp.json()
        return StatusResult(
            status=str(data.get("status", "unknown")),
            aade_mark=data.get("invoiceMark") or data.get("mark"),
            raw_response=str(data)[:4000],
        )
