from __future__ import annotations

import json

from raijin_shared.models.erp import ErpConnector as ConnectorModel
from raijin_shared.models.erp import ErpConnectorKind
from raijin_shared.security import decrypt

from app.services.erp.base import ErpConnector, ErpPermanentError
from app.services.erp.epsilon_net import EpsilonNetConnector
from app.services.erp.softone import SoftOneConnector


def _load_credentials(connector: ConnectorModel) -> dict:
    plain = decrypt(connector.credentials_encrypted)
    try:
        return json.loads(plain)
    except json.JSONDecodeError as exc:
        raise ErpPermanentError(f"invalid_credentials_json: {exc}") from exc


def build_erp_connector(connector: ConnectorModel) -> ErpConnector:
    creds = _load_credentials(connector)
    config = connector.config or {}

    if connector.kind == ErpConnectorKind.SOFTONE:
        missing = [k for k in ("username", "password", "app_id") if k not in creds]
        if missing:
            raise ErpPermanentError(f"missing_credentials:{missing}")
        return SoftOneConnector(
            base_url=connector.base_url,
            username=creds["username"],
            password=creds["password"],
            app_id=creds["app_id"],
            company=int(config.get("company", 1)),
            branch=int(config.get("branch", 1)),
            module=int(config.get("module", 0)),
            refid=int(config.get("refid", 1)),
            object_name=config.get("object", "FINDOC"),
            form_name=config.get("form", "FINDOC"),
        )

    if connector.kind == ErpConnectorKind.EPSILON_NET:
        missing = [k for k in ("api_key", "subscription_id") if k not in creds]
        if missing:
            raise ErpPermanentError(f"missing_credentials:{missing}")
        return EpsilonNetConnector(
            base_url=connector.base_url,
            api_key=creds["api_key"],
            subscription_id=creds["subscription_id"],
            company_id=config.get("company_id"),
        )

    raise ErpPermanentError(f"unknown_erp_kind:{connector.kind}")
