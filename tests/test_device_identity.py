"""Device identity: chip + brand + model + form factor.

Regression guards for the "detection only knows the chip" gap:

* the Rust merged row carries the real ADB model (`model:` extra) and the
  brand family (USB/ADB strings) — the Python adapter must not drop them;
* the live identity probe reads `ro.build.characteristics` and reports a
  canonical form factor (phone/tablet/tv/watch/automotive);
* an unknown/absent characteristic stays unknown — the UI must never guess;
* the device strip and the model tile show "BRAND · MODEL" plus the type.

The Rust-side parsing (`adb_extra_field`, `brand_hint`) is covered by the
crate's own unit tests in `src/usb/filtering.rs` / `src/devices.rs`.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


class TestMergedRowIdentity:
    """The Rust `detect-merged` row → legacy shape adapter."""

    def test_model_brand_and_type_survive_the_adapter(self):
        from python.core import devices

        row = {
            "key": "adb:R9X", "label": "TECNO Mobile · R9X",
            "transports": ["ADB"], "vid": 0x0E8D, "pid": 0x201C,
            "bus": 1, "address": 2, "serial": "R9X",
            "is_adb": False, "adb_state": "device",
            "usb_product": "TECNO Mobile",
            "usb_manufacturer": "TECNO",
            "model": "KG6-GL",
            "brand": "TECNO",
            "device_type": None,
        }
        out = devices._merged_row_to_legacy(row)
        assert out["model"] == "KG6-GL"
        assert out["brand"] == "TECNO"
        assert out["device_type"] is None
        # The USB payload keeps them too (GUI reads row["usb"]).
        assert out["usb"]["model"] == "KG6-GL"
        assert out["usb"]["brand"] == "TECNO"

    def test_missing_identity_fields_are_none_not_guessed(self):
        from python.core import devices

        out = devices._merged_row_to_legacy({
            "key": "usb:04e8:685d@1:3", "label": "SAMSUNG Mobile USB",
            "transports": ["Download mode"], "is_adb": False,
        })
        assert out["model"] is None
        assert out["brand"] is None
        assert out["device_type"] is None


class TestDeviceType:
    """`ro.build.characteristics` → canonical form factor."""

    @pytest.mark.parametrize("raw,expected", [
        ("phone", "phone"),
        ("tablet", "tablet"),
        ("tv", "tv"),
        ("watch", "watch"),
        ("automotive", "automotive"),
        ("phone,nosdcard", "phone"),
        ("tablet nosdcard", "tablet"),
        # A device that says both: the specific form wins over "phone".
        ("phone tablet", "tablet"),
        # Unknown / missing → unknown, never a guess.
        ("", ""),
        ("somethingelse", ""),
        ("nosdcard,noat", ""),
    ])
    def test_characteristics_mapping(self, raw, expected):
        from python.core import device_info

        assert device_info.device_type_from_characteristics(raw) == expected

    def test_apple_product_type_mapping(self):
        from python.core import device_info

        assert device_info._device_type_from_product_type("iPhone14,2") == "phone"
        assert device_info._device_type_from_product_type("iPad13,1") == "tablet"
        assert device_info._device_type_from_product_type("") == ""

    def test_probe_reports_the_device_type(self, monkeypatch):
        from python.core import bridge as _bridge
        from python.core import device_info as _di

        _di._LIVE_CACHE.update({"probed": None, "at": 0.0, "result": None})
        monkeypatch.setattr(_bridge, "adb_presence_status", lambda: [
            {"serial": "R9XTEST1", "state": "device", "extra": ""},
        ])
        monkeypatch.setattr(_bridge, "adb_status", lambda: [
            {"serial": "R9XTEST1", "state": "device", "extra": ""},
        ])
        props = {
            "getprop ro.serialno": "R9XTEST1",
            "getprop ro.product.model": "SM-T870",
            "getprop ro.build.characteristics": "tablet",
        }

        def fake_shell(cmd, timeout=6, serial=None, rescue=True):
            return props.get(cmd, "")

        monkeypatch.setattr(_bridge, "adb_shell", fake_shell)
        monkeypatch.setattr(_di, "_mtp_serial_and_build", lambda: ("", ""))
        monkeypatch.setattr(_di, "_usb_target_serial", lambda: "")

        out = _di.get_live_identity()
        assert out["model"] == "SM-T870"
        assert out["device_type"] == "tablet"

    def test_probe_without_characteristics_leaves_the_type_unknown(self, monkeypatch):
        from python.core import bridge as _bridge
        from python.core import device_info as _di

        _di._LIVE_CACHE.update({"probed": None, "at": 0.0, "result": None})
        monkeypatch.setattr(_bridge, "adb_presence_status", lambda: [
            {"serial": "R9XTEST2", "state": "device", "extra": ""},
        ])
        monkeypatch.setattr(_bridge, "adb_status", lambda: [
            {"serial": "R9XTEST2", "state": "device", "extra": ""},
        ])
        props = {
            "getprop ro.serialno": "R9XTEST2",
            "getprop ro.product.model": "KG6-GL",
        }

        def fake_shell(cmd, timeout=6, serial=None, rescue=True):
            return props.get(cmd, "")

        monkeypatch.setattr(_bridge, "adb_shell", fake_shell)
        monkeypatch.setattr(_di, "_mtp_serial_and_build", lambda: ("", ""))
        monkeypatch.setattr(_di, "_usb_target_serial", lambda: "")

        out = _di.get_live_identity()
        assert out["model"] == "KG6-GL"
        assert out["device_type"] == ""


@pytest.fixture(scope="module")
def win(test_window):
    return test_window()


class TestBrandTokens:
    """The brand families are a Rust/Python contract — they must not drift."""

    def test_python_tokens_match_the_rust_table(self):
        import pathlib
        import re

        from python.gui.qt_app import _USB_BRAND_TOKENS, _USB_VID_BRANDS

        src = (pathlib.Path(__file__).resolve().parents[1]
               / "src" / "usb" / "filtering.rs")
        text = src.read_text(encoding="utf-8")
        block = re.search(r"pub const BRAND_TOKENS[^=]*=\s*&\[(.*?)\];",
                          text, re.S)
        assert block, "BRAND_TOKENS table not found in src/usb/filtering.rs"
        rust = dict(re.findall(r'\("([^"]+)",\s*"([^"]+)"\)', block.group(1)))
        assert dict(_USB_BRAND_TOKENS) == rust, (
            "the GUI brand tokens drifted from the Rust BRAND_TOKENS table"
        )

        vids = re.search(r"pub const VID_BRANDS[^=]*=\s*&\[(.*?)\];", text, re.S)
        assert vids, "VID_BRANDS table not found in src/usb/filtering.rs"
        rust_vids = {
            int(vid, 16): brand
            for vid, brand in re.findall(r"\((0x[0-9A-Fa-f]+),\s*\"([^\"]+)\"\)",
                                         vids.group(1))
        }
        assert _USB_VID_BRANDS == rust_vids, (
            "the GUI VID brands drifted from the Rust VID_BRANDS table"
        )

    def test_usb_brand_reads_the_descriptor_strings(self):
        from python.gui.qt_app import _usb_brand

        assert _usb_brand({"manufacturer": "TECNO", "product": "MT65xx"}) == "TECNO"
        assert _usb_brand({"manufacturer": "Infinix", "product": "Hot 20"}) == "INFINIX"
        assert _usb_brand({"manufacturer": "SAMSUNG", "product": "Mobile USB"}) == "SAMSUNG"
        # A Pixel is a Google phone.
        assert _usb_brand({"manufacturer": "Google", "product": "Pixel 7"}) == "GOOGLE"
        # A stringless OEM stage still names its brand through the VID.
        assert _usb_brand({"vid": 0x04E8}) == "SAMSUNG"
        assert _usb_brand({"vid": 0x05AC}) == "APPLE"
        # Unknown hardware gets no brand guess.
        assert _usb_brand({"manufacturer": "Acme", "product": "Widget"}) is None
        assert _usb_brand({"vid": 0x1234}) is None
        assert _usb_brand(None) is None


class TestGuiIdentity:
    """The strip + the model tile show brand · model · type."""

    def test_strip_title_shows_brand_and_model(self, win):
        rows = [{
            "key": "adb:R9X", "label": "TECNO Mobile · R9X",
            "transports": ["ADB"], "mode": "mediatek",
            "model": "KG6-GL", "brand": "TECNO",
        }]
        win._apply_device_strip(rows)
        assert win._dev_title.text() == "TECNO · KG6-GL"

    def test_strip_falls_back_to_the_label_without_a_model(self, win):
        rows = [{
            "key": "usb:04e8:685d@1:3", "label": "SAMSUNG Mobile USB",
            "transports": ["Download mode"], "mode": "samsung-odin",
        }]
        win._apply_device_strip(rows)
        assert win._dev_title.text() == "SAMSUNG Mobile USB"

    def test_strip_shows_the_form_factor_when_known(self, win):
        rows = [{
            "key": "adb:R9X", "label": "TECNO Mobile · R9X",
            "transports": ["ADB"], "mode": "mediatek",
            "model": "KG6-GL", "brand": "TECNO",
        }]
        try:
            win._cached_device_type = "tablet"
            win._apply_device_strip(rows)
            assert win._dev_text.text().startswith("TABLET · ")
        finally:
            win._cached_device_type = ""

    def test_strip_has_no_type_prefix_when_unknown(self, win):
        rows = [{
            "key": "adb:R9X", "label": "TECNO Mobile · R9X",
            "transports": ["ADB"], "mode": "mediatek",
        }]
        win._cached_device_type = ""
        win._apply_device_strip(rows)
        assert not win._dev_text.text().startswith("PHONE · ")

    def test_model_tile_shows_brand_and_model(self, win, monkeypatch):
        from python.core import devices as _devices

        row = {
            "key": "adb:R9X", "label": "TECNO Mobile · R9X",
            "transports": ["ADB"],
            "usb": {"vid": 0x0E8D, "pid": 0x201C, "serial": "R9X",
                    "product": "TECNO Mobile", "manufacturer": "TECNO",
                    "model": "KG6-GL", "brand": "TECNO"},
            "adb": {"serial": "R9X", "state": "device", "extra": ""},
            "model": "KG6-GL", "brand": "TECNO", "device_type": None,
        }
        monkeypatch.setattr(_devices, "list_devices", lambda: [row])
        win._show_device_row("adb:R9X")
        assert win.info["Device Model"].value.text() == "TECNO · KG6-GL"

    def test_device_type_does_not_leak_to_another_device(self, win, monkeypatch):
        """A tablet's form factor must never be shown for the next phone."""
        from python.core import devices as _devices

        def _row(key, serial, model):
            return {
                "key": key, "label": f"{serial} [{model}]",
                "transports": ["ADB"],
                "usb": {"vid": 0x0E8D, "pid": 0x201C, "serial": serial,
                        "product": "TECNO Mobile", "manufacturer": "TECNO",
                        "model": model, "brand": "TECNO"},
                "adb": {"serial": serial, "state": "device", "extra": ""},
                "model": model, "brand": "TECNO", "device_type": None,
            }

        rows = [_row("adb:R9X", "R9X", "KG6-GL"),
                _row("adb:R9Y", "R9Y", "CAMEL-1")]
        monkeypatch.setattr(_devices, "list_devices", lambda: rows)

        win._cached_device_type = "tablet"
        win._cached_type_serial = "adb:R9X"
        win._show_device_row("adb:R9Y")
        assert win._cached_device_type == "", \
            "the previous device's form factor leaked into the new one"

    def test_device_type_survives_a_reselect_of_the_same_device(self, win, monkeypatch):
        from python.core import devices as _devices

        row = {
            "key": "adb:R9X", "label": "TECNO Mobile · R9X",
            "transports": ["ADB"],
            "usb": {"vid": 0x0E8D, "pid": 0x201C, "serial": "R9X",
                    "product": "TECNO Mobile", "manufacturer": "TECNO",
                    "model": "KG6-GL", "brand": "TECNO"},
            "adb": {"serial": "R9X", "state": "device", "extra": ""},
            "model": "KG6-GL", "brand": "TECNO", "device_type": None,
        }
        monkeypatch.setattr(_devices, "list_devices", lambda: [row])
        win._cached_device_type = "tablet"
        win._cached_type_serial = "adb:R9X"
        win._show_device_row("adb:R9X")
        assert win._cached_device_type == "tablet"
