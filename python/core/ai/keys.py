"""API-key storage for the AI advisor — system keyring only.

The advisor must never leave a key on disk in plaintext, so this module has
exactly one storage backend: the OS keyring (Secret Service / KWallet). When
no backend is usable the advisor stays *disabled* with an explicit reason —
there is no silent fallback to ``config.json``, an env file, or a 0600 file.

Nothing in this module ever logs or returns a key except :func:`get_key` and
the masked preview from :func:`mask_key`.
"""

from __future__ import annotations

SERVICE = "flashpilot-ai"

try:  # pragma: no cover - exercised through the fake backend in tests
    import keyring  # type: ignore
    from keyring.errors import KeyringError  # type: ignore
    _IMPORT_ERROR = None
except Exception as _exc:  # noqa: BLE001 - any import failure means "disabled"
    keyring = None

    class KeyringError(Exception):
        """Stand-in when the ``keyring`` package is unavailable."""

    _IMPORT_ERROR = _exc


def _backend():
    """The active keyring backend object, or ``None`` when unusable."""
    if keyring is None:
        return None
    try:
        return keyring.get_keyring()
    except Exception:  # noqa: BLE001
        return None


def backend_name() -> str:
    """Human-readable backend name (``"unavailable"`` when there is none)."""
    backend = _backend()
    if backend is None:
        return "unavailable"
    return type(backend).__name__


def available() -> tuple[bool, str]:
    """Return ``(usable, reason)`` for the current keyring state.

    A backend that resolves to the ``fail``/``null`` implementation (the
    keyring package's way of saying "no Secret Service here") counts as
    unavailable, because storing a key there silently drops it.
    """
    if keyring is None:
        return False, (
            "the Python 'keyring' package is not installed "
            f"({_IMPORT_ERROR})"
        )
    backend = _backend()
    if backend is None:
        return False, "the OS keyring did not return a backend"
    name = f"{type(backend).__module__}.{type(backend).__name__}".lower()
    if "fail" in name or "null" in name:
        return False, (
            "no Secret Service backend is running — install gnome-keyring "
            "or KWallet, then reopen Settings → AI"
        )
    return True, type(backend).__name__


def get_key(provider_id: str) -> str | None:
    """Return the stored key for *provider_id*, or ``None``."""
    usable, _ = available()
    if not usable:
        return None
    try:
        value = keyring.get_password(SERVICE, provider_id)
    except KeyringError:
        return None
    return value or None


def set_key(provider_id: str, api_key: str) -> None:
    """Store *api_key* in the keyring. Raises ``RuntimeError`` if unusable."""
    usable, reason = available()
    if not usable:
        raise RuntimeError(f"API keys need a system keyring: {reason}")
    keyring.set_password(SERVICE, provider_id, api_key)


def delete_key(provider_id: str) -> None:
    """Remove the stored key, ignoring "not found"."""
    usable, _ = available()
    if not usable:
        return
    try:
        keyring.delete_password(SERVICE, provider_id)
    except KeyringError:
        pass


def mask_key(api_key: str | None) -> str:
    """A safe preview (``sk-…c3f9``) for the settings field and logs."""
    if not api_key:
        return ""
    key = api_key.strip()
    if len(key) <= 8:
        return "•" * len(key)
    return f"{key[:3]}…{key[-4:]}"
