"""Experimental per-run gates + safety backup surfacing.

- Token helpers: counted, single-use, expiring, feature-bound.
- Migrated flows (apple iCloud, Pixel fastboot) enforce strict gates:
  no ack -> RuntimeError naming the ack (no device needed to prove it);
  ctx ack -> gate passes (fails later on missing device/input, never on ack).
- Safety backup failures are bannered loudly and never raise.
"""

import pytest

from python.core import experimental as exp
from python.core import flow as _flow
from python.core import safety


@pytest.fixture(autouse=True)
def _no_cancel():
    # Other suites leave the global broadcast cancel set; wait-loops and
    # flow steps would instantly raise FlowCancelled. Isolate.
    _flow.clear_cancel()
    yield
    _flow.clear_cancel()


def _logs():
    logs = []
    return logs, logs.append


def test_token_note_counts_and_consume_is_single_use():
    store = {}
    exp.token_note(store, "qcn_imei_repair")
    exp.token_note(store, "qcn_imei_repair")
    assert exp.token_consume(store, "qcn_imei_repair", now=1000.0) is True
    assert exp.token_consume(store, "qcn_imei_repair", now=1001.0) is True
    assert exp.token_consume(store, "qcn_imei_repair", now=1002.0) is False


def test_token_consume_is_feature_bound():
    store = {}
    exp.token_note(store, "qcn_backup", now=1000.0)
    assert exp.token_consume(store, "knox_bypass", now=1001.0) is False
    assert exp.token_consume(store, "qcn_backup", now=1001.0) is True


def test_stale_tokens_expire():
    store = {}
    exp.token_note(store, "emmc_ufs_raw", now=1000.0)
    assert exp.token_consume(store, "emmc_ufs_raw", now=1000.0 + exp.ACK_TOKEN_TTL + 1) is False
    store2 = {}
    exp.token_note(store2, "emmc_ufs_raw", now=5000.0)
    assert exp.token_consume(store2, "emmc_ufs_raw", now=5000.0 + exp.ACK_TOKEN_TTL - 1) is True
    # Boundary: exactly TTL is still fresh (<=), past it is stale.
    store3 = {}
    exp.token_note(store3, "emmc_ufs_raw", now=7000.0)
    assert exp.token_consume(store3, "emmc_ufs_raw", now=7000.0 + exp.ACK_TOKEN_TTL) is True


def test_token_helpers_tolerate_garbage():
    assert exp.token_note(None, "x") == {}
    assert exp.token_consume(None, "x") is False
    assert exp.token_consume({}, "") is False
    assert exp.token_consume({"a": [1, 2]}, "a", now=10 ** 9) is False


def test_apple_flows_require_per_run_ack():
    from python.core import apple

    logs, log = _logs()
    try:
        apple.flow_apple_icloud_remove().run({}, log)
        raise AssertionError("expected RuntimeError")
    except RuntimeError as e:
        assert "per-run ack" in str(e)
    try:
        apple.flow_apple_icloud_add().run({}, log)
        raise AssertionError("expected RuntimeError")
    except RuntimeError as e:
        assert "per-run ack" in str(e)
    # With a per-run ack the gate passes; the flow then fails on missing
    # Apple tooling (no usbmuxd here) — proving the failure moved past the
    # gate instead of through it.
    for flow_fn in (apple.flow_apple_icloud_remove, apple.flow_apple_icloud_add):
        try:
            flow_fn().run({"experimental_ack": True}, log)
        except RuntimeError as e:
            assert "per-run ack" not in str(e)


def test_pixel_flows_require_per_run_ack():
    from python.core import fastboot as fb

    logs, log = _logs()
    for flow_fn in (fb.flow_fastboot_unlock, fb.flow_fastboot_flash_factory,
                    fb.flow_fastboot_flash_single):
        try:
            flow_fn().run({}, log)
            raise AssertionError("expected RuntimeError")
        except RuntimeError as e:
            assert "per-run ack" in str(e)
    # Gate passes with ack; flow then fails on missing device/input —
    # proving the failure moved past the gate, not through it.
    try:
        fb.flow_fastboot_unlock().run({"experimental_ack": True}, log)
    except RuntimeError as e:
        assert "per-run ack" not in str(e)


def test_safety_failure_is_bannered_not_buried(monkeypatch):
    import types

    def boom(*a, **k):
        raise RuntimeError("USB stall")
    fake_bridge = types.SimpleNamespace(_run=boom)

    logs, log = _logs()
    assert safety._dump_spd(fake_bridge, "t", "f", 0, "", None, "/tmp/x", log) == []
    text = "\n".join(logs)
    assert "PRE-FLASH BACKUP FAILED" in text
    assert "WITHOUT a restore point" in text
    assert "USB stall" in text


def test_preflash_never_raises_and_reports(monkeypatch, tmp_path):
    import types

    monkeypatch.setenv("HOME", str(tmp_path))

    def boom(*a, **k):
        raise RuntimeError("boom")
    fake_bridge = types.SimpleNamespace(_run=boom)

    logs, log = _logs()
    out = safety.preflash_backup("spd", fake_bridge, log, target="t",
                                 fdl1="f", a1=0, ident="t1")
    assert out != ""  # out dir still returned; operation may proceed
    assert "PRE-FLASH BACKUP FAILED" in "\n".join(logs)
