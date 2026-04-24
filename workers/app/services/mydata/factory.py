from __future__ import annotations

import json

from raijin_shared.models.mydata import MyDataConnector as ConnectorModel
from raijin_shared.models.mydata import MyDataConnectorKind
from raijin_shared.security import decrypt

from app.services.mydata.aade_direct import AadeDirectConnector
from app.services.mydata.base import MyDataConnector, MyDataPermanentError
from app.services.mydata.epsilon import EpsilonConnector
from app.services.mydata.softone import SoftOneConnector


def _load_credentials(connector: ConnectorModel) -> dict:
    plain = decrypt(connector.credentials_encrypted)
    try:
        return json.loads(plain)
    except json.JSONDecodeError as exc:
        raise MyDataPermanentError(f"invalid_credentials_json: {exc}") from exc


def build_connector(connector: ConnectorModel) -> MyDataConnector:
    creds = _load_credentials(connector)

    if connector.kind == MyDataConnectorKind.EPSILON_DIGITAL:
        missing = [k for k in ("api_key",) if k not in creds]
        if missing:
            raise MyDataPermanentError(f"missing_credentials:{missing}")
        return EpsilonConnector(base_url=connector.base_url, api_key=creds["api_key"])

    if connector.kind == MyDataConnectorKind.SOFTONE_MYDATA:
        missing = [
            k for k in ("client_id", "client_secret", "subscription_id") if k not in creds
        ]
        if missing:
            raise MyDataPermanentError(f"missing_credentials:{missing}")
        return SoftOneConnector(
            base_url=connector.base_url,
            client_id=creds["client_id"],
            client_secret=creds["client_secret"],
            subscription_id=creds["subscription_id"],
        )

    if connector.kind == MyDataConnectorKind.AADE_DIRECT:
        missing = [k for k in ("user_id", "subscription_key") if k not in creds]
        if missing:
            raise MyDataPermanentError(f"missing_credentials:{missing}")
        return AadeDirectConnector(
            base_url=connector.base_url,
            user_id=creds["user_id"],
            subscription_key=creds["subscription_key"],
        )

    raise MyDataPermanentError(f"unknown_connector_kind:{connector.kind}")
