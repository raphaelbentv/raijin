"""Tests unitaires pour le service SAML : settings builder, parsing identity, strip cert."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from raijin_shared.models.sprint_6_10 import SamlConfig
from raijin_shared.models.tenant import Tenant

from app.services.saml import (
    SamlNotConfiguredError,
    SamlValidationError,
    _strip_cert,
    build_saml_settings,
    extract_saml_identity,
)


def _tenant() -> Tenant:
    t = Tenant(name="Acme", slug="acme", country_code="FR", default_currency="EUR")
    return t


def _config(enabled: bool = True, **overrides) -> SamlConfig:
    defaults = dict(
        entity_id="http://idp.example.com/entity",
        sso_url="https://idp.example.com/sso",
        certificate="-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----",
        is_enabled=enabled,
    )
    defaults.update(overrides)
    return SamlConfig(**defaults)


def test_strip_cert_removes_headers_and_whitespace() -> None:
    raw = """-----BEGIN CERTIFICATE-----
MIIB
AAAA
-----END CERTIFICATE-----"""
    assert _strip_cert(raw) == "MIIBAAAA"


def test_strip_cert_accepts_already_stripped_base64() -> None:
    assert _strip_cert("MIIBAAAA") == "MIIBAAAA"


def test_build_saml_settings_happy_path() -> None:
    config = _config()
    tenant = _tenant()
    settings = build_saml_settings(config, tenant)
    assert settings["sp"]["entityId"].endswith("/auth/saml/metadata/acme")
    assert settings["sp"]["assertionConsumerService"]["url"].endswith("/auth/saml/acs/acme")
    assert settings["idp"]["entityId"] == "http://idp.example.com/entity"
    assert settings["idp"]["singleSignOnService"]["url"] == "https://idp.example.com/sso"
    assert settings["idp"]["x509cert"] == "AAAA"
    assert settings["security"]["wantAssertionsSigned"] is True


def test_build_saml_settings_raises_when_incomplete() -> None:
    incomplete = _config(sso_url=None)
    with pytest.raises(SamlNotConfiguredError):
        build_saml_settings(incomplete, _tenant())


def test_extract_identity_from_email_attribute() -> None:
    auth = MagicMock()
    auth.get_attributes.return_value = {
        "email": ["alice@example.com"],
        "displayName": ["Alice Martin"],
    }
    auth.get_nameid.return_value = None
    email, name = extract_saml_identity(auth)
    assert email == "alice@example.com"
    assert name == "Alice Martin"


def test_extract_identity_falls_back_to_nameid() -> None:
    auth = MagicMock()
    auth.get_attributes.return_value = {}
    auth.get_nameid.return_value = "bob@example.com"
    email, name = extract_saml_identity(auth)
    assert email == "bob@example.com"
    assert name is None


def test_extract_identity_combines_given_and_surname_when_no_display_name() -> None:
    auth = MagicMock()
    auth.get_attributes.return_value = {
        "email": ["carol@example.com"],
        "givenName": ["Carol"],
        "surname": ["Jones"],
    }
    auth.get_nameid.return_value = None
    email, name = extract_saml_identity(auth)
    assert email == "carol@example.com"
    assert name == "Carol Jones"


def test_extract_identity_raises_without_email() -> None:
    auth = MagicMock()
    auth.get_attributes.return_value = {}
    auth.get_nameid.return_value = None
    with pytest.raises(SamlValidationError):
        extract_saml_identity(auth)
