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


class TestListDevices:
    def test_usb_adb_merge_and_standalone(self, monkeypatch):
        from python.core import bridge

        monkeypatch.setattr(
            bridge, "detect_all",
            lambda: [_usb(serial="R9X", ports="1-2"),
                     _usb(pid=0x685D, serial="", ports="1-3",
                          interfaces=[{"class": 10, "subclass": 0, "protocol": 0}])],
        )
        monkeypatch.setattr(
            bridge, "adb_status",
            lambda: [{"serial": "R9X", "state": "device", "extra": ""},
                     {"serial": "EMUL", "state": "device", "extra": ""}],
        )
        rows = devices.list_devices()
        by_key = {r["key"]: r for r in rows}
        assert "adb:R9X" in by_key  # merged USB+ADB row
        assert by_key["adb:R9X"]["adb"]["state"] == "device"
        assert "ADB" in by_key["adb:R9X"]["transports"]
        assert "adb:EMUL" in by_key  # standalone ADB row
        assert "usb:1-3" in by_key  # serial-less USB row

    def test_candidates_for_modes(self, monkeypatch):
        from python.core import bridge

        monkeypatch.setattr(
            bridge, "detect_all",
            lambda: [_usb(serial="R9X", ports="1-2"),
                     _usb(vid=0x0E8D, pid=0x0003, bus=1, address=2,
                          serial="", ports="1-4", product="MediaTek USB Port")],
        )
        monkeypatch.setattr(bridge, "adb_status", lambda: [])
        got = devices.candidates_for_modes({"MTK BROM"})
        assert [r["key"] for r in got] == ["usb:1-4"]

    def test_resolve_usb_target_follows_reenumeration(self, monkeypatch):
        from python.core import bridge

        state = {"addr": 7}
        monkeypatch.setattr(
            bridge, "detect_all",
            lambda: [_usb(bus=2, address=state["addr"], ports="1-2")],
        )
        assert devices.resolve_usb_target("usb:1-2") == "04e8:6860@2:7"
        state["addr"] = 13  # phone re-enumerated
        assert devices.resolve_usb_target("usb:1-2") == "04e8:6860@2:13"
        assert devices.resolve_usb_target("usb:9-9") is None


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


class TestPhoneFilter:
    """list_devices() must show phones only — never hubs, HID, webcams or
    card readers (regression: one plugged-in modem showed as ~10 devices)."""

    def _peripheral(self, vid, pid, ports, cls, serial=""):
        return {"vid": vid, "pid": pid, "bus": 1, "address": 2,
                "product": "p", "manufacturer": "m", "serial": serial,
                "port_numbers": ports,
                "interfaces": [{"class": cls, "subclass": 0, "protocol": 0}]}

    def test_peripherals_excluded(self, monkeypatch):
        from python.core import bridge

        monkeypatch.setattr(bridge, "detect_all", lambda: [
            self._peripheral(0x1D6B, 0x0002, "1", 9),          # hub
            self._peripheral(0x0461, 0x0010, "1-4", 3),        # keyboard (HID)
            self._peripheral(0x1BCF, 0x2802, "1-5", 14),       # webcam (video)
            self._peripheral(0x0A5C, 0x5800, "1-6", 11, serial="0123456789ABCD"),  # card reader
        ])
        monkeypatch.setattr(bridge, "adb_status", lambda: [])
        assert devices.list_devices() == []

    def test_known_vendor_vids_included(self, monkeypatch):
        from python.core import bridge

        monkeypatch.setattr(bridge, "detect_all", lambda: [
            {"vid": v, "pid": 0x0001, "bus": 1, "address": 2, "serial": "",
             "port_numbers": f"9-{i}", "interfaces": []}
            for i, v in enumerate([0x04E8, 0x05C6, 0x0E8D, 0x1782, 0x18D1, 0x05AC])
        ])
        monkeypatch.setattr(bridge, "adb_status", lambda: [])
        assert len(devices.list_devices()) == 6

    def test_generic_android_heuristics(self, monkeypatch):
        from python.core import bridge

        adb_iface = [{"class": 255, "subclass": 66, "protocol": 1}]
        mtp_iface = [{"class": 6, "subclass": 1, "protocol": 1}]
        monkeypatch.setattr(bridge, "detect_all", lambda: [
            {"vid": 0x2717, "pid": 1, "bus": 1, "address": 2, "serial": "",
             "port_numbers": "7-1", "interfaces": []},                       # generic VID (Xiaomi)
            {"vid": 0x1234, "pid": 1, "bus": 1, "address": 3, "serial": "",
             "port_numbers": "7-2", "interfaces": adb_iface},                # ADB gadget
            {"vid": 0x1234, "pid": 2, "bus": 1, "address": 4, "serial": "",
             "port_numbers": "7-3", "interfaces": mtp_iface},                # MTP iface
            {"vid": 0x1234, "pid": 3, "bus": 1, "address": 5, "serial": "",
             "port_numbers": "7-4", "product": "Redmi Note", "interfaces": []},  # name
        ])
        monkeypatch.setattr(bridge, "adb_status", lambda: [])
        rows = devices.list_devices()
        assert sorted(r["key"] for r in rows) == ["usb:7-1", "usb:7-2", "usb:7-3", "usb:7-4"]

    def test_is_phone_unit(self):
        assert devices.is_phone({"vid": 0x04E8, "interfaces": []}) is True
        assert devices.is_phone({"vid": 0x1D6B, "interfaces": [{"class": 9}]}) is False
        assert devices.is_phone("not-a-dict") is False
