"""Keyring-only API-key storage: no plaintext fallback, ever."""

from __future__ import annotations

import pytest

from python.core.ai import keys


class _FakeKeyring:
    def __init__(self):
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self.store.get((service, username))

    def set_password(self, service, username, value):
        self.store[(service, username)] = value

    def delete_password(self, service, username):
        if (service, username) not in self.store:
            raise keys.KeyringError("not found")
        del self.store[(service, username)]


class _FakeBackend:
    pass


@pytest.fixture()
def fake_keyring(monkeypatch):
    fake = _FakeKeyring()
    monkeypatch.setattr(keys, "keyring", fake)
    monkeypatch.setattr(
        keys, "KeyringError", type("KeyringError", (Exception,), {})
    )
    monkeypatch.setattr(keys, "_backend", lambda: _FakeBackend())
    return fake


def test_roundtrip_store_get_delete(fake_keyring):
    assert keys.available()[0] is True
    assert keys.get_key("openai") is None
    keys.set_key("openai", "sk-secret")
    assert keys.get_key("openai") == "sk-secret"
    assert fake_keyring.store[(keys.SERVICE, "openai")] == "sk-secret"
    keys.delete_key("openai")
    assert keys.get_key("openai") is None


def test_missing_package_disables_storage(monkeypatch):
    monkeypatch.setattr(keys, "keyring", None)
    usable, reason = keys.available()
    assert usable is False
    assert "keyring" in reason
    with pytest.raises(RuntimeError):
        keys.set_key("openai", "sk-secret")
    assert keys.get_key("openai") is None


def test_fail_backend_counts_as_unavailable(monkeypatch):
    class Keyring:  # name matches the keyring fail backend convention
        pass

    Keyring.__module__ = "keyring.backends.fail"
    monkeypatch.setattr(keys, "keyring", object())
    monkeypatch.setattr(keys, "_backend", lambda: Keyring())
    usable, reason = keys.available()
    assert usable is False
    assert "Secret Service" in reason


def test_mask_key_never_reveals_the_secret():
    masked = keys.mask_key("sk-proj-abcdefgh12345678")
    assert masked.startswith("sk-")
    assert masked.endswith("5678")
    assert "abcdefgh" not in masked
    assert keys.mask_key("") == ""
    assert set(keys.mask_key("short")) == {"•"}
