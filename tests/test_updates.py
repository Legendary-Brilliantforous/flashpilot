"""Post-install "what was added or changed" and auto-install update tests.

Covers the behavior added on top of the manual "Update Downloaded / Install
Now" prompt:

* a new Settings switch, ``auto_install_update`` (default True);
* after a sudo ``dpkg -i`` succeeds, the updater stamps ``pending_new_version``
  in QSettings and restarts;
* on the first window after the restart, ``_maybe_show_new_version_window``
  clears that flag and calls ``_show_new_version_window``;
* ``_changelog_section_for`` parses the bullets of the newest CHANGELOG
  section for a version;
* ``_download_and_prompt_install`` routes to the auto-install path when the
  switch is on and keeps the old prompt when it is off.
"""
import os
import time

import pytest
from PyQt6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def win():
    from tests.conftest import build_test_window

    w = build_test_window(())
    w.show()
    for _ in range(20):
        QApplication.processEvents()
    yield w


def _settle(rounds=30):
    for _ in range(rounds):
        QApplication.processEvents()
        time.sleep(0.02)


CHANGELOG = """# Changelog

## 9.9.9 (future release)

- Something brand new
- A fix

## 9.9.8 (earlier)

- Something else
"""


def test_changelog_section_for_parses_newest_match(win, tmp_path):
    p = tmp_path / "CHANGELOG.md"
    p.write_text(CHANGELOG, encoding="utf-8")
    title, bullets = win._changelog_section_for("9.9.9", path=p)
    assert title == "9.9.9 (future release)"
    assert bullets[:2] == ["Something brand new", "A fix"]
    # Falls back to the newest section when the requested version is unknown.
    assert win._changelog_section_for("8.8.8", path=p)[0] == "9.9.9 (future release)"


def test_changelog_section_for_missing_file(win):
    assert win._changelog_section_for("9.9.9", path="/nonexistent/CHANGELOG.md") is None


def test_changelog_section_for_finds_real_changelog(win):
    from python.core import APP_VERSION

    parsed = win._changelog_section_for(APP_VERSION)
    if parsed is not None:
        title, bullets = parsed
        assert title.strip()
        assert all(isinstance(b, str) and b for b in bullets)


def test_pending_new_version_is_consumed_by_the_startup_window(win):
    win.settings.setValue("pending_new_version", "9.9.9")
    shown = []
    original = win._show_new_version_window
    try:
        win._show_new_version_window = lambda version: shown.append(version)
        win._maybe_show_new_version_window()
        # The flag is consumed synchronously.
        assert win.settings.value("pending_new_version", "", type=str) == ""
        _settle()
        assert shown == ["9.9.9"]
    finally:
        win._show_new_version_window = original


def test_pending_flag_ignored_when_already_shown(win):
    win._new_version_window_open = True
    win.settings.setValue("pending_new_version", "9.9.9")
    win._maybe_show_new_version_window()
    assert win.settings.value("pending_new_version", "", type=str) == ""
    win._new_version_window_open = False


def test_show_new_version_window_opens(win):
    from python.core import APP_VERSION

    before = getattr(win, "_centered_open", False)
    try:
        win._show_new_version_window(APP_VERSION)
        _settle()
        assert getattr(win, "_centered_open", False)
    finally:
        from PyQt6.QtWidgets import QFrame

        for ov in win.findChildren(QFrame):
            if ov.objectName() == "centeredOverlay":
                ov.hide()


def test_auto_install_switch_default_is_on(win):
    assert win.settings.value("auto_install_update", True, type=bool) is True


def test_download_routes_to_auto_install_when_enabled(win, monkeypatch, tmp_path):
    calls = []

    def fake_sudo(fpath, tag=""):
        calls.append(("sudo", tag))

    monkeypatch.setattr(win, "_execute_sudo_install", fake_sudo)
    monkeypatch.setattr(win, "_prompt_install_update",
                        lambda tag, fpath: calls.append(("prompt", tag)))
    monkeypatch.setattr("urllib.request.urlretrieve",
                        lambda url, dest: tmp_path / "update.deb")
    monkeypatch.setattr("os.path.exists", lambda p: True)
    win._download_and_prompt_install("https://example/update.deb", "9.9.9")
    _settle()

    sudo_calls = [c for c in calls if c[0] == "sudo"]
    assert len(sudo_calls) == 1 and sudo_calls[0][1] == "9.9.9"
    assert not any(c[0] == "prompt" for c in calls)


def test_download_routes_to_prompt_when_auto_install_disabled(win, monkeypatch, tmp_path):
    calls = []

    def fake_sudo(fpath, tag=""):
        calls.append(("sudo", tag))

    def fake_prompt(tag, fpath):
        calls.append(("prompt", tag))

    monkeypatch.setattr(win, "_execute_sudo_install", fake_sudo)
    monkeypatch.setattr(win, "_prompt_install_update", fake_prompt)
    monkeypatch.setattr("urllib.request.urlretrieve",
                        lambda url, dest: tmp_path / "update.deb")
    monkeypatch.setattr("os.path.exists", lambda p: True)
    win.settings.setValue("auto_install_update", False)
    win._download_and_prompt_install("https://example/update.deb", "9.9.9")
    _settle()
    win.settings.remove("auto_install_update")

    assert calls == [("prompt", "9.9.9")]


def test_manual_install_prompt_passes_the_tag(win, monkeypatch, tmp_path):
    """Clicking 'Install Now' stamps the tag so What's New also shows on manual installs."""
    from PyQt6.QtWidgets import QPushButton

    calls = []
    dest = tmp_path / "update.deb"
    dest.write_bytes(b"")
    monkeypatch.setattr(win, "_execute_sudo_install",
                        lambda fpath, tag="": calls.append((fpath, tag)))
    win._prompt_install_update("9.9.9", str(dest))
    _settle()

    buttons = [b for b in win.findChildren(QPushButton)
               if b.text() == "Install Now" and b.isVisible()]
    assert buttons, "the Update Downloaded notice has an 'Install Now' button"
    buttons[0].click()
    _settle()
    assert calls == [(str(dest), "9.9.9")]
