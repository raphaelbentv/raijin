"""SoftOne ERP connector (Genesis / Atlantis / Cloud).

Base API : POST ``{base_url}/s1services`` (JSON body).
Flow :
  1. ``{service: login, username, password, appId}`` → ``clientID`` + companies
  2. ``{service: authenticate, clientID, company, branch, module, refid}`` → new clientID authed
  3. ``{service: setData, clientID, object: FINDOC, form: FINDOC, data: {...}}`` → create doc

Références : https://manuals.softone.gr/general/s1services (docs publiques).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests

from app.services.erp.base import (
    ErpPermanentError,
    ErpTransientError,
    ExportResult,
)


@dataclass
class SoftOneConnector:
    base_url: str
    username: str
    password: str
    app_id: str = "3001"
    company: int = 1
    branch: int = 1
    module: int = 0
    refid: int = 1
    object_name: str = "FINDOC"
    form_name: str = "FINDOC"
    timeout: int = 30
    kind: str = "softone"

    _client_id: str | None = field(default=None, init=False, repr=False)

    def _endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/s1services"

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = requests.post(self._endpoint(), json=body, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ErpTransientError(f"network: {exc}") from exc

        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise ErpTransientError(f"{resp.status_code}: {resp.text[:400]}")
        if resp.status_code >= 400:
            raise ErpPermanentError(f"{resp.status_code}: {resp.text[:400]}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise ErpPermanentError(f"invalid_json: {exc}") from exc

        if isinstance(data, dict) and data.get("success") is False:
            error = data.get("error") or data.get("errorcode") or "unknown"
            # 1005 = login failure, 100 = permission, etc.  — traitement comme permanent.
            raise ErpPermanentError(f"softone_error: {error}: {data}")
        return data

    def _login(self) -> str:
        data = self._post(
            {
                "service": "login",
                "username": self.username,
                "password": self.password,
                "appId": self.app_id,
            }
        )
        if "clientID" not in data:
            raise ErpPermanentError(f"login_no_clientID: {data}")
        return str(data["clientID"])

    def _authenticate(self, client_id: str) -> str:
        data = self._post(
            {
                "service": "authenticate",
                "clientID": client_id,
                "company": self.company,
                "branch": self.branch,
                "module": self.module,
                "refid": self.refid,
            }
        )
        if "clientID" not in data:
            raise ErpPermanentError(f"authenticate_no_clientID: {data}")
        return str(data["clientID"])

    def _ensure_session(self) -> str:
        if self._client_id:
            return self._client_id
        login_cid = self._login()
        self._client_id = self._authenticate(login_cid)
        return self._client_id

    def export_invoice(self, payload: dict[str, Any]) -> ExportResult:
        client_id = self._ensure_session()
        body = {
            "service": "setData",
            "clientID": client_id,
            "appId": self.app_id,
            "object": self.object_name,
            "form": self.form_name,
            "data": payload,
        }
        data = self._post(body)
        # Response shape: {"success": true, "id": "1234", "rowcount": 1}
        external_id = data.get("id") or data.get("FINDOC")
        return ExportResult(
            external_id=str(external_id) if external_id else None,
            raw_response=str(data)[:4000],
            success=bool(data.get("success", True)),
        )

    def find_supplier_by_vat(self, vat_number: str) -> str | None:
        """Cherche un TRDR (supplier) par VAT. Retourne l'ID SoftOne ou None."""
        client_id = self._ensure_session()
        body = {
            "service": "getData",
            "clientID": client_id,
            "appId": self.app_id,
            "object": "TRDR",
            "list": True,
            "filter": {"AFM": vat_number},
            "selectFields": "TRDR",
        }
        try:
            data = self._post(body)
        except ErpPermanentError:
            return None
        rows = data.get("rows") or data.get("data") or []
        if not rows:
            return None
        first = rows[0]
        return str(first.get("TRDR")) if isinstance(first, dict) and first.get("TRDR") else None
