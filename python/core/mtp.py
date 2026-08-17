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


def find_samsung():
    """Return the first Samsung USB device dict, or None."""
    for d in bridge.detect_usb():
        if d.get("vid") == SAMSUNG_VID:
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


def target(d=None):
    """Normalize a device dict (or bridge USB entry) to a bridge target
    string 'vid:pid@bus:addr'."""
    if d is None:
        d = find_samsung()
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
