# SPDX-License-Identifier: MIT
"""
Tests for Samsung FUS downloader core module.
"""

import pytest
from python.core import fus


def test_fus_module_imports():
    assert hasattr(fus, "check_latest_version")
    assert hasattr(fus, "download_and_decrypt_firmware")
