"""Shared Flow/Step primitives - single source for frp + flashing."""
import threading
from . import bridge


class FlowCancelled(RuntimeError):
    """Raised when the user hits Stop while a flow is running."""


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
    scope = _scope_key(key)
    _event(scope).clear()
    _cancel.clear()


def cancel_requested(key=None):
    """True if this scope was cancelled, or a broadcast STOP was issued."""
    if _cancel.is_set():
        return True
    return _event(_scope_key(key)).is_set()


class Step:
    def __init__(self, name, func):
        self.name = name
        self.func = func

    def run(self, ctx, log):
        if cancel_requested():
            raise FlowCancelled(f"cancelled before step {self.name}")
        log(f"[step] {self.name}")
        result = self.func(ctx, log)
        log(f"[done] {self.name}")
        return result


class Flow:
    def __init__(self, name, steps):
        self.name = name
        self.steps = steps

    def run(self, ctx, log):
        log(f"== running flow: {self.name} ==")
        bridge.set_log_hook(log)
        try:
            results = []
            for step in self.steps:
                results.append(step.run(ctx, log))
                if cancel_requested():
                    raise FlowCancelled("cancelled by user")
            log(f"== flow finished: {self.name} ==")
            return results
        finally:
            bridge.set_log_hook(None)
