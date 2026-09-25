"""Tests for stable multi-device identity (devices.py) + key-aware resolvers.

Contract under test:
* device_key() prefers ADB serial, then stable USB port path, then
  volatile bus:addr — so a key survives USB re-enumeration.
* Resolvers (find_samsung, _download_mode_device, _wait_for_adb,
  _wait_mtk_brom_target) accept key= and default to the ambient
  thread-scoped key, preserving legacy first-match when unset.
"""
import pytest

from python.core import devices


def _usb(vid=0x04E8, pid=0x6860, bus=2, address=7, serial="", ports="1-2",
         interfaces=None, product="SAMSUNG_Android", manufacturer="SAMSUNG"):
    return {
        "vid": vid, "pid": pid, "bus": bus, "address": address,
        "product": product, "manufacturer": manufacturer,
        "serial": serial, "port_numbers": ports,
        "interfaces": interfaces or [], "configs": 1, "active_config": 1,
    }


class TestDeviceKey:
    def test_adb_entry_key(self):
        assert devices.device_key({"serial": "R9X", "state": "device", "extra": ""}) == "adb:R9X"

    def test_usb_with_serial_merges_to_adb_key(self):
        assert devices.device_key(_usb(serial="R9X")) == "adb:R9X"

    def test_usb_without_serial_uses_port_path(self):
        assert devices.device_key(_usb(serial="", ports="1-2.3")) == "usb:1-2.3"

    def test_key_survives_reenumeration(self):
        before = _usb(bus=2, address=7, ports="1-2")
        after = _usb(bus=2, address=13, ports="1-2")
        assert devices.device_key(before) == devices.device_key(after)

    def test_volatile_fallback(self):
        d = _usb(serial="", ports="")
        d.pop("port_numbers")
        assert devices.device_key(d) == "usb:04e8:6860@2:7"

    def test_match_none_matches_all(self):
        assert devices.match_key(_usb(), None) is True
        assert devices.match_key(_usb(serial="A"), "adb:A") is True
        assert devices.match_key(_usb(serial="B"), "adb:A") is False


class TestDeviceScope:
    def test_scope_sets_and_restores(self):
        assert devices.current_key() is None
        with devices.device_scope("adb:X"):
            assert devices.current_key() == "adb:X"
            with devices.device_scope("usb:1-2"):
                assert devices.current_key() == "usb:1-2"
            assert devices.current_key() == "adb:X"
        assert devices.current_key() is None



class TestKeyedResolvers:
    def test_find_samsung_picks_keyed_device(self, monkeypatch):
        from python.core import bridge, mtp

        monkeypatch.setattr(
            bridge, "detect_usb",
            lambda: [_usb(serial="A", ports="1-1"), _usb(serial="B", ports="1-2")],
        )
        assert mtp.find_samsung() ["serial"] == "A"  # legacy first-match
        assert mtp.find_samsung(key="adb:B")["serial"] == "B"
        with devices.device_scope("adb:B"):
            assert mtp.find_samsung()["serial"] == "B"

    def test_download_mode_device_key_filter(self, monkeypatch):
        from python.core import bridge, core

        dl_a = _usb(pid=0x685D, serial="A", ports="1-1",
                    interfaces=[{"class": 10, "subclass": 0, "protocol": 0}])
        dl_b = _usb(pid=0x685D, serial="B", ports="1-2",
                    interfaces=[{"class": 10, "subclass": 0, "protocol": 0}])
        monkeypatch.setattr(bridge, "detect_usb", lambda: [dl_a, dl_b])
        assert core._download_mode_device()["serial"] == "A"
        assert core._download_mode_device(key="adb:B")["serial"] == "B"

    def test_wait_for_adb_pins_serial(self, monkeypatch):
        from python.core import bridge, core

        monkeypatch.setattr(
            bridge, "adb_status",
            lambda: [{"serial": "A", "state": "device", "extra": ""},
                     {"serial": "B", "state": "device", "extra": ""}],
        )
        ctx = {}
        assert core._wait_for_adb(ctx, lambda m: None, timeout=5, key="adb:B") is True
        assert ctx["serial"] == "B"

    def test_wait_mtk_prefers_keyed_device(self, monkeypatch):
        from python.core import core

        monkeypatch.setattr(
            core.mtk, "find_mtk",
            lambda: [{"vid": 0x0E8D, "pid": 0x0003, "bus": 1, "address": 2},
                     {"vid": 0x0E8D, "pid": 0x0003, "bus": 1, "address": 3}],
        )
        import io
        buf = io.StringIO()
        target, stage = core._wait_mtk_brom_target(buf.write, timeout=5)
        assert (target, stage) == ("1:2", "brom")  # legacy: first


class TestScopedCancel:
    """Cancel scopes: per-device request trips only that device; a keyless
    request broadcasts; clearing one scope never clears another."""

    def test_per_key_isolation(self):
        from python.core import flow as _flow

        _flow.clear_cancel(key="adb:A")
        _flow.clear_cancel(key="adb:B")
        assert _flow.cancel_requested(key="adb:A") is False
        _flow.request_cancel(key="adb:A")
        assert _flow.cancel_requested(key="adb:A") is True
        assert _flow.cancel_requested(key="adb:B") is False
        _flow.clear_cancel(key="adb:A")
        assert _flow.cancel_requested(key="adb:A") is False

    def test_broadcast_trips_all_scopes(self):
        from python.core import flow as _flow

        _flow.clear_cancel(key="adb:A")
        _flow.clear_cancel(key="adb:B")
        _flow.request_cancel()
        assert _flow.cancel_requested(key="adb:A") is True
        assert _flow.cancel_requested(key="adb:B") is True
        _flow.clear_cancel(key="adb:A")
        _flow.clear_cancel(key="adb:B")

    def test_ambient_scope_used_by_default(self):
        from python.core import devices, flow as _flow

        _flow.clear_cancel(key="adb:A")
        with devices.device_scope("adb:A"):
            _flow.request_cancel(key="adb:A")
            # No-arg check inside the scope sees the scoped event...
            assert _flow.cancel_requested() is True
        # ...while outside any scope the same scoped event is not consulted.
        assert _flow.cancel_requested(key="adb:B") is False
        _flow.clear_cancel(key="adb:A")
        assert _flow.cancel_requested(key="adb:A") is False



class TestRustMergedRows:
    """Phase 2: list_devices() consumes Rust `detect-merged` rows and adapts
    them to the legacy shape so GUI consumers are unchanged."""

    def test_rust_rows_adapted_to_legacy_shape(self, monkeypatch):
        from python.core import bridge

        rust_rows = [
            {
                "key": "adb:R9X", "label": "Samsung Galaxy · R9X",
                "transports": ["ADB"], "vid": 1256, "pid": 26717,
                "bus": 1, "address": 2, "serial": "R9X",
                "is_adb": False, "adb_state": "device",
                "usb_product": "SAMSUNG_Android",
                "usb_manufacturer": "SAMSUNG",
            },
            {
                "key": "adb:EMU1", "label": "EMU1 [device]",
                "transports": ["ADB"], "vid": 0, "pid": 0,
                "bus": 0, "address": 0, "serial": "EMU1",
                "is_adb": True, "adb_state": "device",
                "usb_product": None, "usb_manufacturer": None,
            },
        ]
        monkeypatch.setattr(bridge, "list_merged", lambda *a, **k: rust_rows)
        rows = devices.list_devices()
        assert [r["key"] for r in rows] == ["adb:R9X", "adb:EMU1"]
        # USB row: legacy usb dict carries the string descriptors the GUI reads
        assert rows[0]["usb"]["product"] == "SAMSUNG_Android"
        assert rows[0]["usb"]["manufacturer"] == "SAMSUNG"
        assert rows[0]["usb"]["serial"] == "R9X"
        assert rows[0]["adb"]["state"] == "device"
        # Standalone ADB row: no usb payload
        assert rows[1]["usb"] is None
        assert rows[1]["adb"]["serial"] == "EMU1"

    def test_bridge_error_propagates_no_fallback(self, monkeypatch):
        from python.core import bridge

        def boom(*a, **k):
            raise bridge.BridgeError("bridge gone")

        monkeypatch.setattr(bridge, "list_merged", boom)
        with pytest.raises(bridge.BridgeError):
            devices.list_devices()

    def test_malformed_rust_rows_dropped(self, monkeypatch):
        from python.core import bridge

        monkeypatch.setattr(bridge, "list_merged", lambda *a, **k: [
            {"label": "no key"},                # no key -> dropped
            {"key": "adb:X", "label": "ok", "transports": ["ADB"],
             "is_adb": True, "adb_state": "device", "serial": "X"},
        ])
        rows = devices.list_devices()
        assert [r["key"] for r in rows] == ["adb:X"]


class TestBackendActions:
    """actions_for / validate_action: backend-authoritative capability gate."""

    def test_actions_for_parses_payload(self, monkeypatch):
        import json as _json
        from python.core import bridge as _bridge

        payload = {
            "key": "adb:R9X",
            "profile": {"platform": "Android", "boot_mode": "SamsungDownload"},
            "actions": [{"id": "samsung_odin_flash", "display_name": "x", "description": "y"}],
        }

        def fake_run(args, timeout=30):
            assert args[:2] == ["actions-for", "adb:R9X"]
            return _json.dumps(payload)

        monkeypatch.setattr(_bridge, "_run", fake_run)
        out = _bridge.actions_for("adb:R9X")
        assert out["actions"][0]["id"] == "samsung_odin_flash"

    def test_actions_for_rejects_empty_key(self):
        from python.core import bridge as _bridge

        with pytest.raises(_bridge.BridgeError):
            _bridge.actions_for("")

    def test_validate_action_allowed(self, monkeypatch):
        import json as _json
        from python.core import bridge as _bridge

        def fake_run(args, timeout=30):
            assert args == ["validate-action", "adb:R9X", "frp_workflow"]
            return _json.dumps({"allowed": True, "key": "adb:R9X"})

        monkeypatch.setattr(_bridge, "_run", fake_run)
        out = _bridge.validate_action("adb:R9X", "frp_workflow")
        assert out["allowed"] is True

    def test_validate_action_rejected_maps_code(self, monkeypatch):
        from python.core import bridge as _bridge

        def fake_run(args, timeout=30):
            raise _bridge.BridgeError(
                "Device state error: Wrong mode: expected capabilities [...] "
                "actual: device adb:R9X in SamsungDownload with [...]"
            )

        monkeypatch.setattr(_bridge, "_run", fake_run)
        with pytest.raises(_bridge.BridgeError) as ei:
            _bridge.validate_action("adb:R9X", "qualcomm_edl_flash")
        assert getattr(ei.value, "code", "") == "ACTION_NOT_SUPPORTED"

    def test_validate_action_device_gone_keeps_identity_code(self, monkeypatch):
        from python.core import bridge as _bridge

        def fake_run(args, timeout=30):
            raise _bridge.USBError("USB error: Device not found [device adb:R9X]")

        monkeypatch.setattr(_bridge, "_run", fake_run)
        with pytest.raises(_bridge.BridgeError) as ei:
            _bridge.validate_action("adb:R9X", "frp_workflow")
        # Gone-device stays a USB/identity error, NOT action-not-supported.
        assert getattr(ei.value, "code", "") != "ACTION_NOT_SUPPORTED"


class TestJobActionGate:
    """Pre-execution gate mapping: job/mode -> backend action candidates."""

    def test_mapping_specificity(self):
        from python.core import actions as _a

        assert _a.actions_for_job("Flash Firmware", "Download mode") == ["samsung_odin_flash"]
        assert _a.actions_for_job("Flash Firmware", "EDL") == ["qualcomm_edl_flash"]
        assert _a.actions_for_job("Flash Firmware", "MTK") == ["mtk_brom_flash", "mtk_crash_to_brom"]
        assert _a.actions_for_job("Remove FRP", "ADB") == ["frp_workflow"]
        # Unmapped jobs (experimental/domain) skip the gate.
        assert _a.actions_for_job("Knox / Warranty", "ADB") is None
        assert _a.actions_for_job("Flash Firmware", "FASTBOOT") is None

    def test_allows_when_one_candidate_validates(self):
        from python.core import actions as _a

        calls = []

        def validate(key, aid):
            calls.append(aid)
            if aid != "mtk_crash_to_brom":
                raise RuntimeError("nope")
            return {"allowed": True}

        ok, err = _a.check_job_allowed("Flash Firmware", "MTK", "usb:1-2", validate)
        assert ok and err is None
        assert calls == ["mtk_brom_flash", "mtk_crash_to_brom"]

    def test_refuses_when_all_rejected(self):
        from python.core import actions as _a

        def validate(key, aid):
            raise RuntimeError("wrong mode")

        ok, err = _a.check_job_allowed("Remove FRP", "ADB", "usb:1-2", validate)
        assert not ok and isinstance(err, RuntimeError)

    def test_skips_unmapped_and_keyless(self):
        from python.core import actions as _a

        def boom(key, aid):  # pragma: no cover
            raise AssertionError("must not validate")

        assert _a.check_job_allowed("Knox / Warranty", "ADB", "usb:1-2", boom) == (True, None)
        assert _a.check_job_allowed("Remove FRP", "ADB", None, boom) == (True, None)


class TestUnifiedCancelRegistry:
    """flow.py and bridge.py share ONE cancel registry (core/cancel.py):
    a Stop from either side trips checks on both sides, per-key and
    broadcast alike."""

    def test_bridge_keyed_stop_trips_flow_check(self):
        from python.core import bridge as _bridge
        from python.core import flow as _flow

        _flow.clear_cancel(key="adb:A")
        _flow.clear_cancel(key="adb:B")
        _bridge.request_cancel(key="adb:A")
        assert _flow.cancel_requested(key="adb:A") is True
        assert _flow.cancel_requested(key="adb:B") is False
        assert _bridge.cancel_requested(key="adb:A") is True
        _bridge.clear_cancel(key="adb:A")

    def test_flow_keyed_stop_trips_bridge_run_loop(self):
        from python.core import bridge as _bridge
        from python.core import flow as _flow

        _bridge.clear_cancel(key="adb:A")
        _flow.request_cancel(key="adb:A")
        assert _bridge.cancel_requested(key="adb:A") is True
        _flow.clear_cancel(key="adb:A")
        assert _bridge.cancel_requested(key="adb:A") is False

    def test_broadcast_unified(self):
        from python.core import bridge as _bridge
        from python.core import core as _core
        from python.core import flow as _flow

        _flow.clear_cancel(key="adb:A")
        _bridge.clear_cancel(key="adb:A")
        _core.request_cancel()
        assert _flow.cancel_requested(key="adb:A") is True
        assert _bridge.cancel_requested(key="adb:A") is True
        assert _core.cancel_requested() is True
        _core.clear_cancel(key="adb:A")
        _bridge.clear_cancel(key="adb:A")


class TestFlashJobs:
    """FlashJob lifecycle: isolation, states, per-device cancel, logs."""

    def setup_method(self):
        from python.core import jobs as _jobs
        from python.core import cancel as _cancel

        _jobs._manager.reset()
        # Registry is process-global: earlier cancel tests may leave scopes
        # set (including the None ambient scope after a broadcast). Start
        # clean so per-device assertions are meaningful.
        _cancel.clear_cancel()
        _cancel.clear_cancel(key="adb:A")
        _cancel.clear_cancel(key="adb:B")

    def test_lifecycle_to_completed(self):
        from python.core import jobs as _jobs

        j = _jobs.start_job("adb:A", "Remove FRP", "ADB", "adb_frp", ["frp_workflow"])
        assert j.state == "CREATED" and j.is_active
        assert j.set_state("VALIDATED") is True
        assert j.set_state("RUNNING") is True
        assert _jobs.finish_job(j.job_id, "COMPLETED") is True
        assert j.state == "COMPLETED" and not j.is_active
        # Terminal states are sticky.
        assert j.set_state("RUNNING") is False
        assert j.state == "COMPLETED"

    def test_jobs_isolated_per_device(self):
        from python.core import jobs as _jobs

        a = _jobs.start_job("adb:A", "Remove FRP", "ADB", "adb_frp")
        b = _jobs.start_job("adb:B", "Remove FRP", "ADB", "adb_frp")
        assert a.job_id != b.job_id
        a.append_log("hello A")
        assert b.summary()["log_lines"] == 0
        assert a.summary()["log_lines"] == 1
        assert [j.job_id for j in _jobs.active_jobs("adb:A")] == [a.job_id]
        assert len(_jobs.active_jobs()) == 2

    def test_cancel_device_leaves_other_device_running(self):
        from python.core import jobs as _jobs

        a = _jobs.start_job("adb:A", "Remove FRP", "ADB", "adb_frp")
        b = _jobs.start_job("adb:B", "Remove FRP", "ADB", "adb_frp")
        cancelled = _jobs.cancel_device("adb:A")
        assert cancelled == [a.job_id]
        assert a.state == "CANCELLED"
        assert b.is_active
        # The shared cooperative registry observed the same stop.
        from python.core import cancel as _cancel

        assert _cancel.cancel_requested(key="adb:A") is True
        assert _cancel.cancel_requested(key="adb:B") is False
        _cancel.clear_cancel(key="adb:A")

    def test_classify_failure(self):
        from python.core import jobs as _jobs
        from python.core.flow import FlowCancelled
        from python.core.bridge import BridgeTimeout, BridgeError

        assert _jobs.classify_failure(FlowCancelled("x"))[0] == "CANCELLED"
        assert _jobs.classify_failure(BridgeTimeout("timed out", timeout=1))[0] == "TIMEOUT"
        # Plain errors keep no code; BridgeErrors keep their own code.
        assert _jobs.classify_failure(RuntimeError("boom")) == ("FAILED", "FAILED")
        assert _jobs.classify_failure(BridgeError("boom")) == ("FAILED", "BRIDGE_ERROR")

    def test_classify_scoped_to_device(self):
        """A timeout on phone B reads TIMEOUT even while phone A's scope
        is cancelled — cancellation is per-device, not global."""
        from python.core import cancel as _cancel
        from python.core import jobs as _jobs
        from python.core.bridge import BridgeTimeout

        _cancel.request_cancel(key="adb:A")
        assert _jobs.classify_failure(
            BridgeTimeout("bulk timed out", timeout=1), "adb:B")[0] == "TIMEOUT"
        assert _jobs.classify_failure(
            BridgeTimeout("bulk timed out", timeout=1), "adb:A")[0] == "CANCELLED"
        _cancel.clear_cancel(key="adb:A")

    def test_finished_history_pruned(self):
        from python.core import jobs as _jobs

        for _ in range(_jobs.MAX_FINISHED_JOBS + 5):
            j = _jobs.start_job("adb:A", "Read Device Info", "ADB", "x")
            _jobs.finish_job(j.job_id, "COMPLETED")
        remaining = len(_jobs._manager._jobs)
        assert remaining == _jobs.MAX_FINISHED_JOBS


class TestChipCommandActions:
    """Chip-page bridge commands map to backend validation candidates."""

    def test_known_commands(self):
        from python.core import actions as _a

        assert _a.actions_for_command("mtk-flash") == ["mtk_brom_flash"]
        assert _a.actions_for_command("mtk-frp") == ["frp_workflow"]
        assert _a.actions_for_command("mtk-backup") == ["backup_partitions"]
        assert _a.actions_for_command("qcom-flash") == ["qualcomm_edl_flash"]
        assert _a.actions_for_command("qcom-frp-reset") == ["frp_workflow"]
        assert _a.actions_for_command("spd-flash") == ["spd_flash"]
        assert _a.actions_for_command("spd-format") == ["spd_flash"]
        assert _a.actions_for_command("spd-boot") == ["reboot_device"]

    def test_unmodeled_commands_skip(self):
        from python.core import actions as _a

        assert _a.actions_for_command("mtk-bypass") is None
        assert _a.actions_for_command("") is None
        assert _a.actions_for_command(None) is None

    def test_check_actions_decision(self):
        from python.core import actions as _a

        def ok(key, aid):
            return {"allowed": True}

        def nope(key, aid):
            raise RuntimeError("wrong mode")

        assert _a.check_actions("usb:1-2", ["mtk_brom_flash"], ok) == (True, None)
        # Unmapped command: skip without calling validate.
        assert _a.check_actions("usb:1-2", None, ok) == (True, None)
        refused, err = _a.check_actions("usb:1-2", ["mtk_brom_flash"], nope)
        assert refused is False and isinstance(err, RuntimeError)


class TestButtonDisplayGate:
    """button_allowed: pure display-gating decision (fail-open)."""

    def test_command_buttons(self):
        from python.core import actions as _a

        edl = ["qualcomm_edl_flash", "frp_workflow", "read_device_info"]
        assert _a.button_allowed(command="qcom-flash", allowed_ids=edl) is True
        assert _a.button_allowed(command="mtk-flash", allowed_ids=edl) is False
        assert _a.button_allowed(command="spd-boot", allowed_ids=edl) is False
        assert _a.button_allowed(command="adb_shell", allowed_ids=edl) is False
        assert _a.button_allowed(command="adb_shell",
                                 allowed_ids=["adb_shell"]) is True

    def test_job_buttons(self):
        from python.core import actions as _a

        dl = ["samsung_odin_flash", "frp_workflow"]
        assert _a.button_allowed(job="Remove FRP", mode="ADB", allowed_ids=dl) is True
        assert _a.button_allowed(job="Remove MDM", mode="ADB", allowed_ids=dl) is False
        assert _a.button_allowed(job="Flash Firmware", mode="EDL", allowed_ids=dl) is False

    def test_unmapped_fail_open(self):
        from python.core import actions as _a

        assert _a.button_allowed(command="mtk-bypass", allowed_ids=[]) is True
        assert _a.button_allowed(job="Knox / Warranty", mode="ADB", allowed_ids=[]) is True
        assert _a.button_allowed(allowed_ids=[]) is True


class TestZeroTouchPresence:
    """adb_presence: poll paths must never open/claim/handshake USB."""

    def test_presence_uses_no_probe_flag(self, monkeypatch):
        from python.core import bridge as _bridge

        seen = {}

        def fake_run(args, timeout=15):
            seen["args"] = args
            return '["AAA\\tdevice product:x", "BBB\\tunknown transport:usb"]'

        monkeypatch.setattr(_bridge, "_run", fake_run)
        rows = _bridge.adb_presence()
        assert seen["args"] == ["adb-devices", "--no-probe"]
        assert rows[0].startswith("AAA\tdevice")
        st = _bridge.adb_presence_status()
        assert st == [
            {"serial": "AAA", "state": "device", "extra": "product:x"},
            {"serial": "BBB", "state": "unknown", "extra": "transport:usb"},
        ]

    def test_live_identity_getprop_burst_cached(self, monkeypatch):
        from python.core import bridge as _bridge
        from python.core import device_info as _di

        _di._LIVE_CACHE.update({"serials": None, "at": 0.0, "result": None})
        calls = {"shell": 0}
        monkeypatch.setattr(_di.bridge if hasattr(_di, "bridge") else _bridge,
                            "detect_all", lambda: [], raising=False)
        from python.core import bridge as _b2
        monkeypatch.setattr(_b2, "detect_all", lambda: [])
        rows = [{"serial": "R9XTEST1", "state": "device", "extra": ""}]
        monkeypatch.setattr(_b2, "adb_presence_status", lambda: rows)
        monkeypatch.setattr(_b2, "adb_status", lambda: rows)

        props = {"getprop ro.serialno": "R9XTEST1", "getprop ro.product.model": "M1"}

        def fake_shell(cmd, timeout=6, serial=None, rescue=True):
            calls["shell"] += 1
            assert serial == "R9XTEST1", f"unpinned getprop: {cmd}"
            return props.get(cmd, "")

        monkeypatch.setattr(_b2, "adb_shell", fake_shell)
        monkeypatch.setattr(_di, "_mtp_serial_and_build", lambda: ("", ""))
        monkeypatch.setattr(_di, "_usb_target_serial", lambda: "")

        r1 = _di.get_live_identity()
        assert r1["serial"] == "R9XTEST1" and r1["model"] == "M1"
        first_burst = calls["shell"]
        assert first_burst > 0
        # Second poll inside TTL: zero new native sessions.
        r2 = _di.get_live_identity()
        assert r2["serial"] == "R9XTEST1"
        assert calls["shell"] == first_burst
        # Serial change re-probes immediately.
        monkeypatch.setattr(_b2, "adb_presence_status",
                            lambda: [{"serial": "R9XTEST2", "state": "device", "extra": ""}])
        monkeypatch.setattr(_b2, "adb_status",
                            lambda: [{"serial": "R9XTEST2", "state": "device", "extra": ""}])
        _di.get_live_identity()
        assert calls["shell"] > first_burst
