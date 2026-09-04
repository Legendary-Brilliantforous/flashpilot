"""Tests for Flow/Step framework and cancellation (frp.py)."""
import pytest
import time
from python.core.core import Flow, Step, request_cancel, clear_cancel, cancel_requested, FlowCancelled


class TestFlowCancellation:
    """Test cooperative cancellation flow."""

    def test_cancel_requested_flow(self):
        clear_cancel()
        assert not cancel_requested()
        request_cancel()
        assert cancel_requested()
        clear_cancel()
        assert not cancel_requested()

    def test_step_cancelled_before_run(self):
        clear_cancel()
        request_cancel()
        step = Step("test", lambda ctx, log: "should not run")
        with pytest.raises(FlowCancelled, match="cancelled before step test"):
            step.run({}, lambda m: None)

    def test_step_cancelled_during_run(self):
        clear_cancel()
        def slow_step(ctx, log):
            time.sleep(0.1)
            request_cancel()
            return "done"
        step = Step("slow", slow_step)
        # Should not raise during run (checks at start and end)
        result = step.run({}, lambda m: None)
        assert result == "done"

    def test_flow_cancelled_between_steps(self):
        clear_cancel()
        results = []
        def step1(ctx, log):
            results.append("1")
            request_cancel()
            return "1"
        def step2(ctx, log):
            results.append("2")
            return "2"
        flow = Flow("test", [Step("s1", step1), Step("s2", step2)])
        with pytest.raises(FlowCancelled):
            flow.run({}, lambda m: None)
        assert results == ["1"]  # step2 never runs

    def test_flow_normal_completion(self):
        clear_cancel()
        results = []
        flow = Flow("test", [
            Step("a", lambda ctx, log: results.append("a")),
            Step("b", lambda ctx, log: results.append("b")),
        ])
        flow.run({}, lambda m: None)
        assert results == ["a", "b"]


class TestFlowContext:
    """Test context passing through flows."""

    def test_context_mutable(self):
        clear_cancel()
        ctx = {"counter": 0}
        def inc(ctx, log):
            ctx["counter"] += 1
        flow = Flow("test", [Step("inc", inc), Step("inc2", inc)])
        flow.run(ctx, lambda m: None)
        assert ctx["counter"] == 2


class TestRunGuard:
    """The GUI run-guard serializes operations PER DEVICE: two flows on the
    same phone can never overlap (so two destructive writes can't collide
    and a second clear_cancel() can't discard the in-flight cancel
    request), while different phones may run in parallel."""

    def test_second_flow_blocked_while_first_runs(self):
        from python.gui.qt_app import _flow_start, _flow_end, _flow_busy_msg
        assert _flow_start("Odin flash", destructive=True)
        assert not _flow_start("MTK flash", destructive=True)
        assert "still running" in _flow_busy_msg()
        _flow_end()

    def test_lock_released_after_end(self):
        from python.gui.qt_app import _flow_start, _flow_end
        assert _flow_start("op", destructive=False)
        _flow_end()
        assert _flow_start("op2", destructive=False)
        _flow_end()

    def test_busy_msg_mentions_blocking_flow(self):
        from python.gui.qt_app import _flow_start, _flow_end, _flow_busy_msg
        assert _flow_start("Carrier lock check", destructive=False)
        assert "Carrier lock check" in _flow_busy_msg()
        _flow_end()

    def test_different_devices_run_in_parallel(self):
        from python.gui.qt_app import _flow_start, _flow_end, _flows_running
        assert _flow_start("Flash A", destructive=True, key="adb:AAA")
        assert _flow_start("Flash B", destructive=True, key="adb:BBB")
        assert _flows_running() == 2
        assert not _flow_start("Flash A2", destructive=True, key="adb:AAA")
        _flow_end(key="adb:AAA")
        assert _flow_start("Flash A3", destructive=True, key="adb:AAA")
        _flow_end(key="adb:AAA")
        _flow_end(key="adb:BBB")
        assert _flows_running() == 0

    def test_busy_msg_names_same_device_op(self):
        from python.gui.qt_app import _flow_start, _flow_end, _flow_busy_msg
        assert _flow_start("Odin flash", destructive=True, key="adb:AAA")
        assert "Odin flash" in _flow_busy_msg(key="adb:AAA")
        _flow_end(key="adb:AAA")