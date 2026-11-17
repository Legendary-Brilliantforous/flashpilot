"""Startup progress hook shared by the window build and the splash screen.

While the splash is visible, ``main()`` installs a callback here. Page builders
call :func:`stage` at natural boundaries, which lets the callback pump the event
loop (so the splash keeps animating instead of freezing during construction) and
report real progress to the bar.

With no hook installed — tests, headless imports, second windows — every call is
a cheap no-op.
"""
from __future__ import annotations

_HOOK = None


def set_hook(hook):
    """Install (or clear with ``None``) the startup callback.

    The callback is called as ``hook(fraction)`` where ``fraction`` is a
    ``0.0``–``1.0`` build stage or ``None`` for a plain "let the loop breathe".
    """
    global _HOOK
    _HOOK = hook


def get_hook():
    return _HOOK


def stage(fraction=None):
    """Report build progress and let the event loop run; never raises."""
    hook = _HOOK
    if hook is None:
        return
    try:
        hook(fraction)
    except Exception:
        pass
