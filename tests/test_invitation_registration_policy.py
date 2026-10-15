from unittest.mock import Mock
from importlib import import_module

import pytest
from fastapi import HTTPException

api = import_module("backend.api.app")


@pytest.mark.parametrize("mode", ["private_alpha", "production", "local", "development"])
@pytest.mark.parametrize("value", ["0", "false", "off", "invalid"])
def test_explicit_closed_registration_applies_in_every_mode(monkeypatch, mode, value):
    monkeypatch.setattr(api, "PRODUCT_MODE", mode)
    monkeypatch.setenv("CIVORA_ALLOW_PUBLIC_REGISTRATION", value)
    assert api._public_registration_allowed() is False


@pytest.mark.parametrize("user_count", [0, 1])
def test_closed_registration_cannot_bootstrap_or_create_an_account(monkeypatch, user_count):
    monkeypatch.setenv("CIVORA_ALLOW_PUBLIC_REGISTRATION", "false")
    monkeypatch.setattr(api, "PRODUCT_MODE", "private_alpha")
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = (user_count,)
    monkeypatch.setattr(api, "DB", Mock(connect=Mock(return_value=connection)))
    store = Mock()
    monkeypatch.setattr(api, "AUTH_STORE", store)
    with pytest.raises(HTTPException) as error:
        api.register(api.RegisterPayload(email="closed@example.test", password="Disposable-123", name="Closed"))
    assert error.value.status_code == 403
    store.register_user.assert_not_called()
    assert api.auth_status()["public_registration_enabled"] is False


def test_explicit_open_registration_and_legacy_local_defaults(monkeypatch):
    monkeypatch.setattr(api, "PRODUCT_MODE", "private_alpha")
    monkeypatch.delenv("CIVORA_ALLOW_PUBLIC_REGISTRATION", raising=False)
    assert api._public_registration_allowed() is True
    monkeypatch.setattr(api, "PRODUCT_MODE", "production")
    assert api._public_registration_allowed() is False
    monkeypatch.setenv("CIVORA_ALLOW_PUBLIC_REGISTRATION", "true")
    assert api._public_registration_allowed() is True
