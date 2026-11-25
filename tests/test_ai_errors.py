"""Known-cause catalogue grounded in real bridge/ADB error strings."""

from __future__ import annotations

from python.core.ai import errors


def test_matches_the_real_error_strings():
    log = "\n".join(
        [
            "[step] opening USB session",
            "USB error: LIBUSB_ERROR_ACCESS",
            "error: not authorized",
            "checksum mismatch on userdata",
        ]
    )
    hits = errors.match(log, limit=3)
    titles = [cause.title for cause, _line in hits]
    assert "ADB is not authorised on the device" in titles
    assert "Read-back verification did not match" in titles
    assert len(hits) == 3


def test_newest_line_wins():
    log = "\n".join(
        [
            "error: not authorized",
            "[retry] adb authorized",
            "USB error: LIBUSB_ERROR_NO_DEVICE",
        ]
    )
    hits = errors.match(log, limit=1)
    assert hits[0][0].title == "The device was unplugged or reset mid-operation"
    assert "LIBUSB_ERROR_NO_DEVICE" in hits[0][1]


def test_limit_is_respected_and_no_duplicates():
    log = "\n".join(["not authorized"] * 5 + ["checksum mismatch"] * 2)
    hits = errors.match(log, limit=2)
    assert len(hits) == 2
    assert len({cause.title for cause, _ in hits}) == 2


def test_render_includes_why_fix_and_the_matched_line():
    rendered = errors.render("error: checksum mismatch on boot_a")
    assert "Known failure causes" in rendered
    assert "Why:" in rendered and "Fix:" in rendered
    assert "Matched line: error: checksum mismatch on boot_a" in rendered


def test_unmatched_log_renders_nothing():
    assert errors.match("all steps completed") == []
    assert errors.render("all steps completed") == ""


def test_wrong_mode_and_handshake_are_distinct_causes():
    wrong = errors.match("Not in download mode")[0][0].title
    handshake = errors.match("Handshake failed: timeout")[0][0].title
    assert wrong != handshake
