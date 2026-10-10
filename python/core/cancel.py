"""Single cooperative-cancel registry (single source of truth).

Historically ``flow.py`` and ``bridge.py`` each kept their own ``_cancel`` /
``_cancels`` event sets with identical shapes. A GUI Stop tripped only the
bridge set (killing subprocesses) while flow-level ``cancel_requested()``
checks consulted the flow set — the two halves of one cancellation could
disagree, and per-key scopes lived in two places.

This module owns the ONLY event set now. ``flow`` and ``bridge`` keep
thin same-named wrappers (zero call-site churn: ``core`` re-exports flow's
names, the GUI calls both modules' names).

Semantics (unchanged, now actually shared):
* ``request_cancel()`` with no key = broadcast: trips the global bus AND
  every per-device scope (global STOP behaviour).
* ``request_cancel(key)`` trips exactly one device scope.
* ``clear_cancel(key)`` clears the scope (ambient thread scope by default)
  plus the broadcast bus, so a fresh op never starts already-cancelled.
* ``cancel_requested(key)`` is true when the scope OR the broadcast is set.
"""

import threading

_cancel = threading.Event()
_cancels = {}  # device-key -> Event; the None/global entry is the broadcast bus
_cancels_lock = threading.Lock()


def _scope_key(key):
    """Explicit key wins, else the ambient thread-scoped device key."""
    if key is not None:
        return key
    try:
        from . import devices as _dev

        return _dev.current_key()
    except Exception:
        return None


def _event(key):
    with _cancels_lock:
        ev = _cancels.get(key)
        if ev is None:
            ev = threading.Event()
            _cancels[key] = ev
        return ev


def request_cancel(key=None):
    """Request cancellation. ``key=None`` broadcasts to every running
    operation (global STOP behaviour, unchanged); an explicit key cancels
    only that device's operation."""
    if key is None:
        _cancel.set()
        with _cancels_lock:
            for ev in _cancels.values():
                ev.set()
    else:
        _event(key).set()


def clear_cancel(key=None):
    """Clear a pending cancel. Scoped to ``key`` (ambient thread scope by
    default) plus the broadcast bus, so a fresh operation never starts
    already-cancelled — without touching other devices' scopes."""
    _event(_scope_key(key)).clear()
    _cancel.clear()


def cancel_requested(key=None):
    """True if this scope was cancelled, or a broadcast STOP was issued."""
    if _cancel.is_set():
        return True
    return _event(_scope_key(key)).is_set()
