"""Shared Flow/Step primitives - single source for frp + flashing."""
from . import bridge
from . import cancel as _cancel_registry


class FlowCancelled(RuntimeError):
    """Raised when the user hits Stop while a flow is running."""


# Cooperative cancel lives in core/cancel.py (single registry shared with
# bridge.py). Same-named thin wrappers here so existing imports
# (core.py re-exports these; flows call cancel_requested()) keep working.
def _scope_key(key):
    return _cancel_registry._scope_key(key)


def _event(key):
    return _cancel_registry._event(key)


def request_cancel(key=None):
    return _cancel_registry.request_cancel(key)


def clear_cancel(key=None):
    return _cancel_registry.clear_cancel(key)


def cancel_requested(key=None):
    return _cancel_registry.cancel_requested(key)


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
