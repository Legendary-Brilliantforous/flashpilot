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
