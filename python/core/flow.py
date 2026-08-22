"""Shared Flow/Step primitives - single source for frp + flashing."""
import threading
from . import bridge


class FlowCancelled(RuntimeError):
    """Raised when the user hits Stop while a flow is running."""


_cancel = threading.Event()


def request_cancel():
    _cancel.set()


def clear_cancel():
    _cancel.clear()


def cancel_requested():
    return _cancel.is_set()


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
