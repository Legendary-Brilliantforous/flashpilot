import time

from . import bridge

SAMSUNG_VID = 0x04E8
MTP_PID = 0x6860
DIAG_CONFIG = 2

# Samsung vendor AT commands used by commercial FRP tools (NDXCode / riskeco /
# apeppels lineage) to flip USB debugging on from the diag port. Order matters:
#   KSTRINGB   = check mode (diagnostic)
#   DUMPCTRL   = enable debug dump
#   DEBUGLVC   = changes the USB configuration -> the phone DISCONNECTS and
#                re-enumerates (expected; see NDXCode README known-issue).
#                The second tuple element marks commands that drop USB so we
#                reconnect before continuing.
#   SWATD / ACTIVATE = toggle the USB-debugging composite / activate it.
#
# Note: entries are the text AFTER "AT" - at_send() prepends "AT" itself.
ENABLE_ADB_CMDS = [
    ("+KSTRINGB=0,3", False),
    ("+DUMPCTRL=1,0", False),
    ("+DEBUGLVC=0,5", True),
    ("+SWATD=0", False),
    ("+ACTIVATE=0,0,0", False),
    ("+SWATD=1", False),
]

# Token-free sequence for patched firmwares (A02s Android 11 etc. where
# DEBUGLVC returns PACM(PROTECTED_NO_TOK)). Commercial tools fall back to
# SWATD/ACTIVATE without DEBUGLVC on these builds.
ENABLE_ADB_CMDS_TOKEN_FREE = [
    ("+KSTRINGB=0,3", False),
    ("+DUMPCTRL=1,0", False),
    ("+SWATD=0", False),
    ("+ACTIVATE=0,0,0", False),
    ("+SWATD=1", False),
]

# Minimal sequence for SDM450 / A02s where even KSTRINGB is enough to
# expose the ADB composite without DUMPCTRL.
ENABLE_ADB_CMDS_MINIMAL = [
    ("+KSTRINGB=0,3", False),
    ("+SWATD=1", False),
]

# Alternative vendor sets observed on newer OneUI (A13+) where the
# classic commands are remapped.
ENABLE_ADB_CMDS_ALT = [
    ("+CFUN=1,1", False),
    ("+CTSA=1,1", False),
]

# SDM450 / A02s (Qualcomm-based Samsung): the modem is Qualcomm, NOT a
# Samsung Shannon — so Shannon-only commands (SHANNONVER/SVL) are a probe,
# not an enable path. The enable still goes through KSTRINGB/SWATD/ACTIVATE.
# This list is used for discovery logging only.
DIAG_PROBE_CMDS = [
    "+CGMM",
    "+CGMR",
    "+DEVCONINFO",
    "+KSTRINGB=0,3",
    "+SHANNONVER",
    "+SVL",
    "+SYSINFO",
    "+SWATD=?",
    "+ACTIVATE=?",
]

# ADB "MTP actions" (open browser / emergency / home / settings). These are the
# same generic intents commercial tools (AndroidSeviceTool "Launch Browser
# (MTP)", SamFw) fire over ADB once USB debugging is enabled - the mechanism
# works on every Android device that enumerates as MTP, it does not use a
# Samsung-proprietary MTP operation.
ACTION_INTENTS = {
    "browser": "am start -a android.intent.action.VIEW -d http://www.google.com",
    "emergency": "am start -a android.intent.action.DIAL -d tel:911",
    "home": "am start -c android.intent.category.HOME -a android.intent.action.MAIN",
    "settings": "am start -n com.android.settings/com.android.settings.Settings",
}


class MtpError(RuntimeError):
    pass


def find_samsung(key=None):
    """Return the first Samsung USB device dict, or None.

    ``key`` is a stable device key (see devices.device_key); None means
    the ambient thread-scoped key, which itself defaults to first-match
    for backward compatibility.
    """
    if key is None:
        from . import devices as _dev

        key = _dev.current_key()
    for d in bridge.detect_usb():
        if d.get("vid") != SAMSUNG_VID:
            continue
        if key is None:
            return d
        from . import devices as _dev2

        if _dev2.match_key(d, key):
            return d
    return None


def is_adb_composite(d):
    """True if the device's active config exposes the ADB interface
    signature (class 255 / subclass 66 / protocol 1)."""
    return any(
        i.get("class") == 255 and i.get("subclass") == 66 and i.get("protocol") == 1
        for i in d.get("interfaces", [])
    )


def is_diag_config(d):
    """True if the device already exposes the diag/modem AT port: a CDC ACM
    interface (class 2 / subclass 2 / protocol 1 = AT-commands) plus its
    CDC Data interface. Modern Samsungs reach this state via their own
    sys.usb.config instead of a second USB configuration, so it is present
    with num_configurations == 1 - there is nothing to switch."""
    return any(
        i.get("class") == 2 and i.get("subclass") == 2 and i.get("protocol") == 1
        for i in d.get("interfaces", [])
    )


def target(d=None, key=None):
    """Normalize a device dict (or bridge USB entry) to a bridge target
    string 'vid:pid@bus:addr'. With no dict, resolves via find_samsung(key);
    ``key`` defaults to the ambient thread-scoped device key."""
    if d is None:
        if key is None:
            from . import devices as _dev

            key = _dev.current_key()
        d = find_samsung(key=key)
        if d is None:
            raise MtpError("no Samsung device detected - plug the phone in")
    return f"{d['vid']:04x}:{d['pid']:04x}@{d['bus']}:{d['address']}"


def switch_to_diag():
    """Switch the phone to the diag/modem USB configuration (index 2) which
    exposes the CDC ACM AT port. Mirrors galaxy-at-tool: reset + retry loop.

    Returns the (possibly re-enumerated) target string.
    """
    d = find_samsung()
    if d is None:
        raise MtpError("no Samsung device detected - plug the phone in")

    # Already in the diag/modem state - nothing to switch. Modern Samsungs
    # expose the AT port via their own sys.usb.config (num_configurations
    # stays 1), so the reset/switch path below is neither needed nor safe.
    if is_diag_config(d):
        return target(d)

    # A USB config switch resets the device and REVOKES an in-progress ADB
    # authorization. Modern devices (A1x/A3x/... and anything whose firmware
    # only exposes a single USB config) have no diag config 2 - the reset
    # would do nothing but drop the user's "Allow USB debugging" approval.
    # Refuse instead of silently breaking the phone's ADB state.
    if d.get("configs", 1) < DIAG_CONFIG:
        hint = (
            "use 'Read device info / ADB' or 'FRP bypass / ADB' instead"
            if is_adb_composite(d)
            else "this device exposes no second USB config, so it cannot be "
            "switched into the diag/modem state"
        )
        raise MtpError(
            f"device exposes only {d.get('configs')} USB configuration(s) and has "
            f"no diag/modem config - {hint}. "
            f"(Refusing: a config switch would reset the phone and revoke the "
            f"USB debugging authorization.)"
        )

    t = target(d)
    try:
        result = bridge.usb_config(t, DIAG_CONFIG, timeout=30)
    except bridge.BridgeError as e:
        raise MtpError(f"config switch failed: {e}")
    time.sleep(1.5)
    d2 = find_samsung()
    if d2 is None:
        raise MtpError("device vanished during config switch")
    return target(d2)


def at(cmd, t=None, timeout_ms=4000):
    """Send one AT command (text after 'AT', or '' for a bare ping) and return
    the parsed reply. A leading 'AT' is tolerated if the caller passes one."""
    if t is None:
        t = target()
    if cmd.startswith("AT"):
        cmd = cmd[2:]
    try:
        return bridge.at_send(t, cmd, timeout_ms=timeout_ms)
    except bridge.BridgeError as e:
        raise MtpError(f"at send failed: {e}")


def ping(t=None, attempts=1):
    """Send a bare 'AT' until the phone answers OK (or attempts exhausted)."""
    for _ in range(attempts):
        r = at("", t)
        if r.get("ok"):
            return True
        time.sleep(1.5)
    return False


def _reconnect_diag(timeout=25):
    """Re-find the Samsung device after an AT command dropped USB and bring the
    diag port back up. Returns the new target string."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        d = find_samsung()
        if d is not None:
            try:
                return switch_to_diag()
            except MtpError as e:
                last = e
        time.sleep(1.5)
    raise MtpError(f"device did not come back after USB re-enumeration: {last}")


def enable_adb_via_at(t=None, slow=True):
    """Commercial AT sequence (NDXCode/riskeco order) that makes the phone pop
    the 'Allow USB debugging' dialog.

    AT+DEBUGLVC intentionally changes the phone's USB configuration, so the
    device disappears and re-enumerates mid-sequence - we reconnect after it
    instead of (incorrectly) failing the rest of the chain.

    Returns (new_target, log_lines). The commands are paced (~2.5s) because
    firing them back-to-back causes `bulk read: Input/Output Error` on this
    firmware.
    """
    lines = []
    if t is None:
        t = target()
    for cmd, drops_usb in ENABLE_ADB_CMDS:
        try:
            r = at(cmd, t)
            reply = (r.get("reply") or "").strip()
            ok = r.get("ok", False)
            lines.append(f"  > {cmd}  ->  {reply or '(no reply)'}{'  OK' if ok else ''}")
        except MtpError as e:
            lines.append(f"  > {cmd}  ->  ERROR: {e}")
        if drops_usb:
            lines.append("  DEBUGLVC: phone re-enumerates USB (expected). "
                         "reconnecting to the diag port...")
            t = _reconnect_diag()
            lines.append(f"  reconnected at {t}")
            if ping(t, attempts=6):
                lines.append("  AT alive again")
            else:
                lines.append("  AT port did not answer after reconnect")
        elif slow:
            time.sleep(2.5)
    return t, lines


def enable_adb_via_at_strong(t=None):
    """Strong multi-sequence AT engine — tries token-free + minimal sets
    when the classic DEBUGLVC is blocked (PACM PROTECTED_NO_TOK on A02s).

    Returns (target, log_lines, success). Success is True if after any
    sequence the device shows an ADB composite (checked via is_adb_composite)
    or AT still answers and SWATD got OK.
    """
    import time as _t
    lines = []
    base_t = t or target()
    # Discovery first: log which diag commands answer so SDM450/Qualcomm
    # units fail fast with the right guidance instead of burning all sequences.
    try:
        _, probe_lines = probe_diag_commands(base_t)
        lines.extend(probe_lines)
    except Exception as e:
        lines.append(f"  [diag-probe] error: {e}")
    # Try sequences in order: classic (with DEBUGLVC), token-free, minimal.
    sequences = [
        ("classic", ENABLE_ADB_CMDS),
        ("token-free", ENABLE_ADB_CMDS_TOKEN_FREE),
        ("minimal", ENABLE_ADB_CMDS_MINIMAL),
    ]
    for name, seq in sequences:
        lines.append(f"  [strong] Trying {name} sequence ({len(seq)} cmds)")
        t = base_t
        # Refresh target each sequence in case device re-enumerated.
        try:
            d = find_samsung()
            if d:
                t = target(d)
        except Exception:
            pass
        # Quick ping first — if AT not alive, skip this sequence.
        try:
            if not ping(t, attempts=2):
                lines.append(f"    AT ping failed on {t} — skip {name}")
                continue
        except Exception as e:
            lines.append(f"    ping error: {e} — try {name} anyway")
        ok_count = 0
        for cmd, drops_usb in seq:
            try:
                r = at(cmd, t)
                reply = (r.get("reply") or "").strip()
                ok = r.get("ok", False)
                lines.append(f"    > {cmd} -> {reply or '(no reply)'}{' OK' if ok else ''}")
                if ok:
                    ok_count += 1
            except MtpError as e:
                lines.append(f"    > {cmd} -> ERROR: {e}")
                # Protected token errors are expected on patched FW — continue to next seq.
                if "PROTECTED" in str(e) or "CME Error" in str(e):
                    lines.append(f"      (protected — will try next sequence)")
                    break
            if drops_usb:
                lines.append("    DEBUGLVC re-enumerate — reconnecting")
                try:
                    t = _reconnect_diag(timeout=18)
                    lines.append(f"    reconnected {t}")
                    if ping(t, attempts=4):
                        lines.append("    AT alive after reconnect")
                    else:
                        lines.append("    AT silent after reconnect")
                        break
                except MtpError as e:
                    lines.append(f"    reconnect failed: {e}")
                    break
            else:
                _t.sleep(1.2)
        # Heuristic: if at least KSTRINGB + SWATD got OK, consider sequence promising.
        if ok_count >= 2:
            # Check if ADB composite appeared (poll 5s)
            for _ in range(5):
                try:
                    d = find_samsung()
                    if d and is_adb_composite(d):
                        lines.append(f"  [strong] {name} sequence exposed ADB composite!")
                        return t, lines, True
                except Exception:
                    pass
                _t.sleep(1)
            lines.append(f"  [strong] {name} got {ok_count} OKs but no ADB composite yet — will check after replug")
            # Don't return False yet — let caller wait for ADB; consider partial success.
            # If this was token-free and got OKs, return True to trigger ADB wait.
            if name != "classic":
                return t, lines, True
        else:
            lines.append(f"  [strong] {name} only {ok_count} OKs — trying next")
    return base_t, lines, False


def probe_diag_commands(t=None, timeout_ms=3000):
    """Probe which vendor AT commands this firmware answers (discovery only).

    On SDM450/A02s the modem is Qualcomm-based, so Shannon commands
    (SHANNONVER/SVL) are expected to be silent — the log this produces tells
    the operator whether the diag port is Samsung-Shannon (enable path viable)
    or Qualcomm (use EDL/Download instead of burning time on AT). Returns
    (answered_list, log_lines).
    """
    lines = []
    answered = []
    if t is None:
        try:
            t = target()
        except MtpError as e:
            return [], [f"  [diag-probe] no target: {e}"]
    for cmd in DIAG_PROBE_CMDS:
        try:
            r = at(cmd, t, timeout_ms=timeout_ms)
            reply = (r.get("reply") or "").strip()
            ok = r.get("ok", False)
            if ok or reply:
                answered.append(cmd)
                lines.append(f"    [diag-probe] {cmd} -> {reply[:80] or '(no reply)'} OK")
            else:
                lines.append(f"    [diag-probe] {cmd} -> silent")
        except MtpError as e:
            lines.append(f"    [diag-probe] {cmd} -> {e}")
    if not answered:
        lines.append("  [diag-probe] no vendor commands answered — likely Qualcomm-based (SDM450) or patched; prefer EDL/Download.")
    else:
        lines.append(f"  [diag-probe] answered: {', '.join(answered)}")
    return answered, lines


def mtp_bypass_try_browser_via_adb(t=None):
    """MTP-side browser/Settings launch without ADB — commercial tools use
    MTP vendor extension 0x101B or file push + auto-open.

    This is a best-effort Python fallback using `gio`/`mtp-tools` if the
    bridge does not expose a native MTP SendObject. It tries to push a
    tiny HTML file that auto-redirects to Settings via intent, then relies
    on Samsung's MTP auto-index to surface it. Returns log lines.
    """
    import os as _os
    import subprocess as _sp
    import tempfile as _tf
    lines = []
    # Check for gio/mtp tools
    has_gio = _os.system("which gio >/dev/null 2>&1") == 0
    has_mtp = _os.system("which mtp-connect >/dev/null 2>&1") == 0
    lines.append(f"  [mtp-bypass] gio={has_gio} mtp-tools={has_mtp}")
    if not has_gio and not has_mtp:
        lines.append("  [mtp-bypass] no gio/mtp-tools — skip file-push vector (AT is primary)")
        return lines
    # Create a minimal HTML that tries to open Settings via intent
    html = b"""<html><head><meta http-equiv="refresh" content="0; url=intent:#Intent;action=android.settings.SETTINGS;end"></head><body>tap</body></html>"""
    try:
        with _tf.NamedTemporaryFile(suffix=".html", delete=False) as f:
            f.write(html)
            tmp = f.name
        lines.append(f"  [mtp-bypass] created {tmp} ({len(html)} bytes)")
        # Try gio copy to mtp://
        if has_gio:
            try:
                out = _sp.run(["gio", "mount", "-l"], capture_output=True, text=True, timeout=8).stdout
                lines.append(f"  gio mounts: {out[:200].replace(chr(10), ' ')}")
                # Find mtp mount
                for line in out.splitlines():
                    if "mtp://" in line.lower():
                        lines.append(f"    mtp mount: {line.strip()}")
                        # Try copy
                        try:
                            _sp.run(["gio", "copy", tmp, line.strip().split()[-1] + "/bypass.html"], timeout=10, capture_output=True)
                            lines.append("    gio copy attempted")
                        except Exception as e:
                            lines.append(f"    gio copy failed: {e}")
                        break
            except Exception as e:
                lines.append(f"  gio error: {e}")
        try:
            _os.unlink(tmp)
        except Exception:
            pass
    except Exception as e:
        lines.append(f"  [mtp-bypass] error: {e}")
    lines.append("  [mtp-bypass] done — check phone for browser/Settings popup")
    return lines


def adb_action(name, timeout=20):
    """Fire an 'MTP action' over ADB once USB debugging is enabled. Returns the
    raw adb shell output (may be empty on success)."""
    if name not in ACTION_INTENTS:
        raise ValueError(f"unknown action: {name!r} (have {sorted(ACTION_INTENTS)})")
    return bridge.adb_shell(ACTION_INTENTS[name], timeout=timeout)


def reboot_to_download(t=None):
    """Best-effort: query the download-mode AT function (galaxy-at-tool
    exposes this via AT+FUN). Experimental - the risky path."""
    return at("+FUN?", t)


def read_device_info(t=None):
    """Vendor command AT+DEVCONINFO -> model/IMEI/SN/software versions."""
    return at("+DEVCONINFO", t, timeout_ms=8000)


def read_serial(t=None):
    """Read the IMEI via AT+CIMI? (subscriber id) if the SIM is readable."""
    return at("+CIMI?", t)


def read_mtp_info(t=None, timeout_ms=8000):
    """Probe the MTP session: which operations (incl. vendor ops) the phone's
    MTP stack supports, and whether an MTP session can even be opened. On FRP /
    setup screens Samsung refuses OpenSession (0x2002) - returns None then.

    Returns the parsed dict or None if the session is refused / not in MTP mode.
    """
    if t is None:
        t = target()
    try:
        return bridge.mtp_info(t, timeout_ms=timeout_ms)
    except bridge.BridgeError:
        return None


def _extract_model(reply):
    """Pull a Samsung model token out of an AT reply. Handles the
    'MODEL:SM-A065F' / 'MODEL=SM-A065F' key:value form and a bare SM- token."""
    import re

    m = re.search(r"[Mm][Oo][Dd][Ee][Ll][:=]\s*([A-Za-z0-9-]+)", reply)
    if m:
        return m.group(1)
    m = re.search(r"\bSM-[A-Z0-9]+/DS\b|\bSM-[A-Z0-9]+\b", reply)
    if m:
        return m.group(0)
    return ""


def read_model_via_at(t=None, timeout_ms=6000):
    """Best-effort model read over the AT channel.

    Samsung's AT+DEVCONINFO only returns data inside test mode (*#0*# from the
    Emergency-call dialer); standard AT+CGMM/AT+GMM work on some firmwares.
    Returns the model string, or '' when the channel is silent/not in the
    diag state.
    """
    import re  # noqa: F401 (kept for parity with _extract_model)

    if t is None:
        try:
            t = target()
        except MtpError:
            return ""
    d = find_samsung()
    if d is None or not is_diag_config(d):
        return ""
    for cmd in ("+DEVCONINFO", "+CGMM", "+GMM"):
        try:
            r = at(cmd, t, timeout_ms=timeout_ms)
        except MtpError:
            continue
        model = _extract_model(r.get("reply") or "")
        if model:
            return model
    return ""
