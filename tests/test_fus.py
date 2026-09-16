# SPDX-License-Identifier: MIT
"""
Tests for Samsung FUS downloader core module.
"""

import pytest
from python.core import fus


def test_fus_module_imports():
    assert hasattr(fus, "check_latest_version")
    assert hasattr(fus, "download_and_decrypt_firmware")
    assert hasattr(fus, "get_firmware_details")


def test_get_firmware_details_parses_pda_csc_cp(monkeypatch):
    ver = "A145MUBS6CXG2/A145MOWO6CXG2/A145MUBS6CXG2/A145MUBS6CXG2"
    monkeypatch.setattr(fus, "check_latest_version", lambda m, r: ver)
    monkeypatch.setattr(fus, "list_all_versions", lambda m, r: [
        {"version": ver, "size": 6442450944, "rcount": 1},
    ])

    class _Client:
        nonce = "n"
    monkeypatch.setattr(fus.fusclient, "FUSClient", lambda: _Client())
    monkeypatch.setattr(
        fus, "_binary_inform",
        lambda c, v, m, r: ("/p/", "AP_A145MUBS6CXG2.enc4", 6442450944),
    )
    d = fus.get_firmware_details("sm-a145m", "eux")
    assert d["model"] == "SM-A145M"
    assert d["region"] == "EUX"
    assert d["pda"] == "A145MUBS6CXG2"
    assert d["csc"] == "A145MOWO6CXG2"
    assert d["cp"] == "A145MUBS6CXG2"
    assert d["size_bytes"] == 6442450944
    assert d["filename"] == "AP_A145MUBS6CXG2.enc4"


def test_get_firmware_details_survives_binaryinfo_failure(monkeypatch):
    ver = "A145MUBS6CXG2/A145MOWO6CXG2/A145MUBS6CXG2"
    monkeypatch.setattr(fus, "check_latest_version", lambda m, r: ver)
    monkeypatch.setattr(fus, "list_all_versions", lambda m, r: [
        {"version": ver, "size": 12345, "rcount": 1},
    ])
    def _boom(*a, **k):
        raise RuntimeError("no network")
    monkeypatch.setattr(fus.fusclient, "FUSClient", _boom)
    d = fus.get_firmware_details("SM-A145M", "EUX")
    assert d["pda"] == "A145MUBS6CXG2"
    assert d["size_bytes"] == 12345
    assert d["filename"] is None
