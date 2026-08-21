import glob
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import tarfile
import tempfile
import threading
import time

from . import bridge, mtk, mtp, pit


class FlowCancelled(RuntimeError):
    """Raised when the user hits Stop while a flow is running."""


_cancel = threading.Event()


def request_cancel():
    _cancel.set()


def clear_cancel():
    _cancel.clear()


def cancel_requested():
    return _cancel.is_set()


class Step:
    def __init__(self, name, func):
        self.name = name
        self.func = func

    def run(self, ctx, log):
        if cancel_requested():
            raise FlowCancelled(f"cancelled before step {self.name}")
        log(f"[step] {self.name}")
        result = self.func(ctx, log)
        log(f"[done] {self.name}")
        return result


class Flow:
    def __init__(self, name, steps):
        self.name = name
        self.steps = steps

    def run(self, ctx, log):
        log(f"== running flow: {self.name} ==")
        # Forward Rust bridge stderr (flash progress, retries, errors) into the
        # caller's log sink so long operations show live progress on screen.
        bridge.set_log_hook(log)
        try:
            results = []
            for step in self.steps:
                results.append(step.run(ctx, log))
                if cancel_requested():
                    raise FlowCancelled("cancelled by user")
            log(f"== flow finished: {self.name} ==")
            return results
        finally:
            bridge.set_log_hook(None)


# Commands that actually clear FRP once a device has adb: mark setup complete
# and disable both setup wizards so the phone boots straight to the launcher.
# Shared by the plain ADB flow and the download-mode/combination flow.
_ADB_FRP_STEPS = [
    ("mark setup wizard run", "settings put global setup_wizard_has_run 1"),
    ("mark user setup complete", "settings put secure user_setup_complete 1"),
    ("mark device provisioned", "settings put global device_provisioned 1"),
    ("allow non-market apps", "settings put secure install_non_market_apps 1"),
    ("disable Google setup wizard",
     "pm disable-user --user 0 com.google.android.setupwizard"),
    ("disable Samsung setup wizard",
     "pm disable-user --user 0 com.sec.android.app.SecSetupWizard"),
    ("back to home", "am start -c android.intent.category.HOME -a android.intent.action.MAIN"),
]


def _wait_for_adb(ctx, log, timeout=60):
    deadline = time.time() + timeout
    last_hint = 0.0
    while time.time() < deadline:
        if cancel_requested():
            raise FlowCancelled("cancelled while waiting for adb device")
        devs = bridge.adb_status()
        good = [d for d in devs if d["state"] == "device"]
        if good:
            ctx["serial"] = good[0]["serial"]
            log(f"adb device online: {good[0]['serial']} ({good[0]['state']})")
            return True
        unauth = [d for d in devs if d["state"] == "unauthorized"]
        if unauth and time.time() - last_hint > 10:
            last_hint = time.time()
            log(
                f"device {unauth[0]['serial']} connected but NOT authorized - "
                f"the 'Allow USB debugging' dialog has not been accepted yet."
            )
            log(
                "  On the phone: the dialog only pops when the SCREEN IS ON AND"
            )
            log("  UNLOCKED. Unlock it if needed, then tap 'Always allow from")
            log("  this computer' + 'Allow'.")
            log(
                "  No dialog at all? Pull down the notification shade -> tap "
            )
            log("  'Charging this device via USB' -> select 'File transfer'")
            log("  (MTP), then unplug + re-plug the cable. A data cable is")
            log("  required (not a charge-only one). (waiting...)" )
        time.sleep(2)
    log("timeout waiting for an AUTHORIZED adb device")
    log("")
    log("Fix steps (Samsung / One UI), in order:")
    log("  1. Unlock the phone and keep the screen ON while plugging in.")
    log("  2. Notification shade -> tap 'Charging this device via USB' ->")
    log("     select 'File transfer' (MTP). Then unplug + re-plug the cable.")
    log("  3. Use a DATA cable (charge-only cables show 'unauthorized' forever).")
    log("  4. Dialog still missing? Settings -> Developer options ->")
    log("     'Revoke USB debugging authorizations', turn USB debugging OFF and")
    log("     back ON, re-plug, and tap 'Always allow'.")
    log("  5. Last resort: `adb kill-server` on the PC, then re-plug.")
    log("")
    log("The dialog is suppressed while the screen is locked - if the phone is")
    log("stuck at a lock screen, remove the lock first (Screen lock remove ->")
    log("recovery factory reset), then ADB will authorize.")
    return False


def _adb_getprop(key, timeout=8):
    """Read one Android property via adb shell getprop ('' if unset/fails)."""
    try:
        return bridge.adb_shell(f"getprop {key}", timeout=timeout).strip()
    except bridge.BridgeError:
        return ""


# Android lockscreen password_type -> human label (DevicePolicyManager quality).
_LOCK_TYPE = {
    "0": "none",
    "65536": "PIN (numeric)",
    "131072": "PIN (complex)",
    "262144": "password (alphabetic)",
    "327680": "password (alphanumeric)",
    "524288": "password (complex)",
}
# locksettings get-lock-mode values (API 28+): none/pin/password/pattern.
_LOCK_MODE = {"0": "none", "1": "PIN", "2": "password", "3": "pattern"}

# USB interface class -> short name (for the detect flow).
_IFACE_CLASS = {
    0: "per-iface", 1: "audio", 2: "cdc", 3: "hid", 5: "physical",
    6: "image/ptp", 7: "printer", 8: "mass-storage", 9: "hub",
    10: "cdc-data", 11: "smart-card", 14: "video", 0xDC: "diagnostic",
    0xE0: "wireless", 0xFE: "app-specific", 0xFF: "vendor",
}
# Samsung download-mode / Odin PIDs (from odin4 udev rules) and MTP PID.
_ODIN_PIDS = {0x6601, 0x685d, 0x68c3, 0x68ef, 0x4eee, 0x4eef}


def _download_mode_device():
    """Return the Samsung USB device dict only if it is genuinely in download
    mode. 04e8:685d is ALSO the normal-boot ADB composite on A14/A06-class
    phones (USB debugging on), so a pid match alone is NOT enough - the ADB
    interface must be absent."""
    d = mtp.find_samsung()
    if not d or d.get("pid") != 0x685d:
        return None
    if mtp.is_adb_composite(d):
        return None
    return d


def _wait_download_mode(log, timeout=30):
    """Wait up to `timeout` seconds for a genuine download-mode device. Logs a
    clear warning when the phone is booted normally (the 0x685d ADB composite)
    instead of being in download mode."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cancel_requested():
            raise FlowCancelled("cancelled while waiting for download mode")
        d = _download_mode_device()
        if d:
            return d
        cur = mtp.find_samsung()
        if cur and cur.get("pid") == 0x685d and mtp.is_adb_composite(cur):
            log("  NOTE: the phone is booted NORMALLY (0x685d ADB composite) -")
            log("  that is NOT download mode. Power it OFF, then enter download")
            log("  mode: hold Volume Down + Power, release both when prompted,")
            log("  press Volume Up to confirm the 'Downloading...' screen.")
        time.sleep(1.5)
    return None


def _odin_model(log):
    """Read the real model string over Odin (session probe, then PIT header).

    Requires the phone in download mode (04e8:685d). Returns '' if not.
    """
    d = mtp.find_samsung()
    if not (d and d.get("pid") == 0x685d):
        return ""
    if mtp.is_adb_composite(d):
        # 0x685d here is the normal-boot ADB composite, not download mode.
        return ""
    t = mtp.target(d)
    model = ""
    try:
        info = bridge.odin_model(t)
        model = (info or {}).get("model") or ""
    except bridge.BridgeError as e:
        log(f"  odin model probe: {e}")
        _odin_diag(log)
        return ""
    if model and not model.startswith("("):
        return model
    try:
        resp = __import__("json").loads(bridge.odin_pit(t))
        raw = bytes.fromhex(resp.get("hex", ""))
        pit_model = pit.parse_model(raw)
        if pit_model:
            return pit_model
    except (bridge.BridgeError, ValueError, KeyError) as e:
        log(f"  PIT model fallback: {e}")
        _odin_diag(log)
        return ""
    return model


def _odin_diag(log):
    """Diagnose a download-mode phone that is present but does not answer the
    Odin/LOKE handshake.

    Samsung MediaTek phones (Galaxy A05/A06, Helio G85) boot a PROPRIETARY
    MediaTek download-agent in download mode. They enumerate as 04e8:685d with
    the usual CDC-data interface, but never answer "ODIN" -> "LOKE". Only the
    desktop Odin (Windows, or the leaked Odin v4 for Linux) implements their protocol; no open-source tool
    (Heimdall, samloader-rs, this one) can read or flash them. This is verified
    empirically - not an error in the tool. Exynos/older models (e.g. the J3)
    still speak LOKE and work fine.
    """
    log("")
    log("  The phone IS present in download mode (04e8:685d) but does not answer")
    log("  the open-source Odin/LOKE handshake. That is expected for MediaTek-")
    log("  based Galaxy models (A05/A06 - Helio G85): their download mode runs")
    log("  Samsung's PROPRIETARY MediaTek download-agent protocol, which only the")
    log("  desktop Odin (Windows, or the leaked Odin v4 for Linux) implements.")
    log("")
    log("  Consequence: on this phone the model read, PIT dump and flashing are")
    log("  NOT possible over open-source Odin. The A05/A06 model is already known")
    log("  from the specs (SM-A055F / SM-A065F) - no Odin read is needed.")
    log("")
    log("  For FRP on a permanently locked A05/A06 the working route is:")
    log("     1. Recovery factory reset  (clears the lock; leaves Google FRP),")
    log("     2. this tool's MTK mode -> 'flash combination firmware (odin4)'")
    log("        (COMBINATION_A065F...) -> boots a test build with full adb ->")
    log("        then 'FRP bypass' -> ADB -> 'clear'.")
    log("  Older Exynos phones (J3) keep working with the ODIN methods in this")
    log("  tool; the MediaTek A05/A06 use the new MTK mode (needs the leaked")
    log("  odin4 binary + a combination firmware).")
    log("")
    log("  Before trusting this result on Linux: the cdc_acm kernel module is")
    log("  known to cause the same 'bulk read timed out' on Samsung download")
    log("  mode. Cheap test: `sudo rmmod cdc_acm`, then rerun this flow. If the")
    log("  handshake then answers, it was the module - not a MediaTek phone.")
    log("")


def _adb_setting(scope, name, timeout=8):
    """Read a settings value ('global'/'secure'/'system') over adb ('' if none)."""
    try:
        return bridge.adb_shell(
            f"settings get {scope} {name}", timeout=timeout
        ).strip()
    except bridge.BridgeError:
        return ""


def _log_lock_state(log):
    """Report the current lock state over ADB before/after a removal attempt.

    Handles the Samsung quirk where an unset setting reads back as "null".
    Cross-checks against `dumpsys lock_settings` (authoritative), so a device
    that IS locked but reports an empty password_type is not misread as
    unlocked.

    Returns a dict:
      password_type: decoded lock type ('' when none/unknown),
      mode: raw `locksettings get-lock-mode` value,
      disabled: bool|None from `locksettings get-disabled`,
      dumpsys_stored: bool|None from `dumpsys lock_settings` 'stored = ...',
      lockscreen_disabled: raw `settings get secure lockscreen.disabled`.
    """
    info = {
        "password_type": "",
        "mode": "",
        "disabled": None,
        "dumpsys_stored": None,
        "lockscreen_disabled": "",
    }

    raw = _adb_setting("secure", "lockscreen.password_type")
    if raw in ("null", "", "0"):
        info["password_type"] = ""
        log("  Lock type: none (settings secure lockscreen.password_type)")
    elif raw in _LOCK_TYPE:
        info["password_type"] = raw
        log(f"  Lock type: {_LOCK_TYPE[raw]} (password_type={raw})")
    else:
        info["password_type"] = raw
        log(f"  Lock type: unknown code {raw}")

    lsd = _adb_setting("secure", "lockscreen.disabled")
    if lsd not in ("", "null"):
        info["lockscreen_disabled"] = lsd
        log(f"  secure lockscreen.disabled = {lsd}")

    # Authoritative cross-check: dumpsys lock_settings.
    try:
        dump = bridge.adb_shell("dumpsys lock_settings", timeout=15)
        for line in dump.splitlines():
            s = line.strip()
            if re.search(r"stored\s*=\s*true", s):
                info["dumpsys_stored"] = True
            elif re.search(r"stored\s*=\s*false", s):
                info["dumpsys_stored"] = False
        for line in dump.splitlines():
            m = re.match(
                r"(?:locks\.)?(?:password\s*type|mPasswordType)\s*=\s*(\d+)",
                line.strip(),
                re.I,
            )
            if m:
                code = m.group(1)
                label = _LOCK_TYPE.get(code, f"code {code}")
                log(f"  dumpsys lock_settings: passwordType={code} ({label})")
                if code == "0" and info["password_type"] == "":
                    info["password_type"] = ""
        if info["dumpsys_stored"] is True:
            log("  dumpsys lock_settings: stored = true  -> a credential IS set")
        elif info["dumpsys_stored"] is False:
            log("  dumpsys lock_settings: stored = false -> no credential stored")
    except bridge.BridgeError:
        log("  dumpsys lock_settings: unavailable")

    try:
        info["mode"] = bridge.adb_shell(
            "locksettings get-lock-mode", timeout=8
        ).strip()
    except bridge.BridgeError:
        info["mode"] = ""
    if info["mode"] and info["mode"] in _LOCK_MODE:
        log(f"  locksettings lock mode: {_LOCK_MODE[info['mode']]} (raw {info['mode']})")
    elif info["mode"]:
        log(f"  locksettings get-lock-mode: {info['mode']!r}")

    try:
        disabled = bridge.adb_shell(
            "locksettings get-disabled", timeout=8
        ).strip().lower()
        if disabled in ("true", "false"):
            info["disabled"] = disabled == "true"
            log(f"  locksettings disabled flag: {info['disabled']}")
        elif disabled:
            log(f"  locksettings get-disabled: {disabled!r}")
    except bridge.BridgeError:
        pass

    pattern = _adb_setting("secure", "lockscreen.pattern_enabled")
    if pattern in ("1", "true"):
        log("  pattern lock file active (lockscreen.pattern_enabled=1)")
    return info


def _try_enable_adb(ctx, log):
    """Best-effort: get an authorized ADB connection when none exists yet.

    Order of attack:
      1. Already authorized -> done.
      2. ADB present but unauthorized -> tell the user to tap 'Always allow'.
      3. Device exposes a diag/modem USB config -> MTP/AT method (switch config,
         vendor AT commands pop the 'Allow USB debugging' dialog).
      4. Otherwise -> test-mode (*#0*#) instructions (auto-enables USB debugging).

    Returns True if the caller should then wait for an authorized ADB device,
    False if the user must act on the phone first (still returns, no error).
    """

    def _adb_ready():
        try:
            devs = bridge.adb_status()
        except bridge.BridgeError:
            return False
        return any(d["state"] == "device" for d in devs)

    if _adb_ready():
        log("  ADB is already enabled and authorized.")
        return True
    try:
        devs = bridge.adb_status()
    except bridge.BridgeError:
        devs = []
    if any(d["state"] == "unauthorized" for d in devs):
        log("  ADB is present but NOT authorized - on the phone tap 'Always allow'")
        log("  + OK on the 'Allow USB debugging' dialog (then unplug/replug).")
        return False

    d = None
    try:
        d = mtp.find_samsung()
    except bridge.BridgeError:
        d = None

    if d is not None and d.get("configs", 1) >= mtp.DIAG_CONFIG:
        log("  Trying the MTP/AT method to enable USB debugging ...")
        try:
            t = mtp.switch_to_diag()
        except mtp.MtpError as e:
            log(f"    could not switch to diag: {e}")
            t = None
        if t is not None and mtp.ping(t, attempts=6):
            try:
                t, lines = mtp.enable_adb_via_at(t)
                for ln in lines:
                    log(ln)
            except mtp.MtpError as e:
                log(f"    AT enable failed: {e}")
            log("")
            log("  PHONE: an 'Allow USB debugging' dialog should appear - tap")
            log("  'Always allow' + OK. If not, unplug/replug the USB cable.")
            return True
        log("    diag port did not answer - falling back to test mode.")
    else:
        log("  Device has no diag/modem USB config (single-config phone).")

    log("")
    log("  PHONE: use test mode instead - on the lock/setup screen tap the")
    log("  emergency-call icon and dial  *#0*#  -> test mode opens and turns")
    log("  USB debugging on automatically. Then plug in and allow debugging.")
    return False


def flow_download_mode_info():
    """Read real device info from download mode over the Odin protocol.

    Does the handshake (LOKE), reads the model via the session probe + PIT
    header, dumps the PIT and prints the parsed partition table, saving the
    raw PIT to a file. On MediaTek phones (A05/A06) whose proprietary agent
    refuses open-source LOKE it explains the limitation and reports the model
    from the specs instead.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("DOWNLOAD MODE INFO - Odin protocol")
        log("=" * 60)
        d = _download_mode_device()
        if not d:
            log("PHONE: enter download mode (power off, hold Volume Down + Power,")
            log("  then press Volume Up to the 'Downloading...' screen), keep it")
            log("  plugged in.")
            d = _wait_download_mode(log, timeout=30)
        if not d:
            raise RuntimeError(
                "phone is not in download mode (04e8:685d without ADB)"
            )
        t = mtp.target(d)
        ctx["target"] = t
        log(f"  USB: 04e8:{d['pid']:04x} bus={d['bus']} addr={d['address']}")
        log("")
        try:
            conn = bridge.odin_connect(t)
            log(f"  handshake: OK  ({conn[:120]})")
        except bridge.BridgeError as e:
            log(f"  handshake refused: {e}")
            _odin_diag(log)
            log("  Model (from specs): SM-A055F (A05) / SM-A065F (A06) -")
            log("  confirmed after a combination build: `getprop ro.product.model`")
            return

        model = _odin_model(log) or ""
        if model:
            log(f"  Model: {model}")
        else:
            log("  Model: (unread - see diagnostic above)")

        try:
            resp = json.loads(bridge.odin_pit(t))
            raw = bytes.fromhex(resp.get("hex", ""))
            out = os.path.join(tempfile.gettempdir(), "samsung_pit.bin")
            with open(out, "wb") as fh:
                fh.write(raw)
            log(f"  PIT dump: {len(raw)} bytes -> {out}")
            if not model:
                pm = pit.parse_model(raw)
                if pm:
                    model = pm
                    log(f"  Model (PIT header): {model}")
            entries = pit.parse_pit(raw)
            log("  Partition table:")
            log("  %-4s %-24s %12s  %s" % ("idx", "name", "size", "device"))
            for e in entries:
                if not e.is_flashable():
                    continue
                log("  %-4d %-24s %12s  0x%02x"
                    % (e.index, e.name, _fmt_bytes(e.size_bytes()),
                       e.device_type))
        except (bridge.BridgeError, ValueError, KeyError, OSError) as e:
            log(f"  PIT read failed: {e}")
            _odin_diag(log)

    steps = [Step("download_mode_info", _run)]
    return Flow("download mode info (real Odin read)", steps)


def _fmt_bytes(n):
    """Human-readable byte count (e.g. 34359738368 -> '32 GiB')."""
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.0f} TiB"


# Fastboot is exposed on the MediaTek Samsung models (A14 5G / A05 / A06) when
# the bootloader is unlocked, as the Google fastboot gadget 18d1:4ee0.  The
# flows below wrap the platform-tools `fastboot` binary for those devices.
_FASTBOOT_IMAGE_ENV = "FASTBOOT_IMAGE"
_FASTBOOT_PARTITION_ENV = "FASTBOOT_PARTITION"


def _fastboot_bin():
    return shutil.which("fastboot")


def _wait_fastboot(log, timeout=30):
    """Wait for a fastboot device (state 'fastboot' from `fastboot devices`)."""
    fb = _fastboot_bin()
    if not fb:
        log("  'fastboot' binary not found on this PC - install Android")
        log("  platform-tools (sudo pacman -S android-tools / apt install")
        log("  android-sdk-platform-tools) and rerun.")
        return False
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cancel_requested():
            raise FlowCancelled("cancelled while waiting for fastboot")
        try:
            proc = subprocess.run(
                [fb, "devices"], capture_output=True, text=True, timeout=15
            )
            # `fastboot devices` prints one line per device with NO header
            # (unlike `adb devices`), so examine every line.
            lines = (proc.stdout or proc.stderr).splitlines()
            if any("fastboot" in l for l in lines):
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    log("  no device in fastboot mode. Put the phone into fastboot")
    log("  (MediaTek A14/A05/A06: power off, hold Volume Down + Power, or")
    log("  from Android `adb reboot bootloader`) and rerun.")
    return False


def _fastboot_run(log, args, timeout=60):
    """Run one fastboot command, echoing args + output. Returns stdout."""
    fb = _fastboot_bin()
    log(f"  > fastboot {' '.join(args)}")
    try:
        proc = subprocess.run(
            [fb, *args], capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        log("      ERROR: command timed out")
        return ""
    except Exception as e:  # noqa: BLE001
        log(f"      ERROR: {e}")
        return ""
    out = (proc.stdout or proc.stderr).strip()
    if out:
        log(f"      {out[:800]}")
    return out


def _fastboot_erase(log, partition, timeout=120):
    """Erase a partition, falling back to `format` for MediaTek fastboots
    that reject the `erase` command ('unknown command'). Returns stdout."""
    out = _fastboot_run(log, ["erase", partition], timeout=timeout)
    if "FAILED" in out or "unknown command" in out or "Error" in out:
        log(f"  `erase {partition}` not supported - trying `format` ...")
        out = _fastboot_run(log, ["format", partition], timeout=timeout)
    return out


_MEDIA_NOTE = (
    "  NOTE: this MediaTek Samsung fastboot only implements a minimal command"
    "  set - `erase`/`format` are often rejected and `getvar all` hangs. If the"
    "  command above failed, use the RECOVERY-menu 'Wipe data/factory reset'"
    "  or Download-mode (odin4) instead - those are the supported paths."
)


def _fastboot_image(log):
    """Locate an image to flash: FASTBOOT_IMAGE env, ctx, or a boot.img under
    ~/Downloads / cwd / root dir."""
    env = os.environ.get(_FASTBOOT_IMAGE_ENV)
    if env and os.path.isfile(env):
        return env
    dirs = [os.path.expanduser("~/Downloads"), os.path.expanduser("~"), os.getcwd()]
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for pat in ("boot.img", "*.img", "*.tar", "*.tar.md5"):
            cands = sorted(glob.glob(os.path.join(d, pat)),
                           key=os.path.getmtime, reverse=True)
            if cands:
                return cands[0]
    return ""


def _fastboot_partition(log):
    return os.environ.get(_FASTBOOT_PARTITION_ENV, "boot")


def flow_fastboot():
    """Fastboot overview: enumerate devices, check bootloader state."""

    def _run(ctx, log):
        log("=" * 60)
        log("FASTBOOT MODE - device overview")
        log("=" * 60)
        log("  MediaTek Samsung models (A14 5G / A05 / A06) expose fastboot")
        log("  (18d1:4ee0) when the bootloader is unlocked. Exynos/Snapdragon")
        log("  Samsung phones do not use fastboot - use Download mode for those.")
        log("")
        if not _wait_fastboot(log):
            return
        log("")
        log("DEVICES")
        _fastboot_run(log, ["devices"])
        log("")
        log("BOOTLOADER STATE")
        for v in ("all", "unlocked", "slot-count", "has-slot:boot"):
            if v == "all":
                out = _fastboot_run(log, ["getvar", "all"], timeout=8)
                if not out:
                    log(_MEDIA_NOTE)
            else:
                _fastboot_run(log, ["getvar", v], timeout=8)
        log("")
        log("  Next: use 'flash partition', 'erase partition', 'unlock/relock")
        log("  bootloader', or 'wipe userdata' from the fastboot methods.")

    steps = [Step("fastboot_overview", _run)]
    return Flow("fastboot device overview", steps)


def flow_fastboot_devices():
    """List fastboot devices attached to the PC."""

    def _run(ctx, log):
        log("=" * 60)
        log("FASTBOOT - LIST DEVICES")
        log("=" * 60)
        if not _wait_fastboot(log):
            return
        _fastboot_run(log, ["devices"])

    steps = [Step("fastboot_devices", _run)]
    return Flow("fastboot list devices", steps)


def flow_fastboot_getvar():
    """Read all fastboot variables (device info)."""

    def _run(ctx, log):
        log("=" * 60)
        log("FASTBOOT - GETVAR ALL (device info)")
        log("=" * 60)
        if not _wait_fastboot(log):
            return
        log("")
        _fastboot_run(log, ["getvar", "all"], timeout=40)

    steps = [Step("fastboot_getvar", _run)]
    return Flow("fastboot getvar all", steps)


def flow_fastboot_flash():
    """Flash an image to a partition via fastboot.

    Target image: FASTBOOT_IMAGE env var, or the newest boot.img / *.img /
    *.tar under ~/Downloads or the working dir. Partition: FASTBOOT_PARTITION
    env var (default 'boot')."""

    def _run(ctx, log):
        log("=" * 60)
        log("FASTBOOT - FLASH PARTITION")
        log("=" * 60)
        log("  Flashing is only allowed with an UNLOCKED bootloader.")
        if not _wait_fastboot(log):
            return
        image = _fastboot_image(log)
        partition = _fastboot_partition(log)
        if not image:
            log("")
            log("  No image found. Set FASTBOOT_IMAGE=/path/to/image.img (or put")
            log("  a boot.img / *.img in ~/Downloads) and rerun. Partition:")
            log("  FASTBOOT_PARTITION=<name> (default 'boot').")
            raise RuntimeError("no fastboot image found (see FASTBOOT_IMAGE)")
        log(f"  image:    {image}")
        log(f"  partition: {partition}")
        log("")
        _fastboot_run(log, ["flash", partition, image], timeout=180)
        log("")
        log("  Done. `fastboot reboot` to boot the flashed image.")

    steps = [Step("fastboot_flash", _run)]
    return Flow("fastboot flash partition", steps)


def flow_fastboot_erase():
    """Erase a partition via fastboot."""

    def _run(ctx, log):
        log("=" * 60)
        log("FASTBOOT - ERASE PARTITION")
        log("=" * 60)
        if not _wait_fastboot(log):
            return
        partition = _fastboot_partition(log)
        log(f"  partition: {partition}  (set FASTBOOT_PARTITION to change)")
        log("")
        _fastboot_erase(log, partition, timeout=60)
        log("  Done.")

    steps = [Step("fastboot_erase", _run)]
    return Flow("fastboot erase partition", steps)


def flow_fastboot_format():
    """Format a partition (ext4/f2fs) via fastboot."""

    def _run(ctx, log):
        log("=" * 60)
        log("FASTBOOT - FORMAT PARTITION")
        log("=" * 60)
        if not _wait_fastboot(log):
            return
        partition = _fastboot_partition(log)
        log(f"  partition: {partition}  (set FASTBOOT_PARTITION to change)")
        log("")
        _fastboot_run(log, ["format", partition], timeout=120)
        log("  Done.")

    steps = [Step("fastboot_format", _run)]
    return Flow("fastboot format partition", steps)


def flow_fastboot_unlock():
    """Unlock the bootloader (flashing unlock). Wipes the device."""

    def _run(ctx, log):
        log("=" * 60)
        log("FASTBOOT - UNLOCK BOOTLOADER (flashing unlock)")
        log("=" * 60)
        log("  WARNING: unlocking wipes ALL user data and trips Knox/FRP on")
        log("  Samsung. This is irreversible on most builds.")
        if not _wait_fastboot(log):
            return
        log("")
        log("  Confirming current lock state ...")
        _fastboot_run(log, ["getvar", "unlocked"])
        log("")
        out = _fastboot_run(log, ["flashing", "unlock"], timeout=60)
        if "FAILED" in out or "Error" in out:
            log("  `flashing unlock` failed - trying `oem unlock` ...")
            _fastboot_run(log, ["oem", "unlock"], timeout=60)
        log("")
        log("  If prompted, confirm on the phone screen. The device will wipe")
        log("  and reboot. Rerun 'fastboot device overview' to confirm.")

    steps = [Step("fastboot_unlock", _run)]
    return Flow("fastboot unlock bootloader", steps)


def flow_fastboot_lock():
    """Relock the bootloader (flashing lock)."""

    def _run(ctx, log):
        log("=" * 60)
        log("FASTBOOT - RELOCK BOOTLOADER (flashing lock)")
        log("=" * 60)
        if not _wait_fastboot(log):
            return
        log("")
        _fastboot_run(log, ["getvar", "unlocked"])
        out = _fastboot_run(log, ["flashing", "lock"], timeout=60)
        if "FAILED" in out or "Error" in out:
            _fastboot_run(log, ["oem", "lock"], timeout=60)
        log("")
        log("  If prompted, confirm on the phone screen. The device will wipe.")

    steps = [Step("fastboot_lock", _run)]
    return Flow("fastboot relock bootloader", steps)


def flow_fastboot_frp():
    """Clear FRP via fastboot: erase the frp partition and reset provisioning
    flags on MediaTek Samsung models with an unlocked bootloader."""

    def _run(ctx, log):
        log("=" * 60)
        log("FASTBOOT - FRP BYPASS (erase frp partition)")
        log("=" * 60)
        log("  Works on MediaTek A14/A05/A06 with the bootloader UNLOCKED.")
        if not _wait_fastboot(log):
            return
        log("")
        log("  Erasing frp partition ...")
        frp1 = _fastboot_erase(log, "frp", timeout=60)
        log("  Erasing cache (resets provisioning flags) ...")
        frp2 = _fastboot_erase(log, "cache", timeout=60)
        if "FAILED" in frp1 or "FAILED" in frp2:
            log("")
            log(_MEDIA_NOTE)
            log("")
            log("  FRP on this model is best cleared with ADB after the")
            log("  combination-firmware route (MTK mode), or with the recovery")
            log("  factory reset + 'adb frp clear' path.")
            return
        log("")
        log("  Rebooting ...")
        _fastboot_run(log, ["reboot"])
        log("")
        log("  Done. On boot the phone should present as a fresh device and")
        log("  skip the Google account verification. If it still stops at")
        log("  FRP, run 'fastboot format userdata' then redo this.")

    steps = [Step("fastboot_frp", _run)]
    return Flow("fastboot frp bypass", steps)


def flow_fastboot_wipe():
    """Wipe userdata + cache via fastboot (factory reset from bootloader)."""

    def _run(ctx, log):
        log("=" * 60)
        log("FASTBOOT - WIPE USERDATA / FACTORY RESET")
        log("=" * 60)
        log("  Erases ALL user data (apps, accounts, photos, lock).")
        if not _wait_fastboot(log):
            return
        log("")
        log("  Erasing userdata ...")
        wipe = _fastboot_erase(log, "userdata", timeout=180)
        log("  Erasing cache ...")
        wipe2 = _fastboot_erase(log, "cache", timeout=60)
        if "FAILED" in wipe or "FAILED" in wipe2:
            log("")
            log(_MEDIA_NOTE)
            log("")
            log("  The fastboot wipe did not run. Use 'Screen lock remove' ->")
            log("  'recovery factory reset' instead - that always works on the")
            log("  A14 5G and does not need an unlocked bootloader.")
            return
        log("")
        log("  Rebooting ...")
        _fastboot_run(log, ["reboot"])
        log("")
        log("  Done. The phone boots to setup as a fresh device. A Google FRP")
        log("  screen may still appear - use 'fastboot frp bypass' for that.")

    steps = [Step("fastboot_wipe", _run)]
    return Flow("fastboot wipe userdata", steps)


def flow_fastboot_reboot():
    """Reboot out of fastboot into the OS."""

    def _run(ctx, log):
        log("=" * 60)
        log("FASTBOOT - REBOOT DEVICE")
        log("=" * 60)
        if not _wait_fastboot(log):
            return
        _fastboot_run(log, ["reboot"])
        log("  Rebooting to normal mode.")

    steps = [Step("fastboot_reboot", _run)]
    return Flow("fastboot reboot", steps)


def flow_fastboot_reboot_bootloader():
    """Reboot the phone back into fastboot/bootloader mode."""

    def _run(ctx, log):
        log("=" * 60)
        log("FASTBOOT - REBOOT TO BOOTLOADER")
        log("=" * 60)
        if not _wait_fastboot(log):
            return
        _fastboot_run(log, ["reboot", "bootloader"])
        log("  Rebooting to bootloader.")

    steps = [Step("fastboot_reboot_bootloader", _run)]
    return Flow("fastboot reboot to bootloader", steps)


def flow_fastboot_recovery():
    """Reboot from fastboot into recovery mode."""

    def _run(ctx, log):
        log("=" * 60)
        log("FASTBOOT - REBOOT TO RECOVERY")
        log("=" * 60)
        if not _wait_fastboot(log):
            return
        _fastboot_run(log, ["reboot", "recovery"])
        log("  Rebooting to recovery.")

    steps = [Step("fastboot_recovery", _run)]
    return Flow("fastboot reboot to recovery", steps)


def flow_fastboot_set_active():
    """Set the active A/B slot."""

    def _run(ctx, log):
        log("=" * 60)
        log("FASTBOOT - SET ACTIVE SLOT")
        log("=" * 60)
        if not _wait_fastboot(log):
            return
        slot = os.environ.get("FASTBOOT_SLOT", "a")
        log(f"  slot: {slot}  (set FASTBOOT_SLOT=a/b to change)")
        log("")
        _fastboot_run(log, ["set_active", slot], timeout=30)
        log("  Done.")

    steps = [Step("fastboot_set_active", _run)]
    return Flow("fastboot set active slot", steps)


def flow_fastboot_oem():
    """Send a raw fastboot OEM command (advanced)."""

    def _run(ctx, log):
        log("=" * 60)
        log("FASTBOOT - RAW OEM COMMAND")
        log("=" * 60)
        if not _wait_fastboot(log):
            return
        cmd = os.environ.get("FASTBOOT_OEM", "device-info")
        log(f"  command: fastboot oem {cmd}  (set FASTBOOT_OEM to change)")
        log("")
        _fastboot_run(log, ["oem", *cmd.split()], timeout=60)
        log("  Done.")

    steps = [Step("fastboot_oem", _run)]
    return Flow("fastboot oem command", steps)


def flow_fastboot_continue():
    """Resume normal boot after a fastboot pause."""

    def _run(ctx, log):
        log("=" * 60)
        log("FASTBOOT - CONTINUE BOOT")
        log("=" * 60)
        if not _wait_fastboot(log):
            return
        _fastboot_run(log, ["continue"])
        log("  Continuing boot.")

    steps = [Step("fastboot_continue", _run)]
    return Flow("fastboot continue boot", steps)


def flow_reboot(target, title, manual):
    """Reboot the phone into a given mode.

    Tries, in order: authorized ADB (`adb reboot <target>`), the diag/AT
    channel (works from MTP when the phone is in test mode), then manual
    key-combo instructions.
    """

    def _run(ctx, log):
        log("=" * 60)
        log(title.upper())
        log("=" * 60)
        try:
            up = any(d["state"] == "device" for d in bridge.adb_status())
        except bridge.BridgeError:
            up = False
        if up:
            cmd = ("reboot " + target).strip()
            log(f"  ADB authorized - sending: adb shell {cmd}")
            try:
                out = bridge.adb_shell(cmd)
                log(f"  reboot sent: {out[:120] or 'ok (phone is restarting)'}")
                return
            except bridge.BridgeError as e:
                log(f"  adb reboot failed: {e}")
        else:
            log("  no authorized ADB - trying the MTP/diag path ...")
            t = None
            try:
                t = mtp.switch_to_diag()
            except mtp.MtpError as e:
                log(f"  diag switch refused: {e}")
            if t is not None and mtp.ping(t, attempts=4):
                for cmd in ("+FUN=0", "+FUN=1", "+FUN=2", "+REBOOT", "+RB"):
                    if cancel_requested():
                        raise FlowCancelled("cancelled during reboot attempt")
                    try:
                        r = mtp.at(cmd, t, timeout_ms=4000)
                        if r.get("ok"):
                            log(f"  AT{cmd} -> OK (phone may be restarting)")
                            return
                        log(f"  AT{cmd} -> {r.get('reply') or r.get('ok') or 'no reply'}")
                    except mtp.MtpError as e:
                        log(f"  AT{cmd} -> {e}")
                log("  AT reboot commands not honored (phone needs test mode *#0*#).")
            else:
                log("  AT port not reachable (phone not in test mode).")
        log("")
        log("  Do it manually:")
        for line in manual:
            log(f"    {line}")

    steps = [Step(f"reboot_{target or 'normal'}", _run)]
    return Flow(title, steps)


def flow_reboot_recovery():
    return flow_reboot(
        "recovery",
        "reboot to recovery",
        [
            "power off the phone",
            "hold Volume Up + Power (add Home on models with a Home button)",
            "release on the Samsung logo -> you are in recovery mode",
        ],
    )


def flow_reboot_download():
    return flow_reboot(
        "download",
        "reboot to download mode",
        [
            "power off the phone",
            "hold Volume Down + Home + Power (or Volume Down + Power)",
            "release on the 'Downloading...' warning",
            "press Volume Up to continue -> download mode (04e8:685d)",
        ],
    )


def flow_reboot_normal():
    return flow_reboot(
        "",
        "reboot normally",
        [
            "press and hold the Power button until the phone restarts",
            "or 'adb reboot' when ADB is authorized",
        ],
    )


def flow_reboot_edl():
    return flow_reboot(
        "edl",
        "reboot to EDL (Qualcomm)",
        [
            "EDL is Qualcomm-only (not available on Exynos/MediaTek models like",
            "the A05/A06 or the J3 Top)",
            "Qualcomm Samsung: power off, then hold Volume Up + Volume Down while",
            "plugging into the PC -> 05c6:9008",
        ],
    )


def flow_reboot_bootloader():
    return flow_reboot(
        "bootloader",
        "reboot to fastboot/bootloader",
        [
            "Samsung has no fastboot - this only applies to Google /",
            "Qualcomm-bootloader devices via 'adb reboot bootloader'",
            "on Samsung use 'reboot to download mode' instead",
        ],
    )


def flow_factory_reset():
    """Factory reset via ADB when possible, with a guided recovery fallback.

    Tries `adb shell recovery --wipe_data` first (works when USB debugging is
    authorized), then falls back to on-screen recovery-menu instructions.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("FACTORY RESET")
        log("=" * 60)
        try:
            up = any(d["state"] == "device" for d in bridge.adb_status())
        except bridge.BridgeError:
            up = False
        if up:
            log("  ADB authorized - sending: adb shell recovery --wipe_data")
            try:
                out = bridge.adb_shell("recovery --wipe_data", timeout=30)
                log(f"  response: {out[:160] or 'ok'}")
                log("  The phone is wiping /data and will restart.")
                return
            except bridge.BridgeError as e:
                log(f"  adb wipe failed: {e} (falling back to recovery menu)")
        else:
            log("  no authorized ADB - using the guided recovery menu.")
        log("")
        log("  Manual recovery reset:")
        log("  1. Power the phone off completely.")
        log("  2. Hold Volume Up + Power together.")
        log("  3. Keep holding until the Samsung logo appears; release Power but")
        log("     KEEP holding Volume Up until the recovery menu appears.")
        log("     (If you see 'No command', hold Power and press Volume Up once.)")
        log("  4. Volume keys: highlight 'Wipe data/factory reset' -> Power.")
        log("  5. Highlight 'Factory data reset' -> Power.")
        log("  6. Highlight 'Reboot system now' -> Power.")
        log("")
        log("  WARNING: if a Google account was on the phone it will stop at")
        log("  'Verify your account' (Google FRP). That is expected; then use")
        log("  the FRP bypass tab to clear it.")

    steps = [Step("factory_reset", _run)]
    return Flow("factory reset", steps)


def flow_setup_wizard():
    """Classic ADB-based bypass for Samsung devices on older Android versions.

    The exact command set depends on the Android version and firmware.
    Edit COMMANDS below to match the device you are working on.
    """
    COMMANDS = [
        # grant the adb shell easy permissions once booted to setup wizard
        ("unlock screens", "wm dismiss-keyguard"),
        ("open settings via activity", "am start -n com.android.settings/.Settings"),
        ("allow USB settings (Android 7-8)", "settings put global usb_mass_storage_enabled 1"),
        ("disable FRP lock flag via settings provider", "settings put secure frp_done 1"),
        ("back to home", "input keyevent 3"),
    ]

    def _run(ctx, log):
        if not _wait_for_adb(ctx, log):
            raise RuntimeError("no adb device available for setup-wizard flow")
        for label, cmd in COMMANDS:
            log(f"  > adb shell {cmd}")
            out = bridge.adb_shell(cmd)
            if out:
                log(f"      {out[:120]}")
            time.sleep(2)

    steps = [
        Step("run_adb_sequence", _run),
        Step(
            "verify",
            lambda ctx, log: log(
                "check FRP flag: "
                + str(bridge.adb_shell("settings get secure frp_done", timeout=10))
            ),
        ),
    ]
    return Flow("setup wizard adb bypass", steps)


def flow_detect():
    """Full device detection: every Samsung USB device, its interfaces and
    configs, the mode it is in (MTP / ADB / download / EDL / HID), and the
    ADB state. Tells you which job+mode is reachable right now."""

    def _describe_interfaces(d):
        lines = []
        for i in d.get("interfaces", []):
            name = _IFACE_CLASS.get(i.get("class"), f"cls{i.get('class')}")
            tags = []
            if (
                i.get("class") == 255
                and i.get("subclass") == 66
                and i.get("protocol") == 1
            ):
                tags.append("ADB")
            if i.get("class") == 3:
                tags.append("HID")
            if i.get("class") == 2:
                tags.append("CDC-ACM")
            suffix = f" [{', '.join(tags)}]" if tags else ""
            lines.append(
                f"    iface {i.get('number')}: {name} "
                f"(cl={i.get('class')}/sc={i.get('subclass')}/pr={i.get('protocol')}){suffix}"
            )
        return lines

    def _mode(d, usb_devs):
        pid = d.get("pid")
        if (d.get("vid"), pid) in [(0x05c6, 0x9008)]:
            return "EDL (Qualcomm 9008)"
        if pid in _ODIN_PIDS:
            return "DOWNLOAD MODE"
        ifany_adb = any(
            i.get("class") == 255 and i.get("subclass") == 66 and i.get("protocol") == 1
            for i in d.get("interfaces", [])
        )
        if ifany_adb:
            return "ADB (debug composite up)"
        if any(i.get("class") == 6 for i in d.get("interfaces", [])):
            return "MTP / IMAGE (setup wizard or normal boot)"
        if any(i.get("class") == 3 for i in d.get("interfaces", [])):
            return "HID interface present"
        if d.get("configs", 1) > 1:
            return "MULTI-CONFIG (MTP w/ switchable modes)"
        return "OTHER"

    def _run(ctx, log):
        log("scanning USB + ADB ...")
        usb = bridge.detect_usb()
        hid = bridge.list_samsung_hid()
        ctx.update(usb=usb, hid=hid)
        adb = []
        try:
            adb = bridge.adb_status()
        except bridge.BridgeError as e:
            log(f"  adb: {e}")
        ctx["adb"] = adb

        samsung = [d for d in usb if d.get("vid") == mtp.SAMSUNG_VID]
        if not samsung:
            log("  No Samsung device over USB - plug it in, check cable/port.")
        for d in samsung:
            log("")
            log(
                f"SAMSUNG 04e8:{d['pid']:04x}  bus={d['bus']} addr={d['address']} "
                f"configs={d.get('configs', 1)}  {d.get('product') or ''}"
            )
            for ln in _describe_interfaces(d):
                log(ln)
            log(f"  >> MODE: {_mode(d, usb)}")

        edl = [d for d in usb if (d.get("vid"), d.get("pid")) == (0x05c6, 0x9008)]
        if edl:
            log("")
            log(f"  EDL/Qualcomm device: 05c6:9008 bus={edl[0]['bus']} addr={edl[0]['address']}")

        mtk_devs = [d for d in usb if d.get("vid") == mtk.MTK_VID]
        if mtk_devs:
            log("")
            log("  MediaTek low-level device(s) (VID 0e8d):")
            for d in mtk_devs:
                log(
                    f"    {d['vid']:04x}:{d['pid']:04x} bus={d['bus']} addr={d['address']} "
                    f"{d.get('product') or ''}"
                )
            log("    -> use 'Detect' -> MTK -> 'BROM / preloader info' for chip details")

        if hid:
            log("")
            log("  HID targets (download-mode tools talk to these):")
            for t in hid:
                log(
                    f"    {t['label']} iface={t['interface']} "
                    f"in=0x{t['in_ep']:02x} out=0x{t['out_ep']:02x}"
                )

        log("")
        if not adb:
            log("  ADB: no devices")
        for a in adb:
            log(f"  ADB: {a['serial']}  state={a['state']}  {a['extra']}")

        log("")
        log("  Reachable now:")
        if adb and any(a["state"] == "device" for a in adb):
            log("    - ADB jobs: FRP bypass / Screen lock remove / Read info")
        elif adb:
            log("    - ADB present but UNAUTHORIZED - tap 'Always allow' on the phone")
        if any(d.get("pid") in _ODIN_PIDS for d in samsung):
            log("    - Download mode: read PIT / info via 04e8:685d")
        if edl:
            log("    - EDL mode: firehose partition access (needs firehose loader)")
        if mtk_devs:
            log("    - MTK low-level mode: BROM/preloader/DA - Detect -> MTK")
        if any(i.get("class") == 3 for d in samsung for i in d.get("interfaces", [])):
            log("    - HID interface: raw HID read/write via hid-open")
        if not samsung and not edl and not adb and not mtk_devs:
            log("    - nothing yet - plug the phone in / put it in the right mode")

    steps = [Step("full_detection", _run)]
    return Flow("detect", steps)


def flow_at_info():
    """Read phone identity over the diag AT port (like commercial 'Read Info'
    via MTP): switch to diag config, then DEVCONINFO / IMEI / versions."""

    def _run(ctx, log):
        log("switching USB to diag/modem config ...")
        try:
            t = mtp.switch_to_diag()
        except mtp.MtpError as e:
            log(f"  NOT switching: {e}")
            log("  Reading over plain MTP instead (no diag channel needed) ...")
            try:
                info = mtp.read_mtp_info()
                if info:
                    log(f"  MTP session: OK")
                    for k, v in (info or {}).items():
                        if k != "vendor_ops":
                            log(f"    {k}: {v}")
                else:
                    log("  MTP session refused (normal on FRP / setup screens).")
            except mtp.MtpError as e2:
                log(f"  MTP read failed: {e2}")
            try:
                r = mtp.read_device_info()
                reply = r.get("reply") or r.get("ok")
                log(f"  device info: {reply if reply else '(no reply)'}")
            except mtp.MtpError as e2:
                log(f"  device info: {e2}")
            log("  Use 'Read device info / ADB' when the phone shows a debug")
            log("  (ADB) interface, or enter test mode (*#0*#) for the full AT dump.")
            return
        ctx["target"] = t
        log(f"  diag target: {t}")
        if not mtp.ping(t, attempts=8):
            raise RuntimeError(
                "AT port not responding - is the phone awake and in test mode "
                "(*#0*# / **# from the Emergency call dialer)?"
            )
        log("  AT alive")
        # Model / firmware / IMEI: generic AT commands first (may be rejected
        # by Samsung firmwares), then the vendor DEVCONINFO dump.
        for name, cmd in [
            ("model", "+CGMM"),
            ("firmware", "+CGMR"),
            ("IMEI", "+CGSN"),
            ("subscriber id (IMSI)", "+CIMI"),
            ("device info (vendor)", "+DEVCONINFO"),
        ]:
            try:
                r = mtp.at(cmd, t, timeout_ms=8000)
                reply = r.get("reply") or r.get("ok")
                log(f"  {name}: {reply if reply else '(no reply)'}")
            except mtp.MtpError as e:
                log(f"  {name}: {e}")

    steps = [Step("at_read_info", _run)]
    return Flow("at read info (MTP/AT)", steps)


def flow_samsung_emergency_call():
    """Samsung FRP bypass via emergency call method.

    Works on Samsung devices by:
    1. Using emergency call to access browser/dialer
    2. Opening settings via intent
    3. Enabling ADB and clearing FRP flags
    """

    def _run(ctx, log):
        log("=" * 60)
        log("SAMSUNG EMERGENCY CALL FRP BYPASS")
        log("=" * 60)
        log("This method uses the emergency call interface to bypass FRP")
        log("on Samsung devices running Android 7-13.")
        log("")
        log("INSTRUCTIONS:")
        log("1. On the 'Verify your account' screen, tap Emergency Call")
        log("2. Dial *#*#4636#*#* (opens Testing menu)")
        log("3. Tap 'Phone information' -> 'Run ping test'")
        log("4. When browser opens, navigate to: bit.ly/2nL2j7b")
        log("5. Download FRP bypass APK and install")
        log("6. Open the bypass app to enable ADB")
        log("")
        log("After ADB is enabled, this tool will clear FRP flags automatically.")
        
        # Wait for ADB
        if not _wait_for_adb(ctx, log, timeout=120):
            log("ADB not detected. Please follow the manual instructions above.")
            return
        
        # Clear FRP flags
        ADB_STEPS = [
            ("mark setup wizard run", "settings put global setup_wizard_has_run 1"),
            ("mark user setup complete", "settings put secure user_setup_complete 1"),
            ("mark device provisioned", "settings put global device_provisioned 1"),
            ("disable Google setup wizard", "pm disable-user --user 0 com.google.android.setupwizard"),
            ("disable Samsung setup wizard", "pm disable-user --user 0 com.sec.android.app.SecSetupWizard"),
        ]
        
        log("Clearing FRP flags...")
        for label, cmd in ADB_STEPS:
            log(f"  > {label}")
            try:
                bridge.adb_shell(cmd, timeout=30)
            except bridge.BridgeError as e:
                log(f"      ERROR: {e}")
            time.sleep(1)
        
        log("Done. Reboot the device to complete setup.")

    steps = [Step("samsung_emergency_call", _run)]
    return Flow("samsung emergency call frp bypass", steps)


def flow_samsung_talkback():
    """Samsung FRP bypass via Talkback accessibility service.

    Uses the Talkback vulnerability on older Samsung devices (Android 6-9)
    to access settings and enable ADB.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("SAMSUNG TALKBACK FRP BYPASS")
        log("=" * 60)
        log("This method uses Talkback accessibility to bypass FRP")
        log("on Samsung devices running Android 6-9.")
        log("")
        log("INSTRUCTIONS:")
        log("1. On the 'Verify your account' screen, draw an 'L' shape")
        log("2. Tap 'Talkback' -> 'Settings' -> 'Text-to-speech settings'")
        log("3. Tap the settings icon (gear) repeatedly until search opens")
        log("4. Search for 'Google Account Manager' and open it")
        log("5. Tap 'Sign in' -> type any email -> tap 'Try again'")
        log("6. Browser will open - navigate to: bit.ly/2nL2j7b")
        log("7. Download and install FRP bypass APK")
        log("8. Open bypass app to enable ADB")
        log("")
        log("After ADB is enabled, this tool will clear FRP flags automatically.")
        
        # Wait for ADB
        if not _wait_for_adb(ctx, log, timeout=120):
            log("ADB not detected. Please follow the manual instructions above.")
            return
        
        # Clear FRP flags
        ADB_STEPS = [
            ("mark setup wizard run", "settings put global setup_wizard_has_run 1"),
            ("mark user setup complete", "settings put secure user_setup_complete 1"),
            ("mark device provisioned", "settings put global device_provisioned 1"),
            ("disable Google setup wizard", "pm disable-user --user 0 com.google.android.setupwizard"),
            ("disable Samsung setup wizard", "pm disable-user --user 0 com.sec.android.app.SecSetupWizard"),
        ]
        
        log("Clearing FRP flags...")
        for label, cmd in ADB_STEPS:
            log(f"  > {label}")
            try:
                bridge.adb_shell(cmd, timeout=30)
            except bridge.BridgeError as e:
                log(f"      ERROR: {e}")
            time.sleep(1)
        
        log("Done. Reboot the device to complete setup.")

    steps = [Step("samsung_talkback", _run)]
    return Flow("samsung talkback frp bypass", steps)


def flow_samsung_account_bypass():
    """Samsung Account FRP bypass.

    Removes Samsung Account lock (Find My Mobile) on Samsung devices.
    Works by removing the Samsung Account app data and clearing Knox flags.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("SAMSUNG ACCOUNT BYPASS")
        log("=" * 60)
        log("Removes Samsung Account (Find My Mobile) lock.")
        log("Requires ADB access.")
        log("")
        
        # Ensure ADB is available
        if not any(d["state"] == "device" for d in bridge.adb_status()):
            log("No authorized ADB device. Please enable ADB first.")
            return
        
        SAMSUNG_APPS = [
            "com.samsung.android.app.samsungaccount",
            "com.samsung.android.scloud",
            "com.samsung.android.drivelink.stub",
            "com.samsung.android.lool",
            "com.samsung.android.b2b",
        ]
        
        log("Removing Samsung Account apps and data...")
        for app in SAMSUNG_APPS:
            log(f"  > Clearing {app}")
            try:
                bridge.adb_shell(f"pm clear {app}", timeout=30)
                bridge.adb_shell(f"pm disable-user --user 0 {app}", timeout=30)
            except bridge.BridgeError as e:
                log(f"      ERROR: {e}")
        
        log("Clearing Knox flags...")
        KNOX_CMDS = [
            ("reset Knox counter", "settings put global knox_setup_complete 0"),
            ("disable Knox", "pm disable-user --user 0 com.sec.knox.bridge"),
            ("clear Knox data", "pm clear com.sec.knox.bridge"),
        ]
        
        for label, cmd in KNOX_CMDS:
            log(f"  > {label}")
            try:
                bridge.adb_shell(cmd, timeout=30)
            except bridge.BridgeError as e:
                log(f"      ERROR: {e}")
        
        log("Done. Reboot the device to complete Samsung Account removal.")

    steps = [Step("samsung_account_bypass", _run)]
    return Flow("samsung account bypass", steps)


def flow_mtk_sp_flash():
    """MTK FRP bypass via SP Flash Tool method.

    Uses MTK download mode to flash a custom scatter file that bypasses FRP.
    Works on MediaTek Samsung devices (A-series, some older models).
    """

    def _run(ctx, log):
        log("=" * 60)
        log("MTK FRP BYPASS - SP FLASH METHOD")
        log("=" * 60)
        log("This method uses MTK download mode to bypass FRP.")
        log("Works on MediaTek Samsung devices.")
        log("")
        log("INSTRUCTIONS:")
        log("1. Download SP Flash Tool for Linux")
        log("2. Get the device's scatter file (from firmware)")
        log("3. Modify scatter to exclude FRP partition")
        log("4. Flash the modified scatter via SP Flash Tool")
        log("5. Device will boot without FRP lock")
        log("")
        log("Alternatively, use combination firmware method:")
        log("1. Download COMBINATION firmware for your model")
        log("2. Flash via Odin or SP Flash Tool")
        log("3. Boot combination firmware (has ADB)")
        log("4. Use ADB FRP bypass to clear flags")
        log("5. Flash back stock firmware")
        log("")
        log("This tool can help with step 4 if you have ADB access.")
        
        # Check for MTK device
        try:
            mtk_devs = mtk.detect_mtk()
            if mtk_devs:
                log(f"Detected MTK device: {mtk_devs}")
                log("Device is in MTK mode - ready for SP Flash Tool.")
            else:
                log("No MTK device detected. Enter download mode:")
                log("  1. Power off device")
                log("  2. Hold Volume Up + Down and connect USB")
                log("  3. Device should enter MTK download mode")
        except Exception as e:
            log(f"MTK detection failed: {e}")

    steps = [Step("mtk_sp_flash", _run)]
    return Flow("mtk frp bypass (sp flash)", steps)


def flow_mtk_meta_mode():
    """MTK FRP bypass via META mode.

    Uses MTK META mode to access service menu and clear FRP.
    Works on MediaTek devices that support META mode.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("MTK FRP BYPASS - META MODE")
        log("=" * 60)
        log("This method uses MTK META mode to bypass FRP.")
        log("")
        log("INSTRUCTIONS:")
        log("1. Enter META mode:")
        log("   - Dial *#*#3646633#*#* on emergency dialer")
        log("   - Or use MTK Engineering Mode app if available")
        log("2. Navigate to: Connectivity -> CDS Information")
        log("3. Select 'Radio Information'")
        log("4. Type AT commands to clear FRP:")
        log("   AT+CLCK=\"SC\",0,\"0000\"")
        log("   AT+CLCK=\"FD\",0,\"0000\"")
        log("5. Reboot device")
        log("")
        log("If META mode is not accessible, use SP Flash Tool method instead.")
        
        # Try to detect MTK device
        try:
            mtk_devs = mtk.detect_mtk()
            if mtk_devs:
                log(f"Detected MTK device: {mtk_devs}")
                for dev in mtk_devs:
                    log(f"  Boot stage: {dev.get('boot_stage', 'unknown')}")
                    log(f"  Chip: {dev.get('chip', 'unknown')}")
            else:
                log("No MTK device detected in META mode.")
        except Exception as e:
            log(f"MTK detection failed: {e}")

    steps = [Step("mtk_meta_mode", _run)]
    return Flow("mtk frp bypass (meta mode)", steps)


def flow_qualcomm_edl_frp():
    """Qualcomm FRP bypass via EDL mode with firehose.

    Uses Qualcomm EDL (Emergency Download) mode with firehose loader
    to directly modify FRP partitions and clear Google account lock.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("QUALCOMM FRP BYPASS - EDL MODE")
        log("=" * 60)
        log("This method uses Qualcomm EDL mode to bypass FRP.")
        log("Works on Qualcomm Samsung devices.")
        log("")
        log("INSTRUCTIONS:")
        log("1. Enter EDL mode:")
        log("   - Power off device")
        log("   - Hold Volume Up + Down and connect USB")
        log("   - Or use: adb reboot edl (if ADB available)")
        log("2. Device should appear as 05c6:9008")
        log("3. Use QFIL or QPST to flash modified FRP partition")
        log("4. Or use this tool with firehose loader (if available)")
        log("")
        
        # Check for EDL device
        EDL_IDS = [(0x05c6, 0x9008)]
        found = None
        for _ in range(12):
            try:
                for d in bridge.detect_usb():
                    if (d.get("vid"), d.get("pid")) in EDL_IDS:
                        found = d
                        break
            except bridge.BridgeError:
                pass
            if found:
                break
            time.sleep(1.5)
        
        if found:
            log(f"EDL device detected: {found}")
            log("Device is in EDL mode.")
            log("")
            log("To clear FRP via EDL, you need:")
            log("1. Firehose loader for your device model")
            log("2. QFIL or QPST tool")
            log("3. Modified FRP partition or rawprogram0.xml")
            log("")
            log("Alternative: Use combination firmware to boot with ADB,")
            log("then use ADB FRP bypass method.")
        else:
            log("No EDL device detected.")
            log("Please enter EDL mode first (see instructions above).")

    steps = [Step("qualcomm_edl_frp", _run)]
    return Flow("qualcomm frp bypass (edl mode)", steps)


def flow_qualcomm_qfil_frp():
    """Qualcomm FRP bypass via QFIL tool.

    Provides instructions for using QFIL (Qualcomm Flash Image Loader)
    to bypass FRP on Qualcomm devices.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("QUALCOMM FRP BYPASS - QFIL METHOD")
        log("=" * 60)
        log("Instructions for using QFIL to bypass FRP.")
        log("")
        log("REQUIREMENTS:")
        log("1. QFIL tool (Qualcomm Flash Image Loader)")
        log("2. Device firmware (rawprogram0.xml, patch0.xml)")
        log("3. Qualcomm USB drivers")
        log("4. Device in EDL mode (05c6:9008)")
        log("")
        log("STEPS:")
        log("1. Put device in EDL mode:")
        log("   - Power off, hold Vol-Up + Vol-Down, connect USB")
        log("2. Open QFIL")
        log("3. Select 'Flat Build'")
        log("4. Load Programmer (prog_emmc_firehose_xxxx.mbn)")
        log("5. Load XML (rawprogram0.xml)")
        log("6. Modify XML to exclude FRP partition (frp, persist)")
        log("7. Click 'Download' to flash")
        log("8. Device will boot without FRP lock")
        log("")
        log("ALTERNATIVE: Flash combination firmware first:")
        log("1. Download combination firmware for your model")
        log("2. Flash via QFIL (include all partitions)")
        log("3. Boot combination firmware (has ADB)")
        log("4. Use ADB FRP bypass to clear Google account")
        log("5. Flash back stock firmware")

    steps = [Step("qualcomm_qfil_frp", _run)]
    return Flow("qualcomm frp bypass (qfil)", steps)


def flow_universal_frp_bypass():
    """Universal FRP bypass methods.

    Collection of universal FRP bypass techniques that work across
    different device manufacturers and Android versions.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("UNIVERSAL FRP BYPASS METHODS")
        log("=" * 60)
        log("Collection of FRP bypass methods that work on various devices.")
        log("")
        
        # Check for ADB
        adb_available = False
        try:
            adb_devs = bridge.adb_status()
            adb_available = any(d["state"] == "device" for d in adb_devs)
        except bridge.BridgeError:
            pass
        
        if adb_available:
            log("ADB is available - attempting ADB FRP bypass...")
            
            UNIVERSAL_ADB_CMDS = [
                ("Clear FRP flag", "settings put secure frp_done 1"),
                ("Mark setup complete", "settings put secure user_setup_complete 1"),
                ("Mark device provisioned", "settings put global device_provisioned 1"),
                ("Disable setup wizard", "pm disable-user --user 0 com.google.android.setupwizard"),
                ("Clear Google Play Services", "pm clear com.google.android.gms"),
                ("Clear Google Account Manager", "pm clear com.google.android.gms"),
            ]
            
            for label, cmd in UNIVERSAL_ADB_CMDS:
                log(f"  > {label}")
                try:
                    result = bridge.adb_shell(cmd, timeout=30)
                    if result:
                        log(f"      {result[:100]}")
                except bridge.BridgeError as e:
                    log(f"      ERROR: {e}")
                time.sleep(1)
            
            log("Done. Reboot the device.")
        else:
            log("ADB not available. Try these manual methods:")
            log("")
            log("METHOD 1: Google Keyboard Vulnerability (Android 5-7)")
            log("1. On FRP screen, tap on text field")
            log("2. Long-press on keyboard -> select 'Keyboard settings'")
            log("3. Search for 'Google Account Manager'")
            log("4. Tap 'Sign in' -> type any email -> 'Try again'")
            log("5. Browser opens -> download FRP bypass APK")
            log("6. Install and open bypass app")
            log("")
            log("METHOD 2: Pattern Bypass (Android 6-8)")
            log("1. Draw pattern 5 times incorrectly")
            log("2. Tap 'Forgot Pattern'")
            log("3. Enter Google account credentials")
            log("4. If unknown, use 'Forgot password' -> security questions")
            log("")
            log("METHOD 3: Calculator Method (Some Samsung/LG)")
            log("1. Type *#*#4636#*#* in emergency dialer")
            log("2. Opens testing menu -> use browser")
            log("3. Download FRP bypass APK")
            log("")
            log("METHOD 4: SIM PIN Bypass (Android 7-9)")
            log("1. Insert SIM with unknown PIN")
            log("2. Enter wrong PIN 3 times")
            log("3. Tap 'Forgot PIN' -> enter PUK")
            log("4. This bypasses FRP on some devices")

    steps = [Step("universal_frp_bypass", _run)]
    return Flow("universal frp bypass", steps)


def flow_frp_clear_adb():
    """Direct FRP clear via ADB (universal method).

    Clears FRP flags directly via ADB when device has ADB access.
    Works on most Android devices once ADB is enabled.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("FRP CLEAR - ADB METHOD")
        log("=" * 60)
        log("Clears FRP flags directly via ADB.")
        log("")
        
        # Ensure ADB is available
        if not any(d["state"] == "device" for d in bridge.adb_status()):
            log("No authorized ADB device. Please enable ADB first.")
            log("Use 'Enable USB debugging' flow first.")
            return
        
        FRP_CLEAR_CMDS = [
            ("Clear FRP flag", "settings put secure frp_done 1"),
            ("Mark setup complete", "settings put secure user_setup_complete 1"),
            ("Mark device provisioned", "settings put global device_provisioned 1"),
            ("Disable setup wizard", "pm disable-user --user 0 com.google.android.setupwizard"),
            ("Clear Google Play Services", "pm clear com.google.android.gms"),
            ("Clear Google Account Manager", "pm clear com.google.android.gms"),
            ("Clear FRP data", "rm -rf /data/system/frp"),
            ("Clear account data", "rm -rf /data/system/accounts_ce.db"),
            ("Clear account data (de)", "rm -rf /data/system/accounts_de.db"),
            ("Clear sync data", "rm -rf /data/system/sync"),
            ("Clear sync managers", "rm -rf /data/system/syncmanager.xml"),
        ]
        
        log("Clearing FRP flags and data...")
        for label, cmd in FRP_CLEAR_CMDS:
            log(f"  > {label}")
            try:
                result = bridge.adb_shell(cmd, timeout=30)
                if result and result.strip():
                    log(f"      {result[:100]}")
            except bridge.BridgeError as e:
                log(f"      ERROR: {e}")
            time.sleep(1)
        
        log("")
        log("Done. Reboot the device:")
        log("  adb reboot")
        log("")
        log("After reboot, the device should complete setup without FRP lock.")

    steps = [Step("frp_clear_adb", _run)]
    return Flow("frp clear (adb)", steps)


def flow_at_control():
    """Commercial-style FRP bypass (SamFw / FRP King 'Bypass FRP (MTP)'):
    MTP-mode phone -> switch USB to diag config -> enable USB debugging via
    AT commands -> 'Allow USB debugging' dialog -> ADB -> clear FRP flags."""

    ADB_STEPS = [
        ("mark setup wizard run", "settings put global setup_wizard_has_run 1"),
        ("mark user setup complete", "settings put secure user_setup_complete 1"),
        ("mark device provisioned",
         "content insert --uri content://settings/secure "
         "--bind name:s:DEVICE_PROVISIONED --bind value:i:1"),
        ("mark user setup complete (provider)",
         "content insert --uri content://settings/secure "
         "--bind name:s:user_setup_complete --bind value:i:1"),
        ("allow non-market apps",
         "content insert --uri content://settings/secure "
         "--bind name:s:INSTALL_NON_MARKET_APPS --bind value:i:1"),
        ("disable Google setup wizard",
         "pm disable-user --user 0 com.google.android.setupwizard"),
        ("disable Samsung setup wizard",
         "pm disable-user --user 0 com.sec.android.app.SecSetupWizard"),
        ("back to home", "am start -c android.intent.category.HOME -a android.intent.action.MAIN"),
    ]

    def _run(ctx, log):
        log("STEP 1/4: switch USB to diag/modem config (exposes AT port)")
        try:
            t = mtp.switch_to_diag()
        except mtp.MtpError as e:
            log(f"  NOT switching: {e}")
            if mtp.is_adb_composite(mtp.find_samsung() or {}):
                log("  The device is already exposing ADB - use "
                    "'FRP bypass' in ADB mode instead.")
            return
        ctx["target"] = t
        log(f"  diag target: {t}")

        log("STEP 2/4: bring the AT port up")
        log("PHONE: if the port does not answer, on the Welcome/Verify-account "
            "screen tap the emergency-call icon (NOT the normal dialer) and dial")
        log("    *#0*#   (trailing *# is required - *#0# alone does nothing).")
        log("  Some firmwares need a leading space before the code, or a second "
            "press of the call key. Test mode shows a tile grid when it works.")
        if not mtp.ping(t, attempts=8):
            raise RuntimeError(
                "AT port not responding - is the phone awake and in test mode?"
            )
        log("  AT alive")

        log("STEP 3/4: enable USB debugging via Samsung AT commands")
        log("NOTE: AT+DEBUGLVC makes the phone drop the USB link and re-enumerate "
            "(expected) - the tool reconnects automatically.")
        t, lines = mtp.enable_adb_via_at(t)
        ctx["target"] = t
        for ln in lines:
            log(ln)
        log("  if every vendor command printed ERROR, the phone is not in test "
            "mode - these commands are only honored inside test mode. Retry after "
            "entering test mode (*#0*# from the Emergency call dialer).")

        log("PHONE: an 'Allow USB debugging' dialog should appear - tap "
            "'Always allow' + OK. If it does not, unplug/replug the USB cable.")
        if not _wait_for_adb(ctx, log, timeout=90):
            raise RuntimeError(
                "no adb device appeared - tap 'Always allow' and re-plug the cable"
            )

        log("STEP 4/4: clear FRP flags over ADB")
        for label, cmd in ADB_STEPS:
            log(f"  > adb shell {cmd}")
            try:
                out = bridge.adb_shell(cmd, timeout=30)
            except bridge.BridgeError as e:
                out = f"ERROR: {e}"
            if out:
                log(f"      {out[:120]}")
            time.sleep(1.2)
        log("Done. Power-cycle the phone and complete setup normally.")

    steps = [Step("commercial_at_bypass", _run)]
    return Flow("bypass FRP (MTP/AT, commercial)", steps)


def flow_test_mode():
    """Commercial-style flow: emergency-dial *#0*# to enter Samsung test mode,
    which enables USB debugging automatically. Then automate ADB to bypass FRP.

    On-screen steps (the tool waits for ADB while you do these):
      1. On the setup / "Verify your account" screen tap the emergency-call icon.
      2. Dial  *#0*#   (no call button needed) -> test mode opens (tile grid).
      3. Plug the phone into the PC (stay in test mode).
      4. If an "Allow USB debugging" popup appears, tick 'Always allow' + OK.
    The tool then drives ADB to disable the setup wizard and mark FRP done.
    """

    ADB_STEPS = [
        ("disable Google setup wizard",
         "pm disable-user --user 0 com.google.android.setupwizard"),
        ("disable Samsung setup wizard",
         "pm disable-user --user 0 com.sec.android.app.SecSetupWizard"),
        ("clear setup wizard data",
         "pm clear com.google.android.setupwizard"),
        ("mark device provisioned",
         "settings put global device_provisioned 1"),
        ("mark setup complete",
         "settings put secure user_setup_complete 1"),
        ("back to home", "input keyevent 3"),
    ]

    def _run(ctx, log):
        log("PHONE: on the FRP screen tap Emergency call, dial *#0*# , "
            "then connect USB and allow USB debugging if prompted.")
        if not _wait_for_adb(ctx, log, timeout=90):
            raise RuntimeError(
                "no adb device appeared - is the phone in test mode "
                "(*#0*#) and did you tap 'Allow USB debugging'?"
            )
        for label, cmd in ADB_STEPS:
            log(f"  > adb shell {cmd}")
            try:
                out = bridge.adb_shell(cmd, timeout=30)
            except bridge.BridgeError as e:
                out = f"ERROR: {e}"
            if out:
                log(f"      {out[:120]}")
            time.sleep(1.5)
        log("Done. Power-cycle the phone and complete setup normally.")

    steps = [Step("test_mode_adb", _run)]
    return Flow("test mode (*#0*#) adb bypass", steps)


def flow_enable_adb():
    """Enable USB debugging (ADB) on a device that is locked out.

    Tries the MTP/AT method first (works on multi-config Samsung devices and
    pops the 'Allow USB debugging' dialog), else guides you through test mode
    (*#0*#), which turns USB debugging on automatically. Afterwards you can
    run 'screen lock remove' or 'read device info' in ADB mode.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("ENABLE USB DEBUGGING (ADB)")
        log("=" * 60)
        _try_enable_adb(ctx, log)
        log("")
        if not _wait_for_adb(ctx, log, timeout=90):
            raise RuntimeError("ADB still not available - see the instructions above")
        log("ADB is up and authorized. You can now run:")
        log("  - 'screen lock remove' -> ADB (locksettings)")
        log("  - 'read device info'   -> ADB")

    steps = [Step("enable_adb", _run)]
    return Flow("enable usb debugging (adb)", steps)


def flow_edl(detect_only=False):
    """EDL (Qualcomm Emergency Download) mode: detect a 9008 Sahara device and
    report what the EDL path can do for FRP (persist/EFS flag rewrite)."""

    EDL_IDS = [(0x05c6, 0x9008)]  # Qualcomm Sahara / EDL

    def _run(ctx, log):
        log("EDL mode selected (Qualcomm Emergency Download).")
        log("To enter EDL on a Qualcomm Samsung device:")
        log("  1. power the phone off (or `adb reboot edl` if adb is reachable)")
        log("  2. press Vol-Down + Home and plug USB, hold until the PC shows")
        log("     a Qualcomm device (05c6:9008)")
        found = None
        for _ in range(12):
            try:
                for d in bridge.detect_usb():
                    if (d.get("vid"), d.get("pid")) in EDL_IDS:
                        found = d
                        break
            except bridge.BridgeError:
                pass
            if found:
                break
            time.sleep(1.5)
        if found is None:
            raise RuntimeError(
                "no EDL device appeared - enter EDL mode on the phone first"
            )
        ctx["edl"] = found
        log(
            f"EDL device detected: {found['vid']:04x}:{found['pid']:04x} "
            f"bus={found['bus']} addr={found['address']}"
        )
        log("Sahara transport is available for partition access.")
        if not detect_only:
            log("NOTE: resetting FRP over EDL means rewriting the FRP flag in the "
                "persist/EFS area via Sahara/Firehose - not yet implemented here. "
                "MTP mode is the recommended working path.")

    steps = [Step("edl_mode", _run)]
    return Flow("edl mode", steps)


def flow_download_mode_frp():
    """Download-mode FRP bypass - REAL implementation: flashes a combination
    firmware with odin4 (the only way to get adb on a bootloader-locked phone),
    then clears FRP over adb."""

    def _run(ctx, log):
        log("=" * 60)
        log("FRP BYPASS - DOWNLOAD MODE (combination firmware + adb clear)")
        log("=" * 60)
        up = False
        try:
            up = any(d["state"] == "device" for d in bridge.adb_status())
        except bridge.BridgeError:
            pass
        if not up:
            log("No adb yet - flashing combination firmware to get adb ...")
            log("")
            if not _combo_flash_to_adb(ctx, log, purpose="FRP bypass"):
                raise RuntimeError(
                    "adb did not come up after the flash - see the notes above"
                )
        log("")
        log("Clearing FRP / finishing setup over adb ...")
        for label, cmd in _ADB_FRP_STEPS:
            log(f"  > adb shell {cmd}")
            try:
                out = bridge.adb_shell(cmd, timeout=30)
            except bridge.BridgeError as e:
                out = f"ERROR: {e}"
            if out:
                log(f"      {out[:120]}")
            time.sleep(1.2)
        log("")
        log("Done. Reboot the phone (adb reboot) - it should go straight to the")
        log("launcher, FRP gone.")

    steps = [Step("download_mode_frp_clear", _run)]
    return Flow("FRP clear (download mode - combo firmware + adb)", steps)


def flow_odin_enable_adb():
    """Enable ADB from download mode - REAL implementation.

    The only way to get adb on a bootloader-LOCKED phone is to flash a
    combination firmware (Samsung-signed test build with adb enabled) via
    odin4. Then this flow waits for adb to come online.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("ENABLE ADB - DOWNLOAD MODE (combination firmware via odin4)")
        log("=" * 60)
        up = False
        try:
            up = any(d["state"] == "device" for d in bridge.adb_status())
        except bridge.BridgeError:
            pass
        if up:
            log("adb is already online - nothing to do.")
            return
        if not _combo_flash_to_adb(ctx, log, purpose="enable adb"):
            raise RuntimeError(
                "adb did not come up after the flash - see the notes above"
            )
        log("")
        log("adb is online on the combination build.")
        log("NEXT: use 'FRP bypass' -> ADB, or 'Screen lock remove' -> ADB now.")

    steps = [Step("enable_adb_combo", _run)]
    return Flow("enable adb (download mode - combo firmware)", steps)


# SHA-256 of the known-good bundled Samsung odin4 Linux binary (root/tools/odin4).
# odin4 is a leaked proprietary binary fetched from public mirrors, so every
# execution is gated on this digest: a binary that does not match it (or is not
# explicitly trusted via ODIN4_SKIP_HASH=1) is refused before it can talk to a
# phone. Keep this in sync with scripts/fetch-odin4.sh.
ODIN4_SHA256 = "a35199f8a3f1b07c79eaf1f0f675e94f45a5edc9e75c79a1e45b01d423ac9644"
# Second known-good odin4 build (2022, 6754aa54). The a35199f8 build cannot
# handshake with MediaTek Samsung download agents (A05/A06/A14 5G), which the
# 2022 build handles fine - so the tool accepts both.
ODIN4_SHA256_MTK = "6754aa54f2abe6e99ece32414cd34c8b23b28dbddde537a33203036813637c3b"
ODIN4_SHA256S = (ODIN4_SHA256, ODIN4_SHA256_MTK)


def _odin4_hash_ok(path):
    """True if `path` is one of the known-good odin4 builds (by SHA-256), or the
    user has explicitly trusted an alternate binary with ODIN4_SKIP_HASH=1."""
    if os.environ.get("ODIN4_SKIP_HASH", "0").strip().lower() in ("1", "true", "yes", "on"):
        return True
    try:
        with open(path, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return False
    return digest in ODIN4_SHA256S


def _verified_odin4(path):
    """Return `path` once it passes the odin4 integrity check, else raise.

    This binary is about to be executed with direct access to the phone's
    storage, so a checksum failure is fatal unless the user opts out."""
    if _odin4_hash_ok(path):
        return path
    raise RuntimeError(
        f"odin4 binary at {path} failed SHA-256 verification "
        f"(expected one of: {', '.join(h[:16] for h in ODIN4_SHA256S)}). Refusing to "
        f"execute it. Re-run scripts/fetch-odin4.sh to restore a known-good binary, "
        f"or set ODIN4_SKIP_HASH=1 to trust this copy explicitly."
    )


def _find_odin4():
    """Locate and verify the leaked Samsung Odin v4 for Linux binary (odin4/odin).

    The located binary is verified against ODIN4_SHA256 before it is returned;
    an unverifiable binary raises instead of silently running."""
    env = os.environ.get("ODIN4_BIN")
    if env and os.path.isfile(env):
        return _verified_odin4(env)
    exe = shutil.which("odin4") or shutil.which("odin")
    if exe:
        return _verified_odin4(exe)
    # bundled copy ships inside the repo (root/tools/odin4)
    bundled = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "root", "tools", "odin4",
    )
    if os.path.isfile(bundled) and os.access(bundled, os.X_OK):
        return _verified_odin4(bundled)
    for cand in (
        "/usr/local/bin/odin4", "/usr/local/bin/odin",
        "/usr/bin/odin4", "/usr/bin/odin",
        os.path.expanduser("~/odin4"), os.path.expanduser("~/odin"),
        os.path.expanduser("~/bin/odin4"), os.path.expanduser("~/bin/odin"),
        os.path.expanduser("~/.local/bin/odin4"),
        os.path.expanduser("~/Downloads/ABDM/Compressed/odin/odin4"),
    ):
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return _verified_odin4(cand)
    return ""


def _odin4_allow_unknown():
    """Return ['--allow-unknown'] only when explicitly enabled (ODIN4_ALLOW_UNKNOWN=1).

    odin4's default PIT check aborts the flash ('check failure pit') when any
    archive entry has no matching partition in the device PIT. That check is the
    guard that stops mismatched firmware from being written, so it stays ON
    unless the user explicitly opts out via the GUI checkbox or the env var."""
    if os.environ.get("ODIN4_ALLOW_UNKNOWN", "0").strip().lower() in ("1", "true", "yes", "on"):
        return ["--allow-unknown"]
    return []


def _odin4_reboot():
    """Return ['--reboot'] only when explicitly requested (ODIN4_REBOOT=1).

    Rebooting automatically after a flash hides a failed write behind a phone
    that no longer answers, so it is off unless the user opts in."""
    if os.environ.get("ODIN4_REBOOT", "0").strip().lower() in ("1", "true", "yes", "on"):
        return ["--reboot"]
    return []


def _odin4_redownload():
    """Return ['--redownload'] only when explicitly requested (ODIN4_REDOWNLOAD=1).

    odin4 sends the Redownload command after flashing so the phone re-enters
    download mode instead of rebooting - the reliable way to chain a second
    flash (e.g. an NVRAM erase) without physically rebooting the phone."""
    if os.environ.get("ODIN4_REDOWNLOAD", "0").strip().lower() in ("1", "true", "yes", "on"):
        return ["--redownload"]
    return []


def _odin4_verbose():
    """Return ['--verbose'] only when explicitly requested (ODIN4_VERBOSE=1)."""
    if os.environ.get("ODIN4_VERBOSE", "0").strip().lower() in ("1", "true", "yes", "on"):
        return ["--verbose"]
    return []


def _reboot_redownload_flags(log):
    """Resolve the mutually-exclusive --reboot / --redownload flags into a list."""
    reboot = _odin4_reboot()
    redownload = _odin4_redownload()
    if reboot and redownload:
        raise RuntimeError(
            "'Auto-reboot' and 'Re-download' are mutually exclusive - enable only one."
        )
    flags = reboot or redownload
    if not flags:
        log("  Auto-reboot DISABLED (opt-in). The phone will stay in download mode -")
        log("  verify the flash finished before manually rebooting.")
    elif "--redownload" in flags:
        log("  Re-download enabled: the phone will re-enter download mode after flashing.")
    return flags


def _explain_odin4_failure(out):
    """Return a short user-facing explanation of a common odin4 check failure."""
    out_l = out.lower()
    if "does not match any pit partition" in out_l:
        return ("An archive partition has no match in the device's PIT (check failure pit). "
                "Enable 'Allow unknown partitions' in the GUI, or pass --allow-unknown.")
    if "firmware file name does not appear to match device type" in out_l:
        return ("The firmware archive name does not match the device model. Rename the .tar file "
                "to include the device model (e.g. AP_A145P_... .tar) or use the exact model firmware.")
    if "multiple entries for the same pit partition" in out_l:
        return ("The archive contains two files mapped to the same PIT partition. "
                "Remove the duplicate entry from the archive.")
    if "md5 verification failed" in out_l or "invalid md5 trailer" in out_l:
        return ("Firmware checksum (md5) mismatch - the .tar.md5 file is corrupt or was renamed "
                "after download. Re-download the firmware.")
    if "handshake failed" in out_l or "bulk read timed out" in out_l or "timed out" in out_l:
        return ("USB transfer failed - the cdc_acm kernel module often breaks Odin bulk transfers. "
                "Run `sudo rmmod cdc_acm` and retry.")
    if "bootloader fail" in out_l:
        return ("The device bootloader rejected a partition (BOOTLOADER_FAIL). "
                "A partition is too large, unauthorized, or the archive/PIT mismatch remains.")
    return ""


def _find_firmware_tar():
    """Locate any Odin firmware tar (AP_*.tar / *.tar / *.tar.md5). With
    ODIN4_EXACT_SLOTS set (GUI-triggered), only FIRMWARE_TAR is honored."""
    env = os.environ.get("FIRMWARE_TAR")
    if env and os.path.isfile(env):
        return env
    if _env_flag("ODIN4_EXACT_SLOTS"):
        return ""
    dirs = [os.path.expanduser("~/Downloads"), os.path.expanduser("~"), os.getcwd()]
    for d in dirs:
        if not os.path.isdir(d):
            continue
        cands = sorted(
            glob.glob(os.path.join(d, "*.tar*")) + glob.glob(os.path.join(d, "AP_*.tar*")),
            key=os.path.getmtime, reverse=True,
        )
        if cands:
            return cands[0]
    return ""


def flow_odin_flash_tar():
    """Flash any Samsung firmware .tar / .tar.md5 archive using odin4."""
    def _run(ctx, log):
        log("=" * 60)
        log("ODIN FLASHING - FIRMWARE ARCHIVE (.tar / .tar.md5)")
        log("=" * 60)
        odin4 = _find_odin4()
        if not odin4:
            raise RuntimeError("odin4 binary not found. Place odin4 in the repo root/tools/ folder or on PATH.")
        
        tar = _find_firmware_tar()
        if not tar:
            raise RuntimeError("No firmware .tar / .tar.md5 file found in ~/Downloads or current directory.")
        
        d = _download_mode_device()
        if not d:
            log("Waiting for device in download mode (04e8:685d)...")
            d = _wait_download_mode(log, timeout=30)
        if not d:
            raise RuntimeError("Device not in download mode. Hold Vol Down + Power, then Vol Up.")
        
        log(f"odin4: {odin4}")
        log(f"archive: {tar} ({os.path.getsize(tar) >> 20} MB)")

        log("")
        log("Running safety checks before flashing...")
        _require_preflight(ctx, log)
        _require_recent_efs_backup(ctx, log)
        _enforce_flash_gates(ctx, log, d)

        if _env_flag("ODIN4_CHECK_ONLY"):
            _run_odin4_check_only(log, odin4, {"AP": tar})

        log("Flashing firmware via odin4... DO NOT unplug!")
        tar = _strip_odin4_md5_trailer(tar)
        cmd = [odin4, "-a", tar, *_odin4_allow_unknown()]
        cmd.extend(_reboot_redownload_flags(log))
        cmd.extend(_odin4_verbose())
        if _env_flag("ODIN4_ERASE_NV") and "--reboot" in cmd:
            raise RuntimeError(
                "'Erase NVRAM' runs after the flash and needs the phone to stay in "
                "download mode - disable Auto-reboot (or enable Re-download) and retry."
            )
        log("> " + " ".join(cmd))
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
        out = (proc.stdout or "") + (proc.stderr or "")
        if out:
            log(out[-3000:])
        if proc.returncode != 0:
            hint = _explain_odin4_failure(out)
            raise RuntimeError(f"odin4 flashing failed (rc={proc.returncode}). {hint}")
        log("Firmware flashed successfully!")
        if _env_flag("ODIN4_ERASE_NV"):
            _erase_nvram(ctx, log, d)
        if "--reboot" in cmd:
            log("  Device is rebooting.")
        elif "--redownload" in cmd:
            log("  Device re-entering download mode - ready for the next step.")
        else:
            log("  Device stays in download mode - power off / reboot manually when ready.")
        return True

    return Flow("Flash firmware tar (odin4)", [Step("odin_flash_tar", _run)])


def flow_odin_check():
    """Validate firmware archive and PIT using odin4 --check-only. Checks the
    slots selected in the GUI (AP_TAR/BL_TAR/... env) or any tar in
    ~/Downloads as a fallback."""
    def _run(ctx, log):
        odin4 = _find_odin4()
        if not odin4:
            raise RuntimeError("odin4 binary not found.")
        archives = {
            "AP": _find_slot_tar("AP"),
            "BL": _find_slot_tar("BL"),
            "CP": _find_slot_tar("CP"),
            "CSC": _find_slot_tar("CSC") or _find_slot_tar("HOME_CSC"),
            "USERDATA": _find_slot_tar("USERDATA"),
        }
        selected = {k: v for k, v in archives.items() if v}
        if not selected:
            tar = _find_firmware_tar()
            if not tar:
                raise RuntimeError("No firmware tar found.")
            selected = {"AP": tar}
        log("Checking selected firmware with odin4 --check-only (no write)...")
        for k, v in selected.items():
            log(f"  [{k}]  {os.path.basename(v)}")
        _run_odin4_check_only(log, odin4, archives)
        log("Firmware archive and PIT structure are valid.")
        return True

    return Flow("Check firmware archive (odin4)", [Step("odin_check", _run)])


def flow_odin_list():
    """List detected download mode devices using odin4 -l."""
    def _run(ctx, log):
        odin4 = _find_odin4()
        if not odin4:
            raise RuntimeError("odin4 binary not found.")
        cmd = [odin4, "-l"]
        log("> " + " ".join(cmd))
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        log((proc.stdout or "") + (proc.stderr or ""))
        return True

    return Flow("List download devices (odin4)", [Step("odin_list", _run)])


def _find_slot_tar(prefix):
    """Locate a slot tar (AP_*, BL_*, CP_*, CSC_*, HOME_CSC_*, USERDATA_*).
    When ODIN4_EXACT_SLOTS is set (GUI-triggered flash), only the path
    explicitly chosen in the GUI is accepted - the ~/Downloads auto-discovery
    fallback is disabled so an empty slot can never silently grab a file the
    user did not select."""
    env = os.environ.get(f"{prefix}_TAR")
    if env and os.path.isfile(env):
        return env
    if _env_flag("ODIN4_EXACT_SLOTS"):
        return ""
    dirs = [os.path.expanduser("~/Downloads"), os.path.expanduser("~"), os.getcwd()]
    for d in dirs:
        if not os.path.isdir(d):
            continue
        cands = sorted(
            glob.glob(os.path.join(d, f"{prefix}*.tar*")),
            key=os.path.getmtime, reverse=True,
        )
        if cands:
            return cands[0]
    return ""


def get_tar_contents(tar_path):
    """List files inside an Odin firmware tar archive without extracting."""
    try:
        with tarfile.open(tar_path, 'r:*') as tf:
            return [m.name for m in tf.getmembers() if m.isfile()]
    except Exception:
        return []


def _lz4_decompress(data):
    """Decompress an LZ4 frame. Uses the system lz4 binary if present, else a
    minimal pure-python fallback for the common Samsung block-format LZ4."""
    try:
        exe = shutil.which("lz4")
        if exe:
            proc = subprocess.run([exe, "-d", "-c"], input=data, capture_output=True, timeout=120)
            if proc.returncode == 0 and proc.stdout:
                return proc.stdout
    except Exception:
        pass
    try:
        import lz4.frame
        return lz4.frame.decompress(data)
    except Exception:
        pass
    # Minimal block-format fallback (Samsung `.img.lz4` are often legacy blocks)
    try:
        import lz4.block
        if data[:4] == b"\x02\x21\x4c\x18":  # legacy magic
            return lz4.block.decompress(data[4:])
        return lz4.frame.decompress(data)
    except Exception:
        raise RuntimeError(
            "Could not decompress LZ4 data. Install `lz4` (apt install liblz4-tool) "
            "or `python3-lz4`."
        )


def _patch_vbmeta_flags(data, flags=0x03):
    """Patch the AVB (vbmeta.img) flags field to disable verification (0x03 =
    HASHTREE_DISABLED | VERIFICATION_DISABLED). Returns patched bytes or None."""
    if len(data) < 96 or data[:4] != b"AVB0":
        return None
    flags_off = 80
    if len(data) < flags_off + 4:
        return None
    patched = bytearray(data)
    struct.pack_into("<I", patched, flags_off, flags)
    return bytes(patched)


def flow_odin_advanced_flash():
    """Advanced Odin flashing: supports AP, BL, CP, CSC, Userdata slots,
    auto-reboot, and --allow-unknown (bypasses PIT mismatch / partition errors
    and allows unofficial/custom firmwares), operating directly on tar/lz4 archives without manual extraction."""
    def _run(ctx, log):
        log("=" * 60)
        log("ODIN ADVANCED FLASHING (AP, BL, CP, CSC, Userdata & Unofficial)")
        log("=" * 60)
        odin4 = _find_odin4()
        if not odin4:
            raise RuntimeError("odin4 binary not found. Place odin4 in the repo root/tools/ folder or on PATH.")
        
        d = _download_mode_device()
        if not d:
            log("Waiting for device in download mode (04e8:685d)...")
            d = _wait_download_mode(log, timeout=30)
        if not d:
            raise RuntimeError("Device not in download mode. Hold Vol Down + Power, then Vol Up.")

        # Detach cdc_acm / kernel drivers - fixes 'bulk read timed out'.
        target = f"04e8:{d['pid']:04x}@{d['bus']}:{d['address']}"
        try:
            res = bridge.usb_detach_kernel(target, timeout=15)
            log(f"  Kernel drivers detached: {res.get('detached')}")
        except bridge.BridgeError as e:
            log(f"  (kernel detach skipped: {e})")

        ap = _find_slot_tar("AP")
        if not ap and not _env_flag("ODIN4_EXACT_SLOTS"):
            ap = _find_firmware_tar()
        bl = _find_slot_tar("BL")
        cp = _find_slot_tar("CP")
        csc = _find_slot_tar("CSC") or _find_slot_tar("HOME_CSC")
        userdata = _find_slot_tar("USERDATA")

        if not ap and not bl and not cp and not csc:
            raise RuntimeError("No firmware slot archives (AP, BL, CP, CSC) found in ~/Downloads or current directory.")

        log("")
        log("Running safety checks before flashing...")
        _require_preflight(ctx, log)
        _require_recent_efs_backup(ctx, log)
        _enforce_flash_gates(ctx, log, d)

        if _env_flag("ODIN4_CHECK_ONLY"):
            _run_odin4_check_only(log, odin4, {
                "AP": ap, "BL": bl, "CP": cp, "CSC": csc, "USERDATA": userdata,
            })

        cmd = [odin4]
        for slot_key, slot_path, opt in [
            ("AP", ap, "-a"),
            ("BL", bl, "-b"),
            ("CP", cp, "-c"),
            ("CSC", csc, "-s"),
            ("USERDATA", userdata, "-u"),
        ]:
            if slot_path:
                log(f"  [{slot_key}]   {os.path.basename(slot_path)} ({os.path.getsize(slot_path) >> 20} MB)")
                files = get_tar_contents(slot_path)
                if files:
                    log(f"         Partitions inside: {', '.join(files[:8])}{' ...' if len(files) > 8 else ''}")
                cmd.extend([opt, slot_path])

        # Advanced flags
        cmd.extend(_odin4_allow_unknown())
        cmd.extend(_reboot_redownload_flags(log))
        cmd.extend(_odin4_verbose())
        if _env_flag("ODIN4_ERASE_NV") and "--reboot" in cmd:
            raise RuntimeError(
                "'Erase NVRAM' runs after the flash and needs the phone to stay in "
                "download mode - disable Auto-reboot (or enable Re-download) and retry."
            )
        if "--allow-unknown" in cmd:
            log("  [PIT check bypass enabled] archive entries without a device PIT match")
            log("  will be skipped instead of aborting ('check failure pit').")

        log("")
        log(f"Executing: {' '.join(cmd)}")
        log("Flashing in progress... DO NOT disconnect cable!")

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        out = (proc.stdout or "") + (proc.stderr or "")
        if out:
            log(out[-3500:])
        if proc.returncode != 0:
            hint = _explain_odin4_failure(out)
            raise RuntimeError(f"Advanced flash failed (rc={proc.returncode}). {hint}")
        log("Advanced flash completed successfully!")
        if _env_flag("ODIN4_ERASE_NV"):
            _erase_nvram(ctx, log, d)
        if "--reboot" in cmd:
            log("  Device is rebooting.")
        elif "--redownload" in cmd:
            log("  Device re-entering download mode - ready for the next step.")
        else:
            log("  Device stays in download mode - power off / reboot manually when ready.")
        return True

    return Flow("Advanced flash (AP/BL/CP/CSC + Unofficial)", [Step("odin_advanced_flash", _run)])


# ---------------------------------------------------------------------------
# Advanced flashing helpers (PIT parsing, verification, USB stability)
# ---------------------------------------------------------------------------

# Samsung .tar.md5 trailer: <32-hex md5> + spaces + <filename> + optional \n.
_MD5_TRAILER_RE = re.compile(rb"([0-9a-fA-F]{32})[ \t]+([^\r\n]+)\r?\n?$")


def _tar_md5_valid(tar_path):
    """Verify a .tar.md5 archive's embedded md5 checksum. Returns (ok, msg).
    Samsung .tar.md5 trailers follow md5sum output: <32-hex>  <filename>\n
    (two spaces and a trailing newline are both legal)."""
    if not str(tar_path).lower().endswith(".md5"):
        return True, "not a .md5 archive, skipping checksum"
    import hashlib
    try:
        # The trailer is the last ~40 bytes; the body is everything before it.
        # Stream the body through hashlib in chunks instead of reading the whole
        # archive into RAM - a Samsung AP tar can be 5-10 GB and a full read
        # exhausts memory (system freeze / OOM-killed app).
        trailer_len = 1024
        with open(tar_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            fsize = f.tell()
            if fsize < 33:
                return False, "file too small"
            win = min(trailer_len, fsize)
            f.seek(-win, os.SEEK_END)
            tail = f.read(win)
            f.seek(0)
            m = _MD5_TRAILER_RE.search(tail)
            if not m:
                return False, "no embedded md5 trailer"
            expected = m.group(1)
            body_len = fsize - win + m.start(1)
            hasher = hashlib.md5()
            remaining = body_len
            while remaining > 0:
                chunk = f.read(min(1 << 20, remaining))
                if not chunk:
                    break
                hasher.update(chunk)
                remaining -= len(chunk)
        actual = hasher.hexdigest().encode()
        if actual.lower() != expected.lower():
            return False, (
                f"checksum mismatch ({actual.decode()[:8]}... vs "
                f"{expected.decode()[:8]}...)"
            )
        return True, "checksum OK"
    except Exception as e:
        return False, f"could not verify: {e}"


def _strip_odin4_md5_trailer(tar):
    """Return a path odin4 can safely consume for a .tar.md5 archive.

    Official Samsung tars use a '<md5>  <name>\\n' trailer (two spaces and a
    trailing newline). odin4's own md5 parser mis-reads this variant and aborts
    with 'MD5 verification failed' even though the checksum is valid (we verify
    it ourselves first via _tar_md5_valid). For such archives, return a
    trailer-free '.tar' copy cached under ~/flashpilot/odin4_cache so odin4 skips
    its broken md5 path. Plain .tar files are returned unchanged."""
    if not str(tar).lower().endswith(".md5"):
        return tar
    try:
        with open(tar, "rb") as f:
            f.seek(0, os.SEEK_END)
            fsize = f.tell()
            f.seek(-min(1024, fsize), os.SEEK_END)
            tail = f.read(1024)
        m = _MD5_TRAILER_RE.search(tail)
        if not m:
            return tar
        body_len = fsize - len(tail) + m.start(1)
    except OSError:
        return tar
    cache = os.path.expanduser("~/flashpilot/odin4_cache")
    os.makedirs(cache, exist_ok=True)
    out = os.path.join(cache, os.path.basename(tar)[: -len(".md5")])
    if not os.path.isfile(out) or os.path.getsize(out) != body_len:
        with open(tar, "rb") as src, open(out, "wb") as dst:
            remaining = body_len
            while remaining > 0:
                chunk = src.read(min(1 << 20, remaining))
                if not chunk:
                    break
                dst.write(chunk)
                remaining -= len(chunk)
    return out


def _bl_rev_from_name(name):
    """Extract the bootloader binary version from a firmware filename.

    Samsung's authoritative bootloader revision is the digit in the build ID
    ('A145PXXU1AWC1' -> binary 1). The '_REVxx_user_low_ship' label in the
    filename is a package label that can disagree (the AWC1 factory build is
    labeled '_REV00_' yet carries binary 1). Prefer the build-ID digit, then
    fall back to the '_REVxx_' label."""
    m = re.search(r"(?:U|S)(\d)", name)
    if m:
        return int(m.group(1))
    m = re.search(r"_REV(\d{2})_", name)
    return int(m.group(1)) if m else None


_MODEL_TOKEN_RE = re.compile(r"(?:SM-)?[A-Z]\d{3}[A-Z]")


def _model_from_firmware_name(name):
    """Extract the device model from a Samsung firmware filename (e.g. SM-A145P).
    Handles 'AP_SM-A145P_...' and the no-SM-prefix convention used by real
    archives ('AP_A145PXXSCDZE3_...', 'CSC_OJM_A145POJMCDZE3_...' -> 'A145P').
    The token requires a trailing LETTER, so sloppy substrings like 'B1102'
    (inside MQB110285214) never match."""
    m = _MODEL_TOKEN_RE.search(name)
    return m.group(0) if m else ""


def _is_device_model(s):
    """True when a string is a recognizable device model (A145P, SM-A145P).
    Combo PIT labels like 'COM_TAR2MTK6765' are not device models."""
    n = _normalize_model(s)
    return bool(re.match(r"^[A-Z]\d{3}[A-Z0-9]$", n))


def _models_match(a, b):
    """Compare two model strings. Returns True/False when both are recognizable
    device models, None when either side is unverifiable (e.g. a combo PIT
    header label like 'COM_TAR2MTK6765')."""
    if not a or not b:
        return None
    na, nb = _normalize_model(a), _normalize_model(b)
    if not _is_device_model(na) or not _is_device_model(nb):
        return None
    return na == nb


def _parse_pit_from_tar(tar_path):
    """Extract a .pit file from a firmware tar and parse its entries."""
    try:
        with tarfile.open(tar_path, "r:*") as tf:
            for member in tf.getmembers():
                if member.isfile() and member.name.lower().endswith(".pit"):
                    raw = tf.extractfile(member).read()
                    entries = pit.parse_pit(raw)
                    return entries, pit.parse_model(raw)
    except Exception:
        pass
    return None, None


def _check_cdc_acm(log):
    """Warn and attempt to remove the cdc_acm kernel module which breaks Odin
    bulk transfers on some Linux setups. Tries `sudo rmmod cdc_acm` if sudo is
    passwordless, otherwise gives the command."""
    try:
        out = subprocess.run(["lsmod"], capture_output=True, text=True, timeout=5)
        if "cdc_acm" not in (out.stdout or ""):
            return
    except Exception:
        return
    log("  NOTE: the cdc_acm kernel module is loaded and can break Odin bulk")
    log("  transfers ('bulk read timed out').")
    try:
        proc = subprocess.run(
            ["sudo", "-n", "rmmod", "cdc_acm"],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode == 0:
            log("  cdc_acm removed automatically (USB stability improved).")
        else:
            log("  Run in a terminal to remove it: `sudo rmmod cdc_acm`")
    except Exception:
        log("  Run in a terminal to remove it: `sudo rmmod cdc_acm`")


def _verify_archives(log, archive_dict):
    """Verify integrity of a {slot: path} mapping. Returns True if all ok."""
    all_ok = True
    for slot, path in archive_dict.items():
        if not path:
            continue
        ok, msg = _tar_md5_valid(path)
        log(f"  [{slot}] {os.path.basename(path)} -> {msg}")
        if not ok:
            all_ok = False
    return all_ok


def _detect_mode(samsung):
    """Classify a Samsung device's current USB mode (download / recovery / adb)."""
    pids = {d.get("pid") for d in samsung}
    if 0x685d in pids:
        return "DOWNLOAD MODE"
    if 0x4eef in pids or 0x4eee in pids:
        return "RECOVERY"
    if 0x685c in pids:
        return "BROM"
    return "NORMAL"


def _normalize_model(s):
    """Canonical form of a Samsung model string for comparison: strips the
    SM- prefix and any punctuation, upper-cases. 'SM-A145P' == 'a145p'."""
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper().replace("SM-", "").replace("SM_", ""))


def _bl_rev_from_bootloader(value):
    """Best-effort parse of the Samsung SW-revision digit out of a bootloader
    version string (ro.bootloader). e.g. 'A145PXXU1BWB1' -> 1. Returns int/None."""
    m = re.search(r"U(\d)", value or "")
    return int(m.group(1)) if m else None


def _get_device_bl_rev(ctx, log):
    """Try to learn the device's current bootloader revision: prefers a value
    already discovered (ctx['bl_rev']), then a live ADB read of ro.bootloader
    (best-effort, requires a booted + authorized device). Returns int or None."""
    val = ctx.get("bl_rev")
    if val is not None:
        return int(val) if str(val).isdigit() else None
    try:
        out = bridge.adb_shell("getprop ro.bootloader", timeout=10).strip()
    except Exception:
        return None
    rev = _bl_rev_from_bootloader(out)
    if rev is not None:
        log(f"  Device bootloader rev (ro.bootloader '{out}'): REV{rev}")
        ctx["bl_rev"] = rev
    return rev


def _enforce_flash_gates(ctx, log, d):
    """Hard safety gates before an odin4 flash.

    - Firmware model (from the archive name) must match the device model read
      over the Odin protocol; a mismatch blocks the flash.
    - A BL archive must not be a lower bootloader revision than the device's.

    The device model is taken from ctx['device_model'] (set by an ADB read or a
    booted device) - NOT from a live Odin session probe: MediaTek download
    agents (A05/A06/A14 5G) only tolerate one session per plug-in and any probe
    before odin4 wedges the agent for the actual flash.

    Both gates can be overridden explicitly (ODIN4_FORCE_MODEL=1 /
    ODIN4_FORCE_BL=1) - overrides log a prominent warning first."""
    target = f"04e8:{d['pid']:04x}@{d['bus']}:{d['address']}"

    fw = _find_slot_tar("AP") or _find_firmware_tar()
    fw_model = _model_from_firmware_name(os.path.basename(fw)) if fw else ""
    dev_model = ctx.get("device_model", "") or ""

    if dev_model and not _is_device_model(dev_model):
        # Combo/MTK labels ('COM_TAR2MTK6765') or partial reads are not device
        # models - treat them as unreadable and skip the model gate.
        log(f"  (device model '{dev_model}' is not a device model - model gate skipped)")
        dev_model = ""

    if fw_model and dev_model:
        if _normalize_model(fw_model) == _normalize_model(dev_model):
            log(f"  Model check: firmware '{fw_model}' vs device '{dev_model}' - MATCH")
        elif os.environ.get("ODIN4_FORCE_MODEL", "0").strip().lower() in ("1", "true", "yes", "on"):
            log(f"  !!! MODEL MISMATCH OVERRIDDEN (ODIN4_FORCE_MODEL=1): firmware "
                f"'{fw_model}' vs device '{dev_model}' - proceeding at your own risk.")
        else:
            raise RuntimeError(
                f"MODEL MISMATCH: firmware targets '{fw_model}' but the device is "
                f"'{dev_model}'. Flashing mismatched firmware can hard-brick the "
                f"device. Use the exact model's firmware, or set "
                f"ODIN4_FORCE_MODEL=1 to proceed anyway."
            )
    elif fw_model:
        log(f"  Model check: firmware '{fw_model}' (device model unavailable - skipped)")

    bl = _find_slot_tar("BL")
    if bl:
        fw_rev = _bl_rev_from_name(os.path.basename(bl))
        dev_rev = _get_device_bl_rev(ctx, log)
        if fw_rev is not None and dev_rev is not None:
            if fw_rev >= dev_rev:
                log(f"  BL check: REV{fw_rev:02d} >= device REV{dev_rev:02d} - OK")
            elif os.environ.get("ODIN4_FORCE_BL", "0").strip().lower() in ("1", "true", "yes", "on"):
                log(f"  !!! BL DOWNGRADE OVERRIDDEN (ODIN4_FORCE_BL=1): flashing REV{fw_rev:02d} "
                    f"on a REV{dev_rev:02d} device - at your own risk.")
            else:
                raise RuntimeError(
                    f"BLOCKED: firmware BL REV{fw_rev:02d} is LOWER than the device's "
                    f"REV{dev_rev:02d}. Flashing a lower bootloader revision can "
                    f"hard-brick the device. Use a newer firmware, remove the BL "
                    f"slot, or set ODIN4_FORCE_BL=1 to proceed anyway."
                )
        elif fw_rev is not None:
            log(f"  BL revision: REV{fw_rev:02d} (device rev unknown - downgrade check skipped)")


def _enforce_bl_downgrade_gate(ctx, log, specs):
    """BL revision downgrade gate for the native multi-partition flash.

    If any flashed image targets a bootloader (BL) partition whose firmware
    name carries a LOWER bootloader revision than the device's current one,
    refuse unless ODIN4_FORCE_BL=1 (logged with a prominent warning first).
    Flashing a lower BL revision on a newer device can hard-brick it."""
    bl = next((img for name, img in specs if name in ("bootloader", "lk", "param")), None)
    if not bl:
        return
    fw_rev = _bl_rev_from_name(os.path.basename(bl))
    dev_rev = _get_device_bl_rev(ctx, log)
    if fw_rev is None or dev_rev is None:
        return
    if fw_rev >= dev_rev:
        log(f"  BL check: REV{fw_rev:02d} >= device REV{dev_rev:02d} - OK")
        return
    if _env_flag("ODIN4_FORCE_BL"):
        log(f"  !!! BL DOWNGRADE OVERRIDDEN (ODIN4_FORCE_BL=1): flashing REV{fw_rev:02d} "
            f"on a REV{dev_rev:02d} device - at your own risk.")
        return
    raise RuntimeError(
        f"BLOCKED: flashed BL REV{fw_rev:02d} is LOWER than the device's "
        f"REV{dev_rev:02d}. Flashing a lower bootloader revision can hard-brick "
        f"the device. Use newer firmware or set ODIN4_FORCE_BL=1 to proceed anyway."
    )


def _require_preflight(ctx, log):
    """Run the pre-flight validation suite as a hard gate before flashing.
    Raises on any failed check (corrupt archive, cross-slot model mismatch)."""
    flow_preflight().steps[0].run(ctx, log)


def _require_recent_efs_backup(ctx, log, max_age_days=30):
    """Require a recent EFS backup before flashing. If a booted, authorized ADB
    device is present, backs EFS up automatically; otherwise accepts a backup
    made within the last `max_age_days` days. Can be skipped explicitly
    (ODIN4_SKIP_BACKUP=1)."""
    if os.environ.get("ODIN4_SKIP_BACKUP", "0").strip().lower() in ("1", "true", "yes", "on"):
        log("  SKIPPING EFS backup requirement (ODIN4_SKIP_BACKUP=1).")
        return
    backup_dir = os.path.expanduser("~/flashpilot/efs_backups")
    cands = []
    if os.path.isdir(backup_dir):
        cands = sorted(
            glob.glob(os.path.join(backup_dir, "efs_*.tar")),
            key=os.path.getmtime, reverse=True,
        )
    if cands:
        age_days = (time.time() - os.path.getmtime(cands[0])) / 86400
        if age_days <= max_age_days:
            log(f"  Recent EFS backup found: {os.path.basename(cands[0])} ({age_days:.0f}d old)")
            ctx["efs_backup"] = cands[0]
            return
        log(f"  EFS backup too old ({age_days:.0f}d) - re-backing up if possible...")
    try:
        if any(d.get("state") == "device" for d in bridge.adb_status()):
            log("  Attempting automatic EFS backup via ADB before flashing...")
            flow_efs_backup().steps[0].run(ctx, log)
            return
    except Exception:
        pass
    raise RuntimeError(
        "No recent EFS backup found. Before flashing, boot the phone normally, "
        "connect with USB debugging, and run the EFS backup flow (or set "
        "ODIN4_SKIP_BACKUP=1 to skip - NOT recommended)."
    )


def _is_nv_partition(name):
    """True when a PIT partition is an NVRAM/NVDATA (network calibration)
    partition. Matches the well-known Samsung MediaTek names (nvram, nvdata,
    nvcfg, nvbackup, ...) by the 'nv' prefix, bounded so 'vendor' etc. never
    match."""
    n = (name or "").strip().lower()
    return n in ("nvram", "nvdata") or (n.startswith("nv") and 3 <= len(n) <= 12)


def _write_zeroes(f, size, chunk=1 << 20):
    """Write exactly `size` zero bytes to the open binary file `f`, streaming
    in `chunk`-sized blocks so huge partitions never get buffered in memory."""
    block = b"\0" * chunk
    remaining = size
    while remaining > 0:
        n = chunk if remaining >= chunk else remaining
        f.write(block[:n])
        remaining -= n


def _erase_nvram(ctx, log, d):
    """Zero-fill every NVRAM/NVDATA partition listed in the device's own PIT.

    Uses the native Odin flash path (odin-flash) with the device-dumped PIT, so
    on Odin-protocol (Exynos/Qualcomm download mode) devices this reliably
    wipes the network-calibration area - the standard fix for IMEI/network and
    a common FRP-adjacent step. MTK download-agent devices do not answer the
    ODIN handshake, so they must use the MediaTek workbench instead."""
    target = f"04e8:{d['pid']:04x}@{d['bus']}:{d['address']}"
    with tempfile.TemporaryDirectory(prefix="nv_erase_") as td:
        pit_path = os.path.join(td, "device.pit")
        bridge.odin_pit(target, pit_path, timeout=120)
        with open(pit_path, "rb") as pf:
            entries = pit.parse_pit(pf.read())
        names = sorted({e.name for e in entries if _is_nv_partition(e.name)})
        if not names:
            log("  No NVRAM/NVDATA partitions in the device PIT - nothing to erase.")
            return
        log(f"  Erasing NVRAM/NVDATA: {', '.join(names)}")
        for name in names:
            entry = next(e for e in entries if e.name == name)
            size = entry.size_bytes()
            log(f"    {name}: {size >> 20} MB -> zero-fill via native Odin flash...")
            img = os.path.join(td, f"{name}.img")
            with open(img, "wb") as f:
                _write_zeroes(f, size)
            res = bridge._run(["odin-flash", target, pit_path, name, img], timeout=1800)
            log(f"    {res}")
        log("  NVRAM erase complete.")


def _run_odin4_check_only(log, odin4, archives):
    """Validate firmware archives with odin4 --check-only before flashing.
    Raises on any failure so a corrupt/mismatched archive is never flashed."""
    log("  Pre-flash validation (odin4 --check-only)...")
    cmd = [odin4, "--check-only", *_odin4_allow_unknown()]
    for opt, path in (("-a", archives.get("AP")), ("-b", archives.get("BL")),
                      ("-c", archives.get("CP")), ("-s", archives.get("CSC")),
                      ("-u", archives.get("USERDATA"))):
        if path:
            cmd.extend([opt, _strip_odin4_md5_trailer(path)])
    log("  > " + " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        hint = _explain_odin4_failure(out)
        raise RuntimeError(
            f"Pre-flash validation FAILED (rc={proc.returncode}). {hint}\n{out[-1200:]}"
        )
    log("  Pre-flash validation passed.")


def _env_flag(name):
    """Read an opt-in boolean env flag (ODIN4_*) - True only when explicitly on."""
    return os.environ.get(name, "0").strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Carrier / SIM-lock workbench
#
# Layer 1 is a read-only, vendor-agnostic lock-status detector (works over ADB
# on any Android). Layer 2 is the MediaTek modem-NVRAM read/backup/analyze path
# (A05/A06). The patch step is RECIPE-GATED: it only writes when a validated
# recipe exists AND the expected locked signature is present - it never guesses
# on modem NV data.
# ---------------------------------------------------------------------------

# Android `gsm.sim.state` values that mean the device itself is carrier-locked.
_SIM_STATE_LOCKED = {
    "NETWORK_LOCKED", "PERSO_LOCKED", "CORPORATE_LOCKED",
    "NETWORK_PERSO_LOCKED", "SIM_LOCKED",
}

# Properties probed by the status detector (all read-only).
_SIM_LOCK_PROPS = (
    "gsm.sim.state", "gsm.sim.state.2", "ril.sim.state",
    "gsm.sim.operator.alpha", "gsm.sim.operator.numeric",
    "gsm.network.type", "gsm.version.baseband",
    "ro.product.model", "ro.product.name", "ro.product.device",
    "ro.csc.sales_code", "ro.boot.carrierid", "ro.boot.carrier", "ro.carrier",
    "persist.radio.simlock_status",
)

# MTK modem-NVRAM SimLock record markers. The lock lives in the modem NVRAM
# files (MP0B001_*) inside nvdata; these strings identify the record headers.
_MTK_SIMLOCK_MARKERS = (
    b"SIMLOCK", b"SIM_LOCK", b"SIM LOCK", b"simlock",
    b"MP0B001_003", b"MP0B001", b"NVD_IMAG",
)

# Partitions that can hold MTK modem NVRAM, probed in order.
_MTK_NV_PARTITIONS = ("nvdata", "nvram", "protect1", "protect2")

# SimLock patch recipes, keyed by normalized model. The pipeline only writes
# when a recipe matches AND its `lock_bytes` are found at `offset` in the
# read-back image. Entries are added ONLY after the offsets are validated on a
# real device - an unvalidated entry here can kill IMEI / RF calibration.
_MTK_SIMLOCK_RECIPES = {
    # "SM-A055F": {
    #     "partition": "nvdata",
    #     "offset": 0x00000000,
    #     "lock_bytes": bytes.fromhex("..."),
    #     "unlocked_bytes": bytes.fromhex("..."),
    # },
    # "SM-A065F": {
    #     "partition": "nvdata",
    #     "offset": 0x00000000,
    #     "lock_bytes": bytes.fromhex("..."),
    #     "unlocked_bytes": bytes.fromhex("..."),
    # },
}


def _carrier_sim_state():
    """Collect every read-only carrier / SIM-lock signal a device exposes over
    ADB. Pure read - never writes anything. Returns a dict with 'props'
    (property -> value) and 'dumps' (service name -> list of matching lines)."""
    props = {k: _adb_getprop(k) for k in _SIM_LOCK_PROPS}
    dumps = {}
    checks = (
        ("phone", "dumpsys phone 2>/dev/null",
         r"(?i)network[ _-]?lock|perso|sim[ _-]?lock|corporate|carrier[ _-]?lock"),
        ("telephony.registry", "dumpsys telephony.registry 2>/dev/null",
         r"(?i)(sim|lock|perso)"),
        ("carrier_config", "dumpsys carrier_config 2>/dev/null",
         r"(?i)lock"),
    )
    for name, cmd, pat in checks:
        try:
            out = bridge.adb_shell(cmd, timeout=25)
        except bridge.BridgeError:
            out = ""
        hits = []
        for line in out.splitlines():
            s = line.strip()
            if s and re.search(pat, s):
                hits.append(s[:160])
                if len(hits) >= 12:
                    break
        dumps[name] = hits
    return {"props": props, "dumps": dumps}


def _carrier_lock_verdict(info):
    """Classify the carrier-lock state from collected signals (read-only).
    Returns (verdict, evidence): verdict is one of
    LOCKED / UNLOCKED / PIN-LOCKED / NO-SIM / SIM-ERROR / UNKNOWN."""
    props = info["props"]
    states = {s.upper()
              for k in ("gsm.sim.state", "gsm.sim.state.2", "ril.sim.state")
              for s in [props.get(k, "")] if s}
    evidence = []
    locked = sorted(states & _SIM_STATE_LOCKED)
    if locked:
        evidence.append(f"sim state reports {', '.join(locked)}")
    for name, hits in info["dumps"].items():
        for h in hits:
            evidence.append(f"{name}: {h}")
    if locked:
        return "LOCKED", evidence
    # Strong lock wording from the phone service (never guesses on generic
    # registry noise like 'mSimState=READY').
    for h in evidence:
        if re.search(r"(?i)(network[ _-]?lock|perso[ _-]?lock|sim[ _-]?lock|carrier[ _-]?lock)", h):
            return "LOCKED", evidence
    if states & {"PIN_REQUIRED", "PUK_REQUIRED"}:
        return "PIN-LOCKED", evidence
    if states and states <= {"ABSENT"}:
        return "NO-SIM", evidence
    if "READY" in states:
        return "UNLOCKED", evidence
    if states & {"UNKNOWN", "NOT_READY", "RESTRICTED", "PERM_DISABLED"}:
        return "SIM-ERROR", evidence
    return "UNKNOWN", evidence


def _locate_simlock(data):
    """Scan a partition image for MTK modem-NVRAM SimLock record markers.
    Returns [(offset, marker_bytes), ...] - the longest marker at each hit."""
    best = {}
    for marker in _MTK_SIMLOCK_MARKERS:
        start = 0
        while True:
            i = data.find(marker, start)
            if i < 0:
                break
            prev = best.get(i)
            if prev is None or len(marker) > len(prev):
                best[i] = marker
            start = i + 1
    return sorted((off, m) for off, m in best.items())


def _hex_dump(data, off, length=48):
    """Render up to `length` bytes at `off` as a hex + ascii block for logs."""
    lines = []
    chunk = data[off:off + length]
    for i in range(0, len(chunk), 16):
        row = chunk[i:i + 16]
        hexs = " ".join(f"{b:02x}" for b in row)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
        lines.append(f"        {off + i:08x}  {hexs:<47}  |{asc}|")
    return "\n".join(lines)


# Map of MediaTek hw_code (hex) to DA filename in mtkclient repo
_MTK_DA_MAP = {
    0x6735: "mt6735_da.bin",   # MT6735
    0x6737: "mt6737_da.bin",   # MT6737
    0x6739: "mt6739_da.bin",   # MT6739
    0x6753: "mt6753_da.bin",   # MT6753
    0x6755: "mt6755_da.bin",   # MT6755
    0x6757: "mt6757_da.bin",   # MT6757
    0x6763: "mt6763_da.bin",   # MT6763
    0x6765: "mt6765_da.bin",   # MT6765
    0x6768: "mt6768_da.bin",   # MT6768
    0x6771: "mt6771_da.bin",   # MT6771
    0x6779: "mt6779_da.bin",   # MT6779
    0x6781: "mt6781_da.bin",   # MT6781
    0x6785: "mt6785_da.bin",   # MT6785
    0x6789: "mt6789_da.bin",   # MT6789
    0x6833: "mt6833_da.bin",   # MT6833
    0x6835: "mt6835_da.bin",   # MT6835
    0x6853: "mt6853_da.bin",   # MT6853
    0x6873: "mt6873_da.bin",   # MT6873
    0x6877: "mt6877_da.bin",   # MT6877
    0x6878: "mt6878_da.bin",   # MT6878
    0x6885: "mt6885_da.bin",   # MT6885
    0x6886: "mt6886_da.bin",   # MT6886
    0x6891: "mt6891_da.bin",   # MT6891
    0x6893: "mt6893_da.bin",   # MT6893
    0x6895: "mt6895_da.bin",   # MT6895
    0x6983: "mt6983_da.bin",   # MT6983
    0x6985: "mt6985_da.bin",   # MT6985
    0x6991: "mt6991_da.bin",   # MT6991
    0x8168: "mt8168_da.bin",   # MT8168
    0x8173: "mt8173_da.bin",   # MT8173
    0x8183: "mt8183_da.bin",   # MT8183
    0x8195: "mt8195_da.bin",   # MT8195
    0x8735: "mt8735_da.bin",   # MT8735
    0x8765: "mt8765_da.bin",   # MT8765
    0x8766: "mt8766_da.bin",   # MT8766
    0x8768: "mt8768_da.bin",   # MT8768
    0x8781: "mt8781_da.bin",   # MT8781
    0x8788: "mt8788_da.bin",   # MT8788
    0x8797: "mt8797_da.bin",   # MT8797
}

_MTK_DA_BASE_URL = "https://github.com/mtkclient/mtkclient/raw/master/da"


def _da_in_dirs(candidates):
    """First MediaTek DA-named .bin in any of the given directories."""
    for d in candidates:
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            low = name.lower()
            if low.endswith(".bin") and ("da" in low or "download" in low):
                p = os.path.join(d, name)
                if os.path.isfile(p):
                    return p
    return ""


def _download_mtk_da(hw_code, cache_dir):
    """Download the DA for the given hw_code from mtkclient repo."""
    import urllib.request
    da_name = _MTK_DA_MAP.get(hw_code)
    if not da_name:
        return ""
    url = f"{_MTK_DA_BASE_URL}/{da_name}"
    dest = os.path.join(cache_dir, da_name)
    if os.path.isfile(dest):
        return dest
    try:
        log(f"  Downloading DA for 0x{hw_code:04X} from {url}...")
        urllib.request.urlretrieve(url, dest)
        if os.path.getsize(dest) < 1024:
            os.remove(dest)
            return ""
        log(f"  Downloaded {da_name} ({os.path.getsize(dest)} bytes)")
        return dest
    except Exception as e:
        log(f"  DA download failed: {e}")
        if os.path.isfile(dest):
            os.remove(dest)
        return ""


def _find_mtk_da():
    """Locate a MediaTek Download Agent binary: the MTK_DA env var first (set
    by the MTK workbench file picker), then local cache, then auto-download
    based on detected chip, then common locations."""
    env = os.environ.get("MTK_DA", "").strip()
    if env and os.path.isfile(env):
        return env
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    candidates = [
        os.path.join(root, "root", "tools"),
        os.path.expanduser("~/Downloads"),
        "/tmp",
    ]
    da = _da_in_dirs(candidates)
    if da:
        return da
    # Try auto-download based on detected chip
    try:
        import json
        devs = json.loads(bridge._run(["mtk-detect"]))
        for d in devs:
            chip = d.get("chip")
            if chip and "hw_code" in chip:
                hw_code = chip["hw_code"]
                cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "flashpilot", "da")
                os.makedirs(cache_dir, exist_ok=True)
                da = _download_mtk_da(hw_code, cache_dir)
                if da:
                    return da
    except Exception:
        pass
    return ""


def _wait_mtk_brom_target(log, timeout=120):
    """Wait for a MediaTek BROM / preloader device to appear on USB.

    Boot-looping phones (the corrupted A14 case) cycle continuously: the
    preloader only stays on USB for a few seconds per reboot, so a fail-fast
    check misses it. This polls until the window is seen (or timeout / user
    cancel). Returns ('bus:address', stage) or (None, None).
    """
    deadline = time.time() + timeout
    last_hint = 0.0
    while time.time() < deadline:
        if cancel_requested():
            raise FlowCancelled("cancelled while waiting for MTK device")
        for d in mtk.find_mtk():
            stage = mtk.pid_stage(d.get("pid", 0))
            if stage in ("brom", "preloader"):
                return f"{d.get('bus')}:{d.get('address')}", stage
        if time.time() - last_hint > 6:
            last_hint = time.time()
            log("  ... waiting for the MTK BROM/preloader window (a boot-looping")
            log("      phone cycles - keep it plugged and wait for the catch)...")
        time.sleep(0.5)
    return None, None


def _mtk_retry(log, label, fn, timeout=180, abort_on=()):
    """Run a BROM-level bridge operation that can lose the device mid-run
    (boot-looping phone). Waits for the next BROM/preloader window and retries
    until success, timeout or user cancel. `fn(target)` returns the result
    string and must raise bridge.BridgeError on failure. `abort_on` is a
    sequence of substrings that mark a PERMANENT failure (e.g. "partition not
    found") - those stop retrying immediately."""
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        if cancel_requested():
            raise FlowCancelled(f"cancelled: {label}")
        target, stage = _wait_mtk_brom_target(log, timeout=deadline - time.time())
        if not target:
            raise RuntimeError(
                f"{label}: no MediaTek BROM/preloader device appeared within "
                f"{timeout}s - enter BROM (Vol Down + Power, dark screen)"
            )
        attempt += 1
        log(f"  [{label}] attempt {attempt} - device in {stage} mode, running ...")
        try:
            return fn(target)
        except bridge.BridgeError as e:
            msg = str(e)
            if abort_on and any(k in msg.lower() for k in abort_on):
                raise
            log(f"  [{label}] attempt {attempt} lost the device ({e}) - "
                "waiting for the next window ...")
    raise RuntimeError(f"{label}: no successful run within {timeout}s")


def _mtk_analyze_nvdata(log, part, img):
    """Scan a dumped MTK partition image for modem-NVRAM SimLock markers.
    Logs a report and returns the offsets of the lock-record markers."""
    with open(img, "rb") as f:
        data = f.read()
    found = _locate_simlock(data)
    if not found:
        log(f"  '{part}': no known SimLock markers "
            f"({len(data) >> 20} MB scanned, read-only).")
        return []
    log(f"  '{part}': {len(found)} SimLock marker(s) found:")
    for off, marker in found:
        label = marker.decode("ascii", "replace")
        log(f"    offset 0x{off:x}  marker '{label}'")
        log(_hex_dump(data, off, 32))
    return [off for off, _ in found]


def _mtk_simlock_patch(ctx, log, da, target, backups):
    """Recipe-gated SimLock patch. Refuses to write unless a validated recipe
    matches AND the expected locked signature is present AND the user opted in
    with MTK_SIMLOCK_PATCH=1. It never guesses on modem NV data."""
    model = (ctx.get("model") or os.environ.get("ODIN4_FORCE_MODEL") or "").upper()
    recipe = _MTK_SIMLOCK_RECIPES.get(model) or _MTK_SIMLOCK_RECIPES.get("*")
    if not recipe:
        log("")
        log("  PATCH: no validated recipe for this model - refusing to write.")
        log("  The read / backup / analysis above is complete and safe. The")
        log("  recipe table (_MTK_SIMLOCK_RECIPES in frp.py) only gains an")
        log("  entry once the offsets are validated on a real device.")
        return
    part = recipe["partition"]
    img = next((i for p, i in backups if p == part), None)
    if not img:
        log(f"  PATCH: recipe needs partition '{part}' but it was not read.")
        return
    if not _env_flag("MTK_SIMLOCK_PATCH"):
        log("")
        log("  PATCH: recipe matches but MTK_SIMLOCK_PATCH=1 is not set -")
        log("  refusing to write. Set the env flag to opt in.")
        return
    with open(img, "rb") as f:
        data = f.read()
    off = recipe["offset"]
    lock = recipe["lock_bytes"]
    unlock = recipe["unlocked_bytes"]
    if data[off:off + len(lock)] != lock:
        log("")
        log(f"  PATCH: locked signature NOT at offset 0x{off:x} "
            f"(got {data[off:off + len(lock)].hex()}) - refusing to guess.")
        return
    log("")
    log(f"  PATCH: locked signature confirmed at 0x{off:x} -> applying unlock...")
    patched = bytearray(data)
    patched[off:off + len(unlock)] = unlock
    out = f"{img}.patched"
    with open(out, "wb") as f:
        f.write(bytes(patched))
    log(f"  PATCH: writing patched '{part}' back through the DA...")
    res = bridge._run(["mtk-flash-part", target, da, f"{part}={out}"], timeout=1800)
    log(f"    {res}")
    log("")
    log("  DONE. Insert the locked SIM and re-run 'Carrier lock status' (ADB)")
    log("  to confirm the verdict is now UNLOCKED.")


def flow_carrier_lock_status():
    """Read-only carrier / SIM-lock status check on ANY connected Android
    device over ADB (Samsung, MediaTek, Qualcomm, UNISOC - vendor-agnostic).
    Never writes anything; reports the verdict + evidence + next steps."""

    def _run(ctx, log):
        log("=" * 60)
        log("CARRIER / SIM-LOCK STATUS CHECK (read-only)")
        log("=" * 60)
        log("  Safe on every device - this step only READS state. It never")
        log("  writes, patches or unlocks anything.")
        log("")
        if not _wait_for_adb(ctx, log, timeout=45):
            raise RuntimeError("no adb device appeared - enable USB debugging first")
        info = _carrier_sim_state()
        verdict, evidence = _carrier_lock_verdict(info)
        props = info["props"]
        model = props.get("ro.product.model") or props.get("ro.product.name")
        log(f"  Device  : {model or 'unknown'}")
        sales = props.get("ro.csc.sales_code") or props.get("ro.boot.carrierid")
        if sales:
            log(f"  Carrier : {sales}")
        op = props.get("gsm.sim.operator.alpha") or props.get("gsm.sim.operator.numeric")
        if op:
            log(f"  SIM     : {op}")
        bb = props.get("gsm.version.baseband")
        if bb:
            log(f"  Baseband: {bb}")
        log("")
        labels = {
            "LOCKED": "SIM / NETWORK LOCKED",
            "UNLOCKED": "UNLOCKED (SIM accepted)",
            "PIN-LOCKED": "SIM PIN / PUK locked (user code, not carrier)",
            "NO-SIM": "No SIM detected",
            "SIM-ERROR": "SIM error state (modem not ready)",
            "UNKNOWN": "State not exposed by this build",
        }
        log(f"  VERDICT: {labels.get(verdict, verdict)}")
        log("")
        if evidence:
            log("  Evidence:")
            for line in evidence:
                log(f"    - {line}")
        log("")
        log("  Guidance:")
        if verdict == "LOCKED":
            log("    This unit reports a carrier/network lock. Options:")
            log("      * Insert the carrier SIM that the phone was sold with (or")
            log("        a same-network brand) and test again - many locked units")
            log("        accept the home-network SIM.")
            log("      * Samsung: Settings -> Connections -> SIM manager ->")
            log("        'Network lock' -> Unlock, or dial *#7465625# to view.")
            log("      * MTK A05/A06 stuck with no network on any SIM: use")
            log("        'Carrier lock' -> 'MTK NVRAM SimLock' (BROM mode) to read")
            log("        and back up the modem lock record.")
        elif verdict == "UNLOCKED":
            log("    No active network lock detected for the inserted SIM.")
        elif verdict == "PIN-LOCKED":
            log("    This is a SIM PIN/PUK state (user code), not a carrier lock.")
            log("    Enter the PIN on the phone, or get the PUK from the carrier.")
        elif verdict == "NO-SIM":
            log("    Insert a SIM to evaluate the lock state.")
        else:
            log("    This build does not expose the lock state over ADB. See the")
            log("    Network Repair page for radio status.")

    steps = [Step("carrier_lock_status", _run)]
    return Flow("carrier lock status (read-only)", steps)


def flow_carrier_lock_mtk():
    """MediaTek (A05/A06) modem SimLock read-back, backup and analysis over the
    low-level DA. Reports where the lock record lives and its state. The patch
    step is recipe-gated: it only writes when a validated recipe matches AND the
    expected locked signature is present - it never guesses on modem NV data."""

    def _run(ctx, log):
        log("=" * 60)
        log("MTK MODEM SIMLOCK - READ / BACKUP / ANALYZE (A05 / A06)")
        log("=" * 60)
        log("  Samsung A05/A06 (Helio G85) keep the SIM/network lock in the")
        log("  modem NVRAM files (MP0B001_*) inside the nvdata partition.")
        log("  This flow reads that area over the low-level DA, keeps a backup")
        log("  and locates the lock record. It WRITES NOTHING unless a")
        log("  validated recipe matches AND MTK_SIMLOCK_PATCH=1 is set.")
        log("")
        da = _find_mtk_da()
        if not da:
            log("  DA binary not found.")
            log("  Pick the MediaTek Download Agent on the 'MTK' workbench page")
            log("  (e.g. MTK_AllInOne_DA.bin / *_DA.bin), then run this again.")
            raise RuntimeError("MediaTek DA binary required - pick it on the MTK workbench")
        log(f"  DA file : {da}")
        devs = mtk.detect_mtk()
        if not devs:
            fallback = mtk.find_mtk()
            if not fallback:
                log("")
                log("  No MediaTek device on USB. Enter BROM / preloader:")
                log("    1. Power the phone OFF completely.")
                log("    2. Hold Volume Down + Power (keep holding - the screen")
                log("       stays dark) until USB shows 0e8d:2000 (BROM) or")
                log("       0e8d:0003 (preloader).")
                raise RuntimeError("no MediaTek BROM/preloader device connected")
        else:
            pid = devs[0].get("pid")
            stage = mtk.pid_stage(pid)
            if stage not in ("brom", "preloader"):
                log(f"  Device is in '{stage}' stage - need BROM/Preloader.")
                log("  Power off, then re-enter with Volume Down + Power.")
                raise RuntimeError(f"MediaTek device in {stage} mode, need BROM/Preloader")
            log(f"  MediaTek device: 0e8d:{pid:04x} ({mtk.stage_label(stage)[0]})")
        log("")

        target = "auto"
        stamp = time.strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(os.path.expanduser("~"), "flashpilot_backups",
                                  f"carrier_lock_{stamp}")
        os.makedirs(backup_dir, exist_ok=True)
        log(f"  Backup dir: {backup_dir}")
        backups = []
        with tempfile.TemporaryDirectory(prefix="mtk_simlock_") as td:
            for part in _MTK_NV_PARTITIONS:
                img = os.path.join(td, f"{part}.img")
                try:
                    log(f"  Reading '{part}' partition via DA...")
                    res = bridge._run(["mtk-read-part", target, da, part, img],
                                      timeout=1200)
                    log(f"    {res}")
                except bridge.BridgeError as e:
                    log(f"    '{part}' unavailable: {e}")
                    continue
                if not os.path.isfile(img) or os.path.getsize(img) == 0:
                    log(f"    '{part}' read was empty - skipping")
                    continue
                shutil.copy2(img, os.path.join(backup_dir, f"{part}.img"))
                backups.append((part, img))
                found = _mtk_analyze_nvdata(log, part, img)
                if found:
                    ctx.setdefault("mtk_simlock_locked", []).extend(found)
            if not backups:
                log("  No NVRAM/NVDATA partition could be read - nothing to analyze.")
                log("  If the DA is rejected, try an authenticated DA or dump the")
                log("  preloader first (Read device info -> MTK BROM).")
                return
            log(f"  Backups saved: {backup_dir}")
            _mtk_simlock_patch(ctx, log, da, target, backups)

    steps = [Step("carrier_lock_mtk", _run)]
    return Flow("MTK nvram simlock read/backup/analyze (A05/A06)", steps)


# ---------------------------------------------------------------------------
# Flow: Pre-flight validation (the biggest single win for success rate)
# ---------------------------------------------------------------------------
def flow_preflight():
    """Validate firmware integrity, model match, PIT compatibility, and USB
    health BEFORE flashing. Catches 90% of the reasons a flash fails."""
    def _run(ctx, log):
        log("=" * 60)
        log("PRE-FLIGHT VALIDATION SUITE")
        log("=" * 60)

        ok = True

        # 1. Firmware archive integrity (md5)
        ap = _find_slot_tar("AP")
        if not ap and not _env_flag("ODIN4_EXACT_SLOTS"):
            ap = _find_firmware_tar()
        bl = _find_slot_tar("BL")
        cp = _find_slot_tar("CP")
        csc = _find_slot_tar("CSC") or _find_slot_tar("HOME_CSC")
        userdata = _find_slot_tar("USERDATA")
        archives = {"AP": ap, "BL": bl, "CP": cp, "CSC": csc, "USERDATA": userdata}

        if not any(archives.values()):
            raise RuntimeError("No firmware archives selected/found.")
        log("Firmware archives found:")
        if not _verify_archives(log, archives):
            ok = False
            log("  ERROR: one or more firmware archives failed checksum validation.")

        # 2. Model consistency check across archives
        models = {}
        for slot, path in archives.items():
            if not path:
                continue
            m = _model_from_firmware_name(os.path.basename(path))
            if m:
                models[slot] = m
        if models:
            uniq = set(models.values())
            if len(uniq) > 1:
                log(f"  ERROR: firmware slots target different models: {models}")
                ok = False
            else:
                log(f"  Firmware model: {next(iter(uniq))}")

        # 3. PIT extraction + device PIT comparison
        pit_src = None
        for slot in ("AP", "BL", "CSC", "HOME_CSC"):
            if archives.get(slot):
                entries, model = _parse_pit_from_tar(archives[slot])
                if entries:
                    pit_src = (slot, entries, model)
                    break
        if not pit_src:
            # Fall back to a PIT dropped in ~/flashpilot/pit/ (e.g. the CSC .pit).
            local_pit = None
            pit_dir = os.path.expanduser("~/flashpilot/pit")
            if os.path.isdir(pit_dir):
                for f in sorted(os.listdir(pit_dir)):
                    if f.lower().endswith(".pit"):
                        local_pit = os.path.join(pit_dir, f)
                        break
            if local_pit:
                try:
                    with open(local_pit, "rb") as pf:
                        raw = pf.read()
                    entries = pit.parse_pit(raw)
                    model = pit.parse_model(raw)
                    pit_src = ("local", entries, model)
                except Exception:
                    pit_src = None
        if pit_src:
            slot, entries, model = pit_src
            log(f"  PIT from {slot}: {len(entries)} partitions ({model})")
            # PITs are model-specific: refuse a PIT that provably belongs to a
            # different device. Combo labels (COM_TAR2MTK6765) cannot be
            # verified -> log and continue; the device PIT is authoritative.
            if models:
                fw_model = next(iter(set(models.values())))
                match = _models_match(fw_model, model)
                if match is False:
                    log(
                        f"  ERROR: PIT model '{model}' does not match firmware "
                        f"model '{fw_model}' - PITs are model-specific, refusing."
                    )
                    ok = False
                elif match is None and _is_device_model(_normalize_model(fw_model)):
                    log(
                        f"  NOTE: PIT header '{model}' is a combo/partition label "
                        "not a device model - proceeding (device PIT is "
                        "authoritative at flash time)."
                    )
            ctx["fw_pit_entries"] = entries
            ctx["fw_pit_model"] = model

        # 4. Device in download mode?
        d = _download_mode_device()
        if not d:
            log("  Device not detected in download mode yet.")
            log("  Connect in download mode to compare PIT & model.")
        else:
            log(f"  Device in download mode: 04e8:{d['pid']:04x} bus={d['bus']} addr={d['address']}")

        # 5. USB health
        _check_cdc_acm(log)

        if not ok:
            log("")
            raise RuntimeError("Pre-flight validation FAILED. Fix the errors above before flashing.")
        log("")
        log("  PRE-FLIGHT CHECKS PASSED - safe to flash.")
        return True

    return Flow("Pre-flight validation", [Step("preflight", _run)])


# ---------------------------------------------------------------------------
# Flow: Dump & compare PIT
# ---------------------------------------------------------------------------
def flow_odin_pit_tools():
    """Dump the device PIT, compare it against the firmware PIT, and optionally
    repartition by flashing a PIT (advanced)."""
    def _run(ctx, log):
        log("=" * 60)
        log("PIT TOOLS (DUMP / COMPARE / REPARTITION)")
        log("=" * 60)
        d = _download_mode_device()
        if not d:
            log("Waiting for device in download mode...")
            d = _wait_download_mode(log, timeout=30)
        if not d:
            raise RuntimeError("Device not in download mode.")

        target = f"04e8:{d['pid']:04x}@{d['bus']}:{d['address']}"

        # Dump device PIT
        import tempfile
        pit_dir = os.path.expanduser("~/flashpilot/pit")
        os.makedirs(pit_dir, exist_ok=True)
        device_pit_path = os.path.join(pit_dir, f"device_{d['bus']}_{d['address']}.pit")
        log(f"Dumping device PIT to {device_pit_path}...")
        try:
            res = bridge.odin_pit(target, device_pit_path, timeout=120)
            log(f"  {res}")
        except bridge.BridgeError as e:
            raise RuntimeError(f"PIT dump failed: {e}")
        raw = open(device_pit_path, "rb").read()
        entries = pit.parse_pit(raw)
        model = pit.parse_model(raw)
        ctx["device_pit_path"] = device_pit_path
        ctx["device_pit_entries"] = entries
        ctx["device_pit_model"] = model
        log(f"  Device model (from PIT): {model}")
        if model and not _is_device_model(model):
            log("  NOTE: combo/MTK PIT label - this is a MediaTek device (uses a")
            log("  GPT partition table). PIT dump/compare work as reference, but")
            log("  PIT repartitioning ('Send PIT') is NOT supported on MTK - use")
            log("  the MTK page GPT flows instead.")
        log(f"  Partitions: {len(entries)}")
        for e in entries[:40]:
            log(f"    {e.name}  {e.size_bytes() >> 20} MB")

        # Compare with firmware PIT
        fw_entries = ctx.get("fw_pit_entries")
        if fw_entries:
            fw_names = {e.name for e in fw_entries}
            dev_names = {e.name for e in entries}
            missing = fw_names - dev_names
            extra = dev_names - fw_names
            if missing or extra:
                log("  PIT MISMATCH between firmware and device:")
                if missing:
                    log(f"    firmware has partitions not in device: {sorted(missing)}")
                if extra:
                    log(f"    device has partitions not in firmware: {sorted(extra)}")
                log("  -> If flashing fails, use 'Repartition with firmware PIT'.")
            else:
                log("  PIT layouts MATCH - no repartition needed.")

        # PITs are model-specific: an A14 PIT is only valid on an A14, an A06
        # PIT only on an A06. Refuse a provable model mismatch.
        fw_model = ctx.get("fw_pit_model")
        if fw_model:
            match = _models_match(model, fw_model)
            if match is False:
                raise RuntimeError(
                    f"PIT model mismatch: device PIT says '{model}' but firmware "
                    f"PIT is '{fw_model}'. Refusing - PITs are model-specific and "
                    "must only be used on the matching device."
                )
            if match is None:
                log(
                    f"  NOTE: '{fw_model}' is a combo/partition PIT label - "
                    "cannot verify model from the header (device PIT is "
                    "authoritative)."
                )

        return True
    return Flow("PIT tools (dump/compare/repartition)", [Step("pit_tools", _run)])


# ---------------------------------------------------------------------------
# Flow: Flash a single partition / raw image
# ---------------------------------------------------------------------------
def flow_odin_flash_partition_gui():
    """Flash a single raw image to a named partition (boot, recovery, vbmeta,
    modem, etc.) using the native Odin protocol (no odin4 binary needed)."""
    def _run(ctx, log):
        log("=" * 60)
        log("FLASH SINGLE PARTITION (RAW IMAGE)")
        log("=" * 60)
        d = _download_mode_device()
        if not d:
            log("Waiting for device in download mode...")
            d = _wait_download_mode(log, timeout=30)
        if not d:
            raise RuntimeError("Device not in download mode.")
        target = f"04e8:{d['pid']:04x}@{d['bus']}:{d['address']}"

        # PIT is needed to map partition -> metadata
        pit_path = ctx.get("device_pit_path")
        if not pit_path or not os.path.isfile(pit_path):
            import tempfile
            pit_path = os.path.join(tempfile.gettempdir(), "samsung_dev.pit")
            try:
                bridge.odin_pit(target, pit_path, timeout=120)
            except bridge.BridgeError as e:
                raise RuntimeError(f"Could not dump PIT: {e}")
        ctx["device_pit_path"] = pit_path

        # Read selections from GUI/context
        partition = ctx.get("flash_partition") or os.environ.get("FLASH_PARTITION")
        image = ctx.get("flash_image") or os.environ.get("FLASH_IMAGE")
        if not partition or not image:
            raise RuntimeError(
                "Select a partition name and an image file in the GUI "
                "(Partition + Image fields)."
            )
        if not os.path.isfile(image):
            raise RuntimeError(f"Image not found: {image}")

        log(f"  Partition: {partition}")
        log(f"  Image:     {image} ({os.path.getsize(image) >> 20} MB)")
        log("  Flashing via native Odin protocol... DO NOT unplug!")
        try:
            res = bridge._run(["odin-flash", target, pit_path, partition, image], timeout=1800)
            log(res)
        except bridge.BridgeError as e:
            raise RuntimeError(f"Flash failed: {e}")
        log("  Single partition flashed successfully.")
        return True
    return Flow("Flash single partition (raw)", [Step("flash_partition", _run)])


# ---------------------------------------------------------------------------
# Flow: VBMETA / signature verification control
# ---------------------------------------------------------------------------
def flow_odin_vbmeta():
    """Extract vbmeta.img from the firmware and (optionally) patch it to disable
    AVB verification - the standard way to boot unofficial/custom images on an
    OEM-unlocked device. Flashes the patched vbmeta with the native protocol."""
    def _run(ctx, log):
        log("=" * 60)
        log("VBMETA / AVB SIGNATURE CONTROL")
        log("=" * 60)
        ap = _find_slot_tar("AP")
        if not ap and not _env_flag("ODIN4_EXACT_SLOTS"):
            ap = _find_firmware_tar()
        if not ap:
            raise RuntimeError("AP firmware archive not found.")

        # Find vbmeta in the AP tar
        vbmeta_member = None
        try:
            with tarfile.open(ap, "r:*") as tf:
                for member in tf.getmembers():
                    if member.isfile() and member.name.lower() in (
                        "vbmeta.img", "vbmeta.img.lz4",
                    ):
                        vbmeta_member = member
                        break
        except Exception as e:
            raise RuntimeError(f"Could not read AP archive: {e}")

        if not vbmeta_member:
            log("  No vbmeta.img found in AP archive - device may not use AVB.")
            return False

        out_dir = os.path.expanduser("~/flashpilot/cache")
        os.makedirs(out_dir, exist_ok=True)
        out_name = os.path.basename(vbmeta_member.name)
        if out_name.endswith(".lz4"):
            out_name = out_name[:-4]
        out_path = os.path.join(out_dir, f"{out_name}.patched")

        # Extract (decode lz4 if needed)
        log(f"  Extracting {vbmeta_member.name} from AP...")
        raw = None
        with tarfile.open(ap, "r:*") as tf:
            raw = tf.extractfile(vbmeta_member).read()
        if vbmeta_member.name.endswith(".lz4"):
            raw = _lz4_decompress(raw)
        if not raw:
            raise RuntimeError("Could not extract vbmeta.")

        log(f"  vbmeta size: {len(raw)} bytes")
        patch = os.environ.get("VBMETA_PATCH", "1") == "1"
        if patch:
            log("  Patching vbmeta: disabling AVB verification (flags 0x03)...")
            patched = _patch_vbmeta_flags(raw)
            if patched is None:
                raise RuntimeError("vbmeta.img is not a valid AVB image - cannot patch.")
            with open(out_path, "wb") as f:
                f.write(patched)
            log(f"  Patched vbmeta written to {out_path}")
            ctx["vbmeta_patched_path"] = out_path
        else:
            with open(out_path.replace(".patched", ""), "wb") as f:
                f.write(raw)
            log("  Skipping patch (VBMETA_PATCH=0).")

        # Flash it (needs download mode + PIT)
        d = _download_mode_device()
        if not d:
            log("  (Not flashing now - device not in download mode. Use")
            log("   'Flash single partition' with partition 'vbmeta' and the")
            log(f"   patched image {out_path} to apply it.)")
            return True
        target = f"04e8:{d['pid']:04x}@{d['bus']}:{d['address']}"
        pit_path = ctx.get("device_pit_path") or os.path.join(tempfile.gettempdir(), "samsung_dev.pit")
        if not os.path.isfile(pit_path):
            try:
                bridge.odin_pit(target, pit_path, timeout=120)
            except bridge.BridgeError:
                pass
        log(f"  Flashing patched vbmeta to partition 'vbmeta'...")
        try:
            bridge._run(["odin-flash", target, pit_path, "vbmeta", out_path], timeout=300)
            log("  vbmeta flashed successfully.")
        except bridge.BridgeError as e:
            raise RuntimeError(f"vbmeta flash failed: {e}")
        return True
    return Flow("VBMETA / AVB signature control", [Step("vbmeta", _run)])


# ---------------------------------------------------------------------------
# Flow: Native multi-partition flash (one session, no odin4 binary)
# ---------------------------------------------------------------------------
def flow_odin_flash_multi():
    """Flash several raw partition images in ONE native Odin session using the
    Rust protocol implementation - the odin4 binary is NOT required.

    Each partition=image pair is resolved against the device's own PIT (dumped
    automatically when missing). The whole set is written in a single session
    with end-of-flash reboot optional.

    Bootloader-revision awareness: when a flashed image is an older bootloader
    (BL) revision than the device's current one, the flow refuses unless
    ODIN4_FORCE_BL=1 (same override as the odin4 advanced flash) - flashing a
    lower BL revision can hard-brick newer devices."""
    def _run(ctx, log):
        log("=" * 60)
        log("MULTI-PARTITION FLASH (NATIVE ODIN PROTOCOL)")
        log("=" * 60)
        d = _download_mode_device()
        if not d:
            log("Waiting for device in download mode...")
            d = _wait_download_mode(log, timeout=30)
        if not d:
            raise RuntimeError("Device not in download mode.")
        target = f"04e8:{d['pid']:04x}@{d['bus']}:{d['address']}"

        spec_str = ctx.get("flash_specs") or os.environ.get("FLASH_SPECS")
        if not spec_str:
            raise RuntimeError(
                "No flash specs. Provide partition=image pairs separated by ';' "
                "(e.g. boot=boot.img;recovery=recovery.img) in the Flash specs field."
            )
        specs = []
        for part in spec_str.split(";"):
            part = part.strip()
            if not part:
                continue
            if "=" not in part:
                raise RuntimeError(f"Bad spec '{part}' (expected partition=image).")
            name, img = part.split("=", 1)
            name, img = name.strip(), img.strip()
            if not name or not os.path.isfile(img):
                raise RuntimeError(f"Bad spec: partition='{name}' image='{img}' (missing file?).")
            specs.append((name, img))

        pit_path = ctx.get("device_pit_path")
        if not pit_path or not os.path.isfile(pit_path):
            pit_path = os.path.join(tempfile.gettempdir(), "samsung_dev.pit")
            try:
                bridge.odin_pit(target, pit_path, timeout=120)
            except bridge.BridgeError as e:
                raise RuntimeError(f"Could not dump device PIT: {e}")
        ctx["device_pit_path"] = pit_path

        log(f"  Partitions to flash ({len(specs)}):")
        total = 0
        for name, img in specs:
            sz = os.path.getsize(img)
            total += sz
            log(f"    {name} <- {os.path.basename(img)} ({sz >> 20} MB)")
        log(f"  Total: {total >> 20} MB - flashing in ONE session via native protocol.")
        log("  DO NOT unplug!")

        _enforce_bl_downgrade_gate(ctx, log, specs)

        reboot = ctx.get("flash_reboot") or _env_flag("ODIN4_REBOOT")
        try:
            res = bridge.odin_flash_multi(target, pit_path, specs, reboot=bool(reboot))
        except bridge.BridgeError as e:
            raise RuntimeError(f"Multi-partition flash failed: {e}")
        log(f"  {res}")
        log("  Multi-partition flash completed successfully.")
        if reboot:
            log("  Device is rebooting.")
        else:
            log("  Device stays in download mode - power off / reboot when ready.")
        return True

    return Flow("Flash multiple partitions (native Odin)", [Step("flash_multi", _run)])


# ---------------------------------------------------------------------------
# Flow: Send a PIT to the device (repartition)
# ---------------------------------------------------------------------------
def flow_odin_send_pit():
    """Send a PIT file to the device to repartition / re-map its partition
    layout, using the native Odin protocol (no odin4 binary)."""
    def _run(ctx, log):
        log("=" * 60)
        log("SEND PIT TO DEVICE (REPARTITION)")
        log("=" * 60)
        pit_file = ctx.get("pit_file") or os.environ.get("PIT_FILE")
        if not pit_file or not os.path.isfile(pit_file):
            raise RuntimeError(
                "No PIT file. Set a .pit path in the PIT file field "
                "(or PIT_FILE env var)."
            )
        d = _download_mode_device()
        if not d:
            log("Waiting for device in download mode...")
            d = _wait_download_mode(log, timeout=30)
        if not d:
            raise RuntimeError("Device not in download mode.")
        target = f"04e8:{d['pid']:04x}@{d['bus']}:{d['address']}"
        log(f"  PIT:     {pit_file} ({os.path.getsize(pit_file)} bytes)")
        log(f"  Device:  {target}")
        try:
            raw = open(pit_file, "rb").read()
            model = pit.parse_model(raw)
        except OSError as e:
            raise RuntimeError(f"Could not read PIT file: {e}")
        if model:
            log(f"  PIT header model: '{model}'")
            if not _is_device_model(model):
                # Combo labels (COM_TAR2MTK6765, ...) belong to MediaTek
                # Samsung devices (A05/A06/A14 5G). They use a GPT partition
                # table and their download agent has no PIT_SET / repartition
                # flow - sending a PIT to them ALWAYS fails at the protocol
                # level, so refuse up front instead of a cryptic error.
                log("  WARNING: this PIT has a combo/MTK label - MediaTek Samsung")
                log("  devices (A05/A06/A14 5G) use a GPT partition table, not a PIT.")
                log("  The MTK download agent does NOT implement the PIT_SET flow,")
                log("  so sending this PIT can never succeed. Partition work on MTK")
                log("  is done over the MediaTek DA: use the MTK page flows")
                log("  'List Partitions' / 'Flash Partition (No Scatter)' /")
                log("  'Generate Scatter (from device GPT)'.")
                raise RuntimeError(
                    "PIT repartition is not supported on MediaTek devices (they "
                    "use a GPT partition table) - sending this PIT would always fail."
                )
        log("  WARNING: repartitioning rewrites the partition table. Only send")
        log("  a PIT for the EXACT same model, or the device may not boot.")
        try:
            res = bridge.odin_send_pit(target, pit_file, timeout=120)
            log(f"  {res}")
        except bridge.BridgeError as e:
            raise RuntimeError(f"PIT send failed: {e}")
        log("  PIT sent successfully.")
        return True

    return Flow("Send PIT to device (repartition)", [Step("send_pit", _run)])


# ---------------------------------------------------------------------------
# Flow: EFS backup / restore
# ---------------------------------------------------------------------------
def flow_efs_backup():
    """Back up the EFS partition (IMEI / network calibration) before flashing."""
    def _run(ctx, log):
        log("=" * 60)
        log("EFS BACKUP (IMEI / NETWORK CALIBRATION)")
        log("=" * 60)
        if not _wait_for_adb(ctx, log, timeout=30):
            raise RuntimeError("ADB device required for EFS backup.")
        backup_dir = os.path.expanduser("~/flashpilot/efs_backups")
        os.makedirs(backup_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"efs_{ctx.get('serial','device')}_{stamp}.tar")
        log("  Running: adb shell su -c 'tar -cf /sdcard/efs_backup.tar /efs'")
        try:
            bridge.adb_shell("su -c 'tar -cf /sdcard/efs_backup.tar /efs'", timeout=120)
            log("  Pulling backup to PC...")
            import subprocess as sp
            sp.run(["adb", "pull", "/sdcard/efs_backup.tar", backup_path], check=True, timeout=300)
            log(f"  EFS backup saved: {backup_path}")
            ctx["efs_backup"] = backup_path
        except Exception as e:
            raise RuntimeError(f"EFS backup failed: {e}")
        return True
    return Flow("EFS backup", [Step("efs_backup", _run)])


def flow_efs_restore():
    """Restore a previously saved EFS backup."""
    def _run(ctx, log):
        log("=" * 60)
        log("EFS RESTORE")
        log("=" * 60)
        backup = os.environ.get("EFS_BACKUP_PATH")
        if not backup or not os.path.isfile(backup):
            # pick most recent
            d = os.path.expanduser("~/flashpilot/efs_backups")
            cands = sorted(glob.glob(os.path.join(d, "efs_*.tar")), key=os.path.getmtime, reverse=True)
            if not cands:
                raise RuntimeError("No EFS backup found. Run EFS backup first.")
            backup = cands[0]
        if not _wait_for_adb(ctx, log, timeout=30):
            raise RuntimeError("ADB device required for EFS restore.")
        log(f"  Using backup: {backup}")
        try:
            bridge.adb_shell("su -c 'mount -o rw,remount /'", timeout=30)
            sp = __import__("subprocess")
            sp.run(["adb", "push", backup, "/sdcard/efs_backup.tar"], check=True, timeout=300)
            bridge.adb_shell("su -c 'tar -xf /sdcard/efs_backup.tar -C /'", timeout=300)
            log("  EFS restored successfully.")
        except Exception as e:
            raise RuntimeError(f"EFS restore failed: {e}")
        return True
    return Flow("EFS restore", [Step("efs_restore", _run)])


# ---------------------------------------------------------------------------
# Flow: Change sales code (CSC) - Thor feature
# ---------------------------------------------------------------------------
def flow_change_sales_code():
    """Change the device CSC / sales code (Thor feature) via ADB."""
    def _run(ctx, log):
        log("=" * 60)
        log("CHANGE SALES CODE (CSC)")
        log("=" * 60)
        if not _wait_for_adb(ctx, log, timeout=30):
            raise RuntimeError("ADB device required.")
        code = (os.environ.get("SALES_CODE") or "").strip().upper()
        if not code:
            raise RuntimeError("Set a sales code (e.g. OJM, XME, INS) in the Sales Code field.")
        if not re.fullmatch(r"[A-Z0-9]{2,6}", code):
            raise RuntimeError(
                f"Invalid sales code {code!r}: sales codes are 2-6 chars of "
                "letters/digits (e.g. OJM, XME, INS)."
            )
        log(f"  Setting sales code to {code}...")
        try:
            bridge.adb_shell(f"settings put global sales_code '{code}'", timeout=30)
            bridge.adb_shell(f"setprop persist.sys.csc.sales_code '{code}'", timeout=30)
            bridge.adb_shell("am broadcast -a com.sec.android.app.csc.MAIN", timeout=30)
            log(f"  Sales code set to {code}. Some features apply after reboot.")
        except Exception as e:
            raise RuntimeError(f"Sales code change failed: {e}")
        return True
    return Flow("Change sales code (CSC)", [Step("sales_code", _run)])


def _find_combo_tar():
    """Locate a combination firmware tar (COMBINATION_*.tar / .tar.md5)."""
    env = os.environ.get("COMBINATION_TAR")
    if env and os.path.isfile(env):
        return env
    dirs = [os.path.expanduser("~/Downloads"), os.path.expanduser("~"), os.getcwd()]
    for d in dirs:
        if not os.path.isdir(d):
            continue
        cands = sorted(
            glob.glob(os.path.join(d, "COMBINATION*.tar*")),
            key=os.path.getmtime, reverse=True,
        )
        if cands:
            return cands[0]
    return ""


def _combo_flash_to_adb(ctx, log, purpose="get adb"):
    """REAL download-mode implementation: flash a combination firmware with
    the leaked Odin v4 for Linux (odin4) so a bootloader-LOCKED phone boots a
    test build with full adb, then wait for adb.

    A combination build (COMBINATION_A055F*.tar / COMBINATION_A065F*.tar) is a
    Samsung-signed test firmware - it is the only way to get adb on a locked
    A05/A06. Returns True once adb is online. Raises RuntimeError when the
    odin4 binary or the firmware is missing, the phone is not in download mode,
    or the flash / boot fails.
    """
    log("=" * 60)
    log(f"FLASH COMBINATION FIRMWARE (download mode) - {purpose}")
    log("=" * 60)
    log("  What this does: combo firmware (COMBINATION_A055F.../A065F...) is a")
    log("  Samsung-signed TEST build. Flashed into the AP slot it boots a debug")
    log("  Android with full adb on a bootloader-LOCKED phone - the only way to")
    log("  get adb on a locked A05/A06.")

    odin4 = _find_odin4()
    if not odin4:
        log("")
        log("  'odin4' NOT FOUND on this PC.")
        log("  Download the official leaked Odin v4 for Linux (single binary,")
        log("  works on MediaTek) - XDA thread:")
        log("    'OFFICIAL Samsung Odin v4 1.2.1-dc05e3ea - For Linux'")
        log("    (https://xdaforums.com/t/4453423, attachment odin.zip)")
        log("  or on Arch: `paru -S odin4`.")
        log("  Then put it on PATH, or set ODIN4_BIN=/path/to/odin4, and rerun.")
        raise RuntimeError("odin4 binary not found (see above for the download)")

    combo = _find_combo_tar()
    if not combo:
        log("")
        log("  Combination firmware NOT FOUND. It is a Samsung-signed test")
        log("  build named like COMBINATION_A065F*...tar (A06) or")
        log("  COMBINATION_A055F*...tar (A05). Search the web for:")
        log("    'SM-A065F combination firmware' / 'A065F combination'")
        log("  (~2-4 GB download). Put it in ~/Downloads, or set")
        log("  COMBINATION_TAR=/path/to/file.tar, and rerun this method.")
        raise RuntimeError("combination firmware not found (see above)")

    d = _download_mode_device()
    if not d:
        log("")
        log("PHONE: enter download mode (power off, hold Volume Down + Power,")
        log("  then press Volume Up to the 'Downloading...' screen 04e8:685d),")
        log("  keep it plugged in.")
        d = _wait_download_mode(log, timeout=30)
    if not d:
        raise RuntimeError(
            "phone is not in download mode (04e8:685d without ADB) - see "
            "the note above if it shows the normal ADB composite instead"
        )
    log(f"  Odin target: {d['vid']:04x}:{d['pid']:04x} "
        f"bus={d['bus']} addr={d['address']}")
    log("  (the download agent is Samsung's proprietary protocol; odin4 is the")
    log("   tool that talks to it)")

    log(f"  odin4:     {odin4}")
    log(f"  firmware:  {os.path.basename(combo)} ({os.path.getsize(combo) >> 20} MB)")

    log("")
    log("  Note for 'bulk read timeout' on Linux: the cdc_acm kernel module")
    log("  is known to break Odin transfers on some setups. If odin4 fails")
    log("  with 'Connection timed out', run in a terminal:")
    log("      sudo rmmod cdc_acm")
    log("  (and retry). The udev rule for access is usually already fine on")
    log("  Ubuntu/Debian with the plugdev group.")

    log("")
    log("  Flashing now ... phone shows progress; DO NOT unplug. (15 min cap)")
    combo = _strip_odin4_md5_trailer(combo)
    cmd = [odin4, "-a", combo, *_odin4_allow_unknown()]
    log("  > " + " ".join(cmd))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            "odin4 timed out after 15 min - phone still in download mode; "
            "check the cable and rerun"
        )
    out = (proc.stdout or "") + (proc.stderr or "")
    if out:
        log(out[-2500:])
    if proc.returncode != 0:
        hint = _explain_odin4_failure(out)
        raise RuntimeError(
            f"odin4 failed (rc={proc.returncode}). {hint}"
        )
    log("")
    log("  odin4 reported success. The phone reboots into the combination")
    log("  build (test firmware with full adb). Waiting up to 3 min for adb...")
    if not _wait_for_adb(ctx, log, timeout=180):
        log("  No adb device yet. The combo build may still be booting - watch")
        log("  the phone, then rerun 'FRP bypass' -> ADB when 'adb devices'")
        log("  shows it online.")
        return False
    return True


def flow_mtk_download_info():
    """Read device info for a MediaTek download-mode phone (A05/A06 family).

    These boot a proprietary MediaTek download agent that open-source LOKE
    tools cannot talk to - so there is no PIT/model read over Odin. Reports
    the device, explains the limitation, and how to get the model after a
    combination build.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("MEDIATEK DOWNLOAD MODE (A05 / A06 family)")
        log("=" * 60)
        d = _download_mode_device()
        if not d:
            log("PHONE: enter download mode (power off, hold Volume Down + Power,")
            log("  then press Volume Up), keep it plugged in.")
            d = _wait_download_mode(log, timeout=30)
        if not d:
            raise RuntimeError("phone is not in download mode (04e8:685d without ADB)")
        log(f"  USB: 04e8:{d['pid']:04x} bus={d['bus']} addr={d['address']}")
        _odin_diag(log)
        log("  Model: MediaTek models are read from the specs (A06 = SM-A065F,")
        log("  A05 = SM-A055F). After flashing a combination build the model is")
        log("  confirmed over adb: `getprop ro.product.model`.")

    steps = [Step("mtk_download_info", _run)]
    return Flow("mediaTek download mode info", steps)


def flow_mtk_brom_info():
    """Detect and report a MediaTek BROM / preloader device.

    Samsung A05/A06 (Helio G85) expose the low-level MediaTek USB modes:
    BROM (pid 0x2000), preloader (0x0003) and the Download Agent (0x0004).
    This flow detects which stage the phone is in, runs the real MediaTek
    BROM sync handshake over USB, reads the SoC / security config and the
    device identity (ME_ID / SOC_ID), and explains what each stage unlocks.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("MEDIATEK BROM / PRELOADER DETECTION")
        log("=" * 60)
        log("  Samsung A05/A06 run MediaTek chips (Helio G85). Besides the")
        log("  Samsung download agent they expose the classic MediaTek USB")
        log("  low-level modes: BROM, Preloader and the Download Agent (DA).")
        log("")

        devs = mtk.detect_mtk()
        if not devs:
            fallback = mtk.find_mtk()
            if fallback:
                for d in fallback:
                    log(
                        f"  USB: {d['vid']:04x}:{d['pid']:04x} "
                        f"bus={d['bus']} addr={d['address']}"
                    )
                log("  (bridge chip-read not available - device listed from USB detect)")
            log("")
            log("  No MediaTek device detected on USB right now.")
            log("")
            log("  How to ENTER the MediaTek low-level modes:")
            log("    1. Power the phone OFF completely.")
            log("    2. BROM/preloader entry differs by board:")
            log("       - Most Samsung MTK boards: hold Volume Down + Power, then")
            log("         keep holding until the phone enumerates as '0e8d:2000'")
            log("         (BROM) or '0e8d:0003' (preloader) - it stays dark.")
            log("       - Some boards need the battery out first, then plug USB")
            log("         while holding Volume Up (battery-less BROM entry).")
            log("    3. Do NOT let it boot Android - the low-level USB device only")
            log("       appears in the first seconds or in the held state.")
            log("")
            log("  What each stage unlocks:")
            log("    BROM 0e8d:2000 - chip id read, preloader dump, bootloader")
            log("                    unlock and partition reads (mtkclient).")
            log("    Preloader      - DA handshake -> full flashing (mtkclient,")
            log("                    SP Flash Tool) or Samsung combo via odin4.")
            log("    DA   0e8d:0004 - flashing already in progress.")
            raise RuntimeError("no MediaTek device connected (see entry guide above)")

        for d in devs:
            log(f"  USB device: {d['vid']:04x}:{d['pid']:04x} "
                f"bus={d['bus']} addr={d['address']}")
            if d.get("manufacturer"):
                log(f"    manufacturer: {d['manufacturer']}")
            if d.get("product"):
                log(f"    product:      {d['product']}")
            stage = d.get("boot_stage", "other")
            name, note = mtk.stage_label(stage)
            log(f"    stage:        {name}  (pid 0x{d['pid']:04x})")
            chip = d.get("chip")
            if chip is None:
                if d.get("note"):
                    log(f"    {d['note']}")
                log("")
                continue

            log("    handshake:    OK  (BROM sync echo a0 0a 50 05)")
            log(f"    mode:         {'MediaTek BootROM (BROM)' if chip.get('is_brom') else 'MediaTek Preloader'}")
            if chip.get("hw_code"):
                log(f"    SoC hw code:  0x{chip['hw_code']:04X}  ->  "
                    f"{mtk.chip_name(chip['hw_code'])}")
            log(f"    hw sub code:  0x{chip.get('hw_sub_code', 0):04X}   "
                f"hw ver {chip.get('hw_ver', 0)}   sw ver {chip.get('sw_ver', 0)}")
            if chip.get("blver") is not None:
                log(f"    BL ver:       0x{chip['blver']:02X}")
            if chip.get("bromver") is not None:
                log(f"    BROM version: 0x{chip['bromver']:02X}")
            tc = chip.get("target_config")
            if tc:
                log("    security flags (0x%02x):" % tc.get("raw", 0))
                log(f"      secure boot (SBC):   {'yes' if tc['sbc'] else 'no'}")
                log(f"      SLA auth:            {'yes' if tc['sla'] else 'no'}")
                log(f"      DAA auth:            {'yes' if tc['daa'] else 'no'}")
                log(f"      root cert required:  {'yes' if tc['cert'] else 'no'}")
                log(f"      mem read auth:       {'yes' if tc['memread'] else 'no'}")
                log(f"      mem write auth:      {'yes' if tc['memwrite'] else 'no'}")
                log(f"      cmd 0xC8 blocked:    {'yes' if tc['cmd_c8'] else 'no'}")
            if chip.get("meid"):
                log(f"    ME_ID:        {chip['meid']}")
            if chip.get("socid"):
                log(f"    SOC_ID:       {chip['socid']}")
            log("")

        secure = any(
            (c.get("chip") or {}).get("target_config")
            and (c["chip"]["target_config"]["sbc"]
                 or c["chip"]["target_config"]["sla"]
                 or c["chip"]["target_config"]["daa"])
            for c in devs
        )
        log("  What to do next:")
        if secure:
            log("    Secure boot is enabled (SBC/SLA/DAA) - this chip is under")
            log("    MediaTek's signed-chain protection. mtkclient can still read")
            log("    the chip id, but writes need an auth file, a test point or")
            log("    the Samsung combination-firmware route (MTK mode -> flash")
            log("    combination firmware) which boots full adb instead.")
        else:
            log("    No secure-boot flags set: a BROM/preloader session can back")
            log("    up the preloader and read partitions. On Linux:")
            log("        pipx install mtkclient")
            log("        mtk r preloader preloader.bin   (backup preloader)")
        log("    - Preloader mode: use 'flash combination firmware' (MTK mode)")
        log("      to get adb, or mtkclient / SP Flash Tool for full flashing.")
        log("    - If no handshake answer, the device never echoed the sync -")
        log("      re-enter BROM/preloader and make sure no other tool holds the")
        log("      USB port (the bridge needs a udev rule or root).")

    steps = [Step("mtk_brom_info", _run)]
    return Flow("mediaTek BROM / preloader detection", steps)


# Bootloader / security partitions worth backing up before any SW-REV bypass
# or downgrade write. Names are the standard MediaTek GPT labels on Samsung
# A-series; partitions that do not exist are skipped, never guessed at.
_MTK_BROM_BACKUP_PARTS = (
    "preloader", "boot", "vbmeta", "lk", "tee",
    "seccfg", "proinfo", "frp", "recovery", "dtbo",
)


def flow_mtk_brom_backup():
    """MediaTek BROM partition backup - the read-only safety net that must run
    BEFORE any SW-REV bypass / downgrade write.

    On Samsung MTK devices (A14 5G = MT6833, A05/A06 = Helio G85) the
    bootloader binary counter (SW-REV) is enforced by the Download Agent
    during the Odin/DA flash protocol, so a REV00 AP/BL can never be flashed
    over a REV1 bootloader through download mode. The only way past it is
    writing partitions directly at BROM level (kamakiri2 / mtkclient flow).
    Before that is ever attempted this flow:

      1. verifies the device is in BROM / preloader,
      2. runs the kamakiri2 BROM exploit and dumps + patches the preloader
         (the patched preloader is the DA that bypasses SLA auth later),
      3. lists the device GPT partition table,
      4. reads the bootloader / security partitions (preloader, boot, vbmeta,
         lk, tee, seccfg, proinfo, frp, recovery, dtbo) to a dated backup dir.

    It WRITES NOTHING to the device. If the exploit or a partition read fails
    it reports clearly - the downgrade flash is a separate explicit write flow.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("MTK BROM PARTITION BACKUP (read-only safety net)")
        log("=" * 60)
        log("  Purpose: back up the bootloader / security area before any")
        log("  SW-REV bypass or downgrade write. WRITES NOTHING to the phone.")
        log("")
        da = _find_mtk_da()
        if not da:
            log("  DA binary not found.")
            log("  Pick the MediaTek Download Agent on the 'MTK' workbench page")
            log("  (e.g. MTK_AllInOne_DA.bin / *_DA.bin), then run this again.")
            raise RuntimeError("MediaTek DA binary required - pick it on the MTK workbench")
        log(f"  DA file : {da}")
        log("")

        log("  Waiting for a MediaTek BROM / preloader device ...")
        log("  (Boot-looping phone: keep it plugged - the flow catches the")
        log("   preloader window automatically instead of failing instantly.)")
        log("")
        target, stage = _wait_mtk_brom_target(log, timeout=120)
        if not target:
            log("  To enter BROM / preloader:")
            log("    1. Power the phone OFF completely.")
            log("    2. Hold Volume Down + Power (keep holding - the screen")
            log("       stays dark) until USB shows 0e8d:2000 (BROM) or")
            log("       0e8d:0003 (preloader).")
            raise RuntimeError("no MediaTek BROM/preloader device appeared")
        log(f"  Caught device in '{stage}' ({mtk.stage_label(stage)[0]}).")
        log("")

        stamp = time.strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(os.path.expanduser("~"), "flashpilot_backups",
                                  f"brom_{stamp}")
        os.makedirs(backup_dir, exist_ok=True)
        log(f"  Backup dir: {backup_dir}")

        # 1) kamakiri2 exploit + preloader dump/patch. This validates the
        #    bypass path on THIS unit and produces the patched preloader (the
        #    DA used later to skip SLA auth), even if the partition reads below
        #    turn out to be rejected. Retried across boot-loop windows.
        pl_out = os.path.join(backup_dir, "preloader_patched.bin")
        os.environ["MTK_PRELOADER_OUT"] = pl_out
        try:
            log("  Running kamakiri2 BROM exploit (handshake + preloader dump)...")
            res = _mtk_retry(
                log, "kamakiri2 exploit",
                lambda t: bridge._run(["mtk-exploit", t, "mtk_bypass"],
                                      timeout=120),
                timeout=300,
            )
            log(f"    {res}")
        except (bridge.BridgeError, RuntimeError) as e:
            log(f"    exploit failed: {e}")
            log("    (continuing to GPT/read - unprotected chips may still work)")
        finally:
            os.environ.pop("MTK_PRELOADER_OUT", None)
        if os.path.isfile(pl_out) and os.path.getsize(pl_out):
            log(f"  Patched preloader saved: {pl_out} "
                f"({os.path.getsize(pl_out) >> 10} KB)")
        log("")

        # 2) Device GPT partition table listing (also saved to the backup dir).
        gpt_file = os.path.join(backup_dir, "gpt.txt")
        try:
            res = _mtk_retry(
                log, "GPT listing",
                lambda t: bridge._run(["mtk-gpt", t, da], timeout=300),
                timeout=120,
            )
            log(f"  Device GPT:\n{res}")
            with open(gpt_file, "w") as f:
                f.write(res + "\n")
        except (bridge.BridgeError, RuntimeError) as e:
            log(f"    GPT read failed: {e}")
        log("")

        # 3) Read the bootloader / security partitions.
        saved = []
        with tempfile.TemporaryDirectory(prefix="mtk_brom_") as td:
            for part in _MTK_BROM_BACKUP_PARTS:
                img = os.path.join(td, f"{part}.img")
                try:
                    res = _mtk_retry(
                        log, f"read '{part}'",
                        lambda t, p=part, i=img: bridge._run(
                            ["mtk-read-part", t, da, p, i], timeout=1200),
                        timeout=90,
                        abort_on=("not found",),
                    )
                    log(f"  {part}: {res}")
                except (bridge.BridgeError, RuntimeError) as e:
                    log(f"  {part}: unavailable ({e})")
                    continue
                if not os.path.isfile(img) or os.path.getsize(img) == 0:
                    log(f"  {part}: empty - skipping")
                    continue
                shutil.copy2(img, os.path.join(backup_dir, f"{part}.img"))
                saved.append(part)
        log("")
        if not saved:
            log("  No partitions could be read back.")
            log("  The patched preloader above may already be enough for the")
            log("  later downgrade path. If reads were rejected with an auth")
            log("  error, the DA itself still needs the bypass - re-run this")
            log("  with the phone freshly in BROM, or supply an auth file.")
        else:
            log(f"  Backed up {len(saved)} partition(s): {', '.join(sorted(saved))}")
        log(f"  Backup saved at: {backup_dir}")
        log("  Next step when ready: the explicit 'MTK BROM downgrade flash' write.")

    steps = [Step("mtk_brom_backup", _run)]
    return Flow("MTK BROM read & backup (bootloader + security area)", steps)


def flow_mtk_combo_flash():
    """Flash a combination firmware on a MediaTek phone via the leaked
    Samsung Odin v4 for Linux (odin4) - the only open-source-usable tool that
    speaks the MediaTek download-agent protocol. Combo firmware is a
    Samsung-signed test build that boots with full adb on a locked phone,
    which is what actually clears FRP on the A05/A06.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("MEDIATEK DOWNLOAD MODE - FLASH COMBINATION FIRMWARE (odin4)")
        log("=" * 60)
        log("  Samsung A05/A06 (Helio G85) boot a proprietary MediaTek download")
        log("  agent; odin4 is the only open-source tool that talks to it.")
        log("")
        if not _combo_flash_to_adb(ctx, log, purpose="get adb on a locked A05/A06"):
            return
        log("")
        log("  NEXT: run 'FRP bypass' -> ADB -> 'clear' now that adb works, then")
        log("  'Reboot device' -> ADB -> 'normal' to leave the test build.")

    steps = [Step("mtk_combo_flash", _run)]
    return Flow("flash combination firmware (mediaTek, odin4)", steps)


def flow_mtk_recovery_reset():
    """Guided recovery factory reset - clears the 'too many attempts /
    permanently locked' screen on any Samsung (MediaTek A05/A06 included),
    no PC or firmware needed."""

    def _run(ctx, log):
        log("=" * 60)
        log("RECOVERY FACTORY RESET (clears lock / 'too many attempts')")
        log("=" * 60)
        log("  Works on any Samsung phone with no PC. The lock and its attempt")
        log("  counter live in /data, so wiping /data clears them.")
        log("")
        log("  1. Power the phone off completely.")
        log("  2. Hold Volume Up + Power together.")
        log("  3. Keep holding until the Samsung logo appears; release Power but")
        log("     KEEP holding Volume Up until the recovery menu appears.")
        log("     (If you see 'No command', hold Power and press Volume Up once.)")
        log("  4. Volume keys: highlight 'Wipe data/factory reset' -> Power.")
        log("  5. Highlight 'Factory data reset' -> Power.")
        log("  6. Highlight 'Reboot system now' -> Power.")
        log("")
        log("  Result: no more lock, the phone boots to setup.")
        log("")
        log("  WARNING: if a Google account was on the phone it will stop at")
        log("  'Verify your account' (Google FRP). That is expected. Then use")
        log("  'flash combination firmware' (MTK mode) to get adb and clear it.")

    steps = [Step("mtk_recovery_reset", _run)]
    return Flow("recovery factory reset (mediaTek)", steps)


def flow_adb_frp():
    """Bypass FRP over a device that already has ADB (USB debugging on).

    Waits for the device, then marks setup complete / device provisioned and
    disables both setup wizards so the phone boots straight to the launcher.
    """
    ADB_STEPS = _ADB_FRP_STEPS

    def _run(ctx, log):
        log("PHONE: USB debugging must be on and this PC authorized")
        log("  (plug in, tap 'Always allow' on the 'Allow USB debugging' dialog).")
        log("  No ADB yet? Use 'FRP bypass' in 'MTP mode', or enter test mode "
            "(*#0*# from the Emergency dialer) first.")
        if not _wait_for_adb(ctx, log, timeout=60):
            raise RuntimeError("no adb device appeared - enable USB debugging first")
        for label, cmd in ADB_STEPS:
            log(f"  > adb shell {cmd}")
            try:
                out = bridge.adb_shell(cmd, timeout=30)
            except bridge.BridgeError as e:
                out = f"ERROR: {e}"
            if out:
                log(f"      {out[:120]}")
            time.sleep(1.2)
        log("Done. Reboot the phone (adb reboot) - it should go straight to the "
            "launcher, FRP gone.")

    steps = [Step("adb_frp_clear", _run)]
    return Flow("adb frp clear", steps)


def flow_frp_browser():
    """FRP bypass via the BROWSER method (on-phone, Android 8/9).

    Works at the 'Verify your account' / FRP screen after a factory reset:
    get the browser open, use it to reach Settings, and remove/swap the
    Google account blocking setup.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("FRP BYPASS - BROWSER METHOD")
        log("=" * 60)
        log("NOTE: this exploit targets ANDROID 8/9 FRP screens. On Android")
        log("13/14 (Galaxy A05/A06 and newer) these legacy methods are patched -")
        log("the reliable route there is combination firmware via Odin")
        log("(COMBINATION_*_*.tar in download mode).")
        log("")
        log("Do this ON the phone, at the 'Verify your account' (FRP) screen.")
        log("")
        log("1. From the FRP screen, open the BROWSER:")
        log("   - Tap Emergency call / Clock / Camera first; many builds then")
        log("     reveal a browser icon or a 'www' shortcut on the FRP screen.")
        log("   - If nothing appears, enable TalkBack (hold both Volume keys")
        log("     ~3s), then use 'Explore by touch' to reach the browser or a")
        log("     '...' menu.")
        log("")
        log("2. In the browser, jump to Settings:")
        log("     chrome://settings/        (Chrome)")
        log("   or type 'settings' as the address (browser shortcut).")
        log("")
        log("3. In Settings -> Accounts (Users & accounts):")
        log("   - REMOVE the Google account that is blocking you.")
        log("   - (Optional) Add a NEW Google account.")
        log("")
        log("4. Reboot the phone - it should now pass the FRP screen.")
        log("")
        log("If ADB is authorized (tap 'Always allow' if the dialog pops):")
        log("  I can open the browser for you.")
        if not _wait_for_adb(ctx, log, timeout=15):
            log("  (no ADB device yet - the reset usually wipes ADB authorization,")
            log("   so the manual steps above are the way to go)")
            return
        try:
            out = bridge.adb_shell(
                "am start -a android.intent.action.VIEW -d https://www.google.com",
                timeout=15,
            )
            log(f"  browser intent: {out[:120]}")
        except bridge.BridgeError as e:
            log(f"  browser intent failed: {e}")

    steps = [Step("frp_browser", _run)]
    return Flow("frp bypass (browser)", steps)


def flow_frp_emergency():
    """FRP bypass via the EMERGENCY-CALL method (on-phone, Android 8/9).

    Exploits the Emergency dialer on the FRP screen to reach Settings and
    remove the Google account that blocks setup.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("FRP BYPASS - EMERGENCY CALL METHOD")
        log("=" * 60)
        log("NOTE: this exploit targets ANDROID 8/9 FRP screens. On Android")
        log("13/14 (Galaxy A05/A06 and newer) these legacy methods are patched -")
        log("the reliable route there is combination firmware via Odin.")
        log("")
        log("Do this ON the phone, at the 'Verify your account' (FRP) screen.")
        log("")
        log("1. Tap 'EMERGENCY CALL' on the FRP screen.")
        log("2. Dial any number, then end the call (or hit back).")
        log("3. On the dialer/phone screen, swipe down the notification shade,")
        log("   or tap the in-call '3-dot' menu.")
        log("4. Open SETTINGS from there (gear icon in the shade or the menu).")
        log("5. In Settings -> Accounts (Users & accounts):")
        log("   - REMOVE the Google account that is blocking you.")
        log("   - (Optional) Add a NEW Google account.")
        log("6. Reboot the phone - it should now pass the FRP screen.")
        log("")
        log("If the Settings gear won't open, try the 'Browser' method - it uses")
        log("chrome://settings/ from the browser instead.")

    steps = [Step("frp_emergency", _run)]
    return Flow("frp bypass (emergency call)", steps)


def flow_frp_settings():
    """FRP bypass via the SETTINGS method (on-phone, Android 8/9).

    Many Samsung Oreo builds leave the Settings app reachable straight from
    the FRP screen - use it to remove the blocking Google account.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("FRP BYPASS - SETTINGS METHOD")
        log("=" * 60)
        log("NOTE: this exploit targets ANDROID 8/9 FRP screens. On Android")
        log("13/14 (Galaxy A05/A06 and newer) these legacy methods are patched -")
        log("the reliable route there is combination firmware via Odin.")
        log("")
        log("Do this ON the phone, at the 'Verify your account' (FRP) screen.")
        log("")
        log("1. Swipe down the notification shade and tap the SETTINGS (gear)")
        log("   icon, OR long-press 'Skip', OR open the CAMERA and go back -")
        log("   the app menu that appears often includes Settings.")
        log("2. In Settings -> Accounts (Users & accounts / Cloud and accounts):")
        log("   - REMOVE the Google account that is blocking you.")
        log("   - (Optional) Add a NEW Google account.")
        log("3. Reboot the phone - it should now pass the FRP screen.")
        log("")
        log("If Settings is not reachable, use the 'Emergency call' or 'Browser'")
        log("method to get in from another angle.")

    steps = [Step("frp_settings", _run)]
    return Flow("frp bypass (settings)", steps)


def flow_adb_info():
    """Read device identity over ADB: properties, provisioning/FRP state,
    lock state, encryption, battery and storage."""

    PROPS = [
        ("model", "ro.product.model"),
        ("marketing name", "ro.product.marketname"),
        ("device codename", "ro.product.device"),
        ("product name", "ro.product.name"),
        ("manufacturer", "ro.product.manufacturer"),
        ("android version", "ro.build.version.release"),
        ("SDK / API level", "ro.build.version.sdk"),
        ("security patch", "ro.build.version.security_patch"),
        ("build id", "ro.build.id"),
        ("build type", "ro.build.type"),
        ("One UI version", "ro.build.version.oneui"),
        ("bootloader", "ro.bootloader"),
        ("hardware", "ro.hardware"),
        ("board platform", "ro.board.platform"),
        ("chipset", "ro.chipname"),
        ("baseband / modem", "gsm.version.baseband"),
        ("serial", "ro.serialno"),
        ("adb secure", "ro.adb.secure"),
        ("usb config", "sys.usb.config"),
        ("boot mode", "ro.bootmode"),
        ("crypto state", "ro.crypto.state"),
        ("crypto type", "ro.crypto.type"),
        ("density (dpi)", "ro.sf.lcd_density"),
    ]

    def _run(ctx, log):
        if not _wait_for_adb(ctx, log, timeout=30):
            raise RuntimeError("no adb device available")

        log("=" * 60)
        log("DEVICE INFO (over ADB)")
        log("=" * 60)
        for label, key in PROPS:
            val = _adb_getprop(key)
            if label == "One UI version" and not val:
                continue
            log(f"  {label:<18}: {val or '(unset)'}")

        log("")
        log("  provisioning / FRP state:")
        for label, scope, name in [
            ("device_provisioned", "global", "device_provisioned"),
            ("user_setup_complete", "secure", "user_setup_complete"),
            ("setup_wizard_has_run", "global", "setup_wizard_has_run"),
            ("frp_done", "secure", "frp_done"),
        ]:
            val = _adb_setting(scope, name)
            log(f"    {label:<20}: {val if val else '(unset)'}")

        log("")
        log("  lock state:")
        _log_lock_state(log)

        log("")
        log("  battery / storage:")
        try:
            battery = bridge.adb_shell("dumpsys battery", timeout=15)
            for line in battery.splitlines():
                s = line.strip()
                if s.startswith("level:") or s.startswith("status:") or s.startswith("temperature:"):
                    log(f"    {s}")
        except bridge.BridgeError as e:
            log(f"    battery: {e}")
        try:
            disk = bridge.adb_shell("df /data", timeout=15)
            lines = disk.strip().splitlines()
            if lines:
                log(f"    /data: {lines[-1].split()[:3]}")
        except bridge.BridgeError as e:
            log(f"    storage: {e}")

    steps = [Step("adb_info", _run)]
    return Flow("adb read info", steps)


# ---------------------------------------------------------------------------
# Flow: Knox Guard (KG) state check
# ---------------------------------------------------------------------------
def flow_kg_state_check():
    """Check Knox Guard (KG) state via ADB.

    Reads ro.boot.kgstate, ro.boot.knox, ro.warranty_bit, and ro.secure
    to determine the current KG/Knox state.
    """
    def _run(ctx, log):
        if not _wait_for_adb(ctx, log, timeout=30):
            raise RuntimeError("ADB device required for KG state check.")
        
        log("=" * 60)
        log("KNOX GUARD (KG) STATE CHECK")
        log("=" * 60)
        
        kg_props = [
            ("KG State (ro.boot.kgstate)", "ro.boot.kgstate"),
            ("Knox Warranty Bit (ro.boot.knox)", "ro.boot.knox"),
            ("Warranty Bit (ro.warranty_bit)", "ro.warranty_bit"),
            ("Secure Boot (ro.secure)", "ro.secure"),
            ("Knox Version (ro.config.knox)", "ro.config.knox"),
            ("Knox Build Date (ro.build.knox)", "ro.build.date"),
        ]
        
        for label, key in kg_props:
            val = _adb_getprop(key)
            log(f"  {label:<35}: {val or '(unset)'}")
        
        # Interpret KG state
        kg_state = _adb_getprop("ro.boot.kgstate")
        if kg_state == "0":
            log("  >> KG STATE: UNLOCKED (0) - Custom firmware can boot")
        elif kg_state == "1":
            log("  >> KG STATE: LOCKED (1) - KG active, custom firmware blocked")
        elif kg_state:
            log(f"  >> KG STATE: UNKNOWN ({kg_state})")
        else:
            log("  >> KG STATE: Property not found (may be pre-KG device)")
        
        knox = _adb_getprop("ro.boot.knox")
        if knox == "0x0":
            log("  >> KNOX WARRANTY: INTACT (0x0)")
        elif knox:
            log(f"  >> KNOX WARRANTY: VOID ({knox})")
        
        return True
    return Flow("KG state check", [Step("kg_state_check", _run)])


# ---------------------------------------------------------------------------
# Flow: Knox Guard (KG) remove (requires vbmeta patch + root)
# ---------------------------------------------------------------------------
def flow_kg_remove():
    """Attempt to remove/disable Knox Guard (KG) by patching vbmeta.

    This requires:
    1. Device in Download mode
    2. vbmeta patching (disable AVB verification)
    3. Flash patched vbmeta
    4. Root access to clear KG state files

    WARNING: This trips Knox warranty bit permanently!
    """
    def _run(ctx, log):
        log("=" * 60)
        log("KNOX GUARD (KG) REMOVE / DISABLE")
        log("=" * 60)
        log("WARNING: This will trip the Knox warranty bit permanently!")
        log("This operation patches vbmeta to disable AVB verification,")
        log("then attempts to clear KG state via root.")
        log("")
        
        # First check current state
        if not _wait_for_adb(ctx, log, timeout=10):
            log("  ADB not available - will need Download mode for vbmeta flash")
        else:
            kg_state = _adb_getprop("ro.boot.kgstate")
            if kg_state == "0":
                log("  KG already appears UNLOCKED (ro.boot.kgstate=0)")
                return True
        
        # Use existing vbmeta patch flow to disable AVB
        log("  Patching vbmeta to disable AVB verification...")
        try:
            # Run the vbmeta patch flow
            from python.core import bridge
            ctx["vbmeta_patched_path"] = None
            flow_odin_vbmeta().run(ctx, log)
            vbmeta_path = ctx.get("vbmeta_patched_path")
            if not vbmeta_path:
                raise RuntimeError("vbmeta patch failed")
            log(f"  Patched vbmeta: {vbmeta_path}")
        except Exception as e:
            raise RuntimeError(f"vbmeta patch failed: {e}")
        
        # Flash the patched vbmeta (requires Download mode)
        log("  Flashing patched vbmeta (requires Download mode)...")
        try:
            flow_odin_flash_partition_gui().run(ctx, log)
        except Exception as e:
            raise RuntimeError(f"vbmeta flash failed: {e}")
        
        log("")
        log("vbmeta patched and flashed. Now you need to:")
        log("  1. Boot the device")
        log("  2. Gain root access (Magisk, etc.)")
        log("  3. Run: echo 0 > /sys/fs/pstore/kgstate (or similar)")
        log("  4. Clear /data/system/kgstate files if present")
        
        return True
    return Flow("KG remove (patch vbmeta)", [Step("kg_remove", _run)])


def flow_screen_lock_locksettings():
    """Screen lock removal via ADB `locksettings` (Android 8/9, no root).

    This is the reliable method for older Samsung devices such as the
    SM-S357BL (Galaxy J3 Top/Orbit, Android 8.0, Exynos 7570): the lock is
    stored in /data/system/locksettings.db and `locksettings` (present since
    Android 8) can disable or clear it without root, as long as USB debugging
    is on AND this PC is authorized before the phone is locked out.

    On Android 9+, `locksettings clear` refuses to run without `--old
    <credential>` once a lock is set, so the flow tries it without --old and
    then with common placeholder values.  `locksettings set-disabled true`
    does NOT need the old credential and is tried first.

    Falls back to the pre-8.0 settings keys for older Android versions.
    If no authorized ADB device is found up front, the flow first tries to
    ENABLE USB debugging for you (MTP/AT method, then test mode *#0*#).
    """

    _NO_LOCK_CODES = ("0", "", "null")

    def _run(ctx, log):
        log("=" * 60)
        log("SCREEN LOCK REMOVAL - ADB locksettings (Android 8/9)")
        log("=" * 60)

        up = False
        try:
            up = any(d["state"] == "device" for d in bridge.adb_status())
        except bridge.BridgeError:
            pass
        if not up:
            log("No authorized ADB device yet - enabling USB debugging ...")
            _try_enable_adb(ctx, log)
            log("")

        log("Waiting for an AUTHORIZED ADB device ...")
        if not _wait_for_adb(ctx, log, timeout=90):
            raise RuntimeError(
                "no adb device appeared - enable USB debugging first "
                "(see instructions above)"
            )

        serial = ctx.get("serial", "")
        log(f"Device serial: {serial}")

        # Lock state FIRST (the user wants to see this before anything else).
        log("")
        log("Current lock state (before):")
        before = _log_lock_state(log)
        log("")

        model = _adb_getprop("ro.product.model")
        android_version = _adb_getprop("ro.build.version.release")
        api_level = _adb_getprop("ro.build.version.sdk")
        crypto = _adb_getprop("ro.crypto.state")
        if model:
            log(f"Model: {model}")
        log(f"Android: {android_version or 'unknown'} (API {api_level or '?'})")
        log(f"Encryption: {crypto or 'unknown'}")
        if crypto == "encrypted":
            log("NOTE: encrypted (FDE/FBE) device - only the `locksettings` path")
            log("  is safe here. Never delete locksettings.db on an encrypted device.")
        log("")

        def run_cmd(label, cmd):
            """Run one adb shell command, log full output. Returns (ok, output)."""
            log(f"  > adb shell {cmd}")
            try:
                out = bridge.adb_shell(cmd, timeout=20) or ""
                out = out.strip()
            except bridge.BridgeError as e:
                log(f"      ERROR: {e}")
                return False, ""
            if not out:
                return True, ""
            log(f"      {out[:400]}")
            failed = (
                "exception" in out.lower()
                or "error:" in out.lower()
                or "failed" in out.lower()
            )
            return (not failed), out

        # No lock set at all -> nothing to remove. Only declare "no lock" when
        # we have POSITIVE confirmation; Samsung reports password_type as "null"
        # on locked devices, so uncertainty means: keep going (harmless).
        no_lock_confirmed = (
            before.get("password_type") in _NO_LOCK_CODES
            and before.get("disabled") is False
            and before.get("dumpsys_stored") is False
        )
        if no_lock_confirmed:
            log("This device has NO screen lock set - nothing to remove.")
            log("(You can set one in Settings -> Lock screen, then re-test.)")
            log("")
            log("If you were actually trying to clear an FRP/Google-account lock,")
            log("use the FRP bypass flows instead - this flow only clears a")
            log("pattern/PIN/password.")
            return
        if (
            before.get("password_type") in _NO_LOCK_CODES
            and before.get("dumpsys_stored") is None
        ):
            log("NOTE: lock state is ambiguous (password_type unset, no dumpsys")
            log("      confirmation) - continuing with removal anyway; harmless")
            log("      if there is no lock to remove.")
            log("")

        # --- Attack ladder -------------------------------------------------
        ok_set_disabled = False

        # 1) No old credential needed: disable the lock screen.
        ok, out = run_cmd(
            "disable lock screen (no old credential needed)",
            "locksettings set-disabled true",
        )
        ok_set_disabled = ok
        try:
            flag = bridge.adb_shell("locksettings get-disabled", timeout=8).strip()
            if flag.lower() == "true":
                ok_set_disabled = True
                log("      confirmed: locksettings get-disabled -> true")
            else:
                log(f"      get-disabled -> {flag!r}")
        except bridge.BridgeError:
            pass

        # 2) Clear the credential. On Android 9+ a set lock requires --old.
        ok_clear = False
        for old in ("", "0000", "000000", "1234"):
            if old:
                cmd = f"locksettings clear --old {old}"
            else:
                cmd = "locksettings clear"
            ok, out = run_cmd(f"clear lock (--old {old or 'none'})", cmd)
            if ok and out and "clear" in out.lower():
                pass
            if ok:
                ok_clear = True
                break
        # get-lock-mode shows the surviving lock type (API 28+).
        try:
            mode = bridge.adb_shell("locksettings get-lock-mode", timeout=8).strip()
            if mode in ("0", "none"):
                ok_clear = True
                log("      confirmed: locksettings get-lock-mode -> none")
            else:
                log(f"      get-lock-mode -> {mode!r} (still set)")
        except bridge.BridgeError:
            pass

        # 3) Wake + dismiss the keyguard so the home screen shows.
        run_cmd("wake screen", "input keyevent 82")
        run_cmd("dismiss keyguard", "wm dismiss-keyguard")

        # 4) Fallback for older Android (<8) / Samsung settings keys.
        run_cmd("legacy: disable lockscreen", "settings put secure lockscreen.disabled 1")
        run_cmd("legacy: disable keyguard",
                "settings put global lockscreen_disabled 1")

        log("")
        log("State AFTER removal:")
        after = _log_lock_state(log)
        log("")

        pt_gone = after.get("password_type") in _NO_LOCK_CODES
        disabled_flag = after.get("disabled") is True
        lsd_gone = after.get("lockscreen_disabled") == "1"
        lock_gone = pt_gone or disabled_flag or lsd_gone or ok_clear
        still_stored = after.get("dumpsys_stored") is True
        changed = (before.get("password_type") or "") != (after.get("password_type") or "")

        log("=" * 60)
        if lock_gone:
            if changed:
                log("RESULT: lock removed - the phone should now boot straight to the")
                log("        launcher. Reboot to confirm: 'adb reboot'")
            else:
                log("RESULT: lock cleared/disabled - reboot to confirm: 'adb reboot'")
        else:
            log("RESULT: lock could NOT be changed over ADB.")
            if still_stored:
                log("  dumpsys lock_settings still reports a stored credential.")
            log("  The commands ran but the lock is still reported as set.")
            if not ok_set_disabled:
                log("   - 'locksettings set-disabled true' itself failed - paste the")
                log("     'Exception ...' line above to get a targeted fix.")
            log("  Possible reasons:")
            log("   - Screen is still locked at keyguard: ADB is authorized but the")
            log("     phone must be UNLOCKED once for `locksettings` to apply -")
            log("     unlock it manually, re-run this flow.")
            log("   - A password/PIN needs --old <your-credential>; if you know the")
            log("     PIN/pattern/password, re-run the flow (it tries --old variants,")
            log("     and we can hard-code the real value).")
            log("   - Device policy (Knox MDM / Exchange) forbids changing the lock.")
            log("   - FRP is active (this is not a screen lock) - use FRP bypass.")
            log("  Alternatives: 'screen lock remove (Recovery)' (factory reset,")
            log("  wipes data) or combination firmware via Odin.")
        log("=" * 60)

    steps = [Step("screen_lock_locksettings", _run)]
    return Flow("screen lock remove (ADB locksettings, Android 8/9)", steps)


def flow_screen_lock_remove():
    """Remove screen lock (pattern, PIN, password) via ADB.
    
    This method attempts to clear screen lock settings using ADB commands.
    NOTE: This method has LIMITED success on modern Android devices due to:
    - Device encryption (Android 10+)
    - Samsung Knox security
    - File system permissions (ADB runs as unprivileged user)
    
    For reliable screen lock removal, use the download mode method or factory reset.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("SCREEN LOCK REMOVAL - ADB METHOD")
        log("=" * 60)
        log("WARNING: This method has limited success on modern devices.")
        log("For reliable results, use download mode or factory reset.")
        log("")
        log("PHONE: USB debugging must be on and this PC authorized")
        log("  (plug in, tap 'Always allow' on the 'Allow USB debugging' dialog).")
        if not _wait_for_adb(ctx, log, timeout=60):
            raise RuntimeError("no adb device appeared - enable USB debugging first")
        
        serial = ctx.get("serial", "")
        log(f"Device serial: {serial}")
        
        # Check Android version to determine the appropriate method
        try:
            android_version = bridge.adb_shell("getprop ro.build.version.release", timeout=10).strip()
            api_level = bridge.adb_shell("getprop ro.build.version.sdk", timeout=10).strip()
            log(f"Android version: {android_version} (API {api_level})")
        except bridge.BridgeError:
            log("Could not detect Android version, trying all methods...")
            android_version = "unknown"
            api_level = "0"
        
        # Check if device is encrypted
        try:
            encrypted = bridge.adb_shell("getprop ro.crypto.state", timeout=10).strip()
            log(f"Device encryption: {encrypted}")
            if encrypted == "encrypted":
                log("WARNING: Device is encrypted. ADB methods will NOT work.")
                log("Use download mode method or factory reset instead.")
        except bridge.BridgeError:
            pass
        
        log("")
        
        # Try multiple methods used by commercial tools
        methods_tried = []
        methods_succeeded = []
        
        # Method 1: Clear lock pattern via settings commands (works on some devices)
        log("Method 1: Clear lock via settings commands...")
        try:
            commands = [
                ("Clear lock pattern", "settings put secure lock_pattern_enable 0"),
                ("Clear lock password", "settings put secure lock_password_enable 0"),
                ("Clear PIN biometric", "settings put secure lock_biometric_weak 0"),
                ("Disable keyguard", "settings put global lockscreen_disabled 1"),
            ]
            
            method_success = False
            for label, cmd in commands:
                try:
                    out = bridge.adb_shell(cmd, timeout=15)
                    if out and "Error" not in out:
                        log(f"  {label}: Success")
                        method_success = True
                    else:
                        log(f"  {label}: No effect")
                except bridge.BridgeError as e:
                    log(f"  {label}: Failed - {e}")
            
            if method_success:
                methods_succeeded.append("Settings commands")
            methods_tried.append("Settings commands")
        except bridge.BridgeError as e:
            log(f"  Method 1 failed: {e}")
        
        # Method 2: Clear lockscreen data (may work on some Samsung devices)
        log("")
        log("Method 2: Clear lockscreen data...")
        try:
            commands = [
                ("Clear settings data", "pm clear com.android.settings"),
                ("Clear system UI data", "pm clear com.android.systemui"),
            ]
            
            method_success = False
            for label, cmd in commands:
                try:
                    out = bridge.adb_shell(cmd, timeout=15)
                    if out and "Success" in out:
                        log(f"  {label}: Success")
                        method_success = True
                    else:
                        log(f"  {label}: No effect")
                except bridge.BridgeError as e:
                    log(f"  {label}: Failed - {e}")
            
            if method_success:
                methods_succeeded.append("Clear app data")
            methods_tried.append("Clear app data")
        except bridge.BridgeError as e:
            log(f"  Method 2 failed: {e}")
        
        # Method 3: Try to remove lock databases (requires root, will likely fail)
        log("")
        log("Method 3: Remove lock databases (requires root, will likely fail)...")
        try:
            db_files = [
                "/data/system/locksettings.db",
                "/data/system/gesture.key",
                "/data/system/password.key",
            ]
            
            method_success = False
            for db_file in db_files:
                try:
                    result = bridge.adb_shell(f"rm -f {db_file}", timeout=15)
                    log(f"  Removed: {db_file}")
                    method_success = True
                except bridge.BridgeError:
                    log(f"  No permission: {db_file}")
            
            if method_success:
                methods_succeeded.append("Database removal")
            methods_tried.append("Database removal")
        except bridge.BridgeError as e:
            log(f"  Method 3 failed: {e}")
        
        log("")
        log("=" * 60)
        log(f"Methods tried: {', '.join(methods_tried)}")
        log(f"Methods succeeded: {', '.join(methods_succeeded) if methods_succeeded else 'None'}")
        log("=" * 60)
        
        if methods_succeeded:
            log("Some commands executed successfully.")
            log("IMPORTANT: Reboot the device NOW for changes to take effect.")
            log("")
            log("After reboot:")
            log("  - The screen lock MAY be removed (not guaranteed)")
            log("  - If lock still present, device encryption is blocking the method")
            log("  - Try download mode method or factory reset")
        else:
            log("WARNING: All methods failed or had no effect.")
            log("This is normal for modern Android devices due to:")
            log("  - Device encryption (Android 10+)")
            log("  - Samsung Knox security")
            log("  - File system permissions")
            log("")
            log("RECOMMENDED SOLUTIONS:")
            log("  1. Use download mode -> flash a combination firmware, then ADB clear")
            log("  2. Perform factory reset (will wipe data)")
            log("  3. Use commercial tool with proprietary Samsung payloads")
            log("")
            log("To reboot now, run: adb reboot")

    steps = [Step("screen_lock_remove", _run)]
    return Flow("screen lock remove (ADB)", steps)


def flow_screen_lock_download():
    """Screen lock removal via download mode - REAL implementation: flashes a
    combination firmware with odin4 (the only way to get adb on a locked
    phone), then clears the lock over adb `locksettings`.

    Replaces the old fake HID "payload database": there are no generic HID
    unlock payloads - sending unverified bytes risks soft-bricking the phone.
    The method the commercial tools actually use is combination firmware + adb.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("SCREEN LOCK REMOVAL - DOWNLOAD MODE (combo firmware + adb)")
        log("=" * 60)
        up = False
        try:
            up = any(d["state"] == "device" for d in bridge.adb_status())
        except bridge.BridgeError:
            pass
        if not up:
            log("No adb yet - flashing combination firmware to get adb ...")
            log("")
            if not _combo_flash_to_adb(ctx, log, purpose="screen lock removal"):
                raise RuntimeError(
                    "adb did not come up after the flash - see the notes above"
                )
        log("")
        log("adb is online on the combination build - clearing the lock ...")
        flow_screen_lock_locksettings().run(ctx, log)

    steps = [Step("screen_lock_download_combo", _run)]
    return Flow("screen lock remove (download mode - combo firmware + adb)", steps)


def flow_screen_lock_csc():
    """Screen lock removal that adapts to the device state - NOT Odin-only.
    When an authorized adb device is online it clears the lock over adb
    (locksettings, no Odin). Otherwise it flashes the model's CSC slot in
    download mode / Samsung BROM / MediaTek DA, which performs the factory
    reset that removes the lock. The CSC is model-specific and is refused when
    it does not match the connected device's PIT (A14 CSC only on A14, A06
    CSC only on A06)."""

    def _run(ctx, log):
        log("=" * 60)
        log("SCREEN LOCK REMOVAL (adb first, CSC flash fallback)")
        log("=" * 60)
        try:
            adb_ok = any(d["state"] == "device" for d in bridge.adb_status())
        except bridge.BridgeError:
            adb_ok = False
        if adb_ok:
            log("  Authorized adb device online - clearing the lock over adb")
            log("  (no Odin / download mode needed)...")
            flow_screen_lock_locksettings().run(ctx, log)
            return True
        log("  No adb (or not authorized). Falling back to the CSC factory-reset flash.")
        log("  The CSC slot wipes /data and clears FRP. The lock lives in /data,")
        log("  so after this flash the phone boots to setup with no lock.")
        log("")
        csc = _find_slot_tar("CSC") or _find_slot_tar("HOME_CSC")
        if not csc:
            raise RuntimeError(
                "No CSC archive found. Put the model's CSC_*.tar.md5 in "
                "~/Downloads (or set CSC_TAR=/path/to/file.tar) and retry."
            )
        log(f"  CSC archive: {os.path.basename(csc)} ({os.path.getsize(csc) >> 20} MB)")
        ok, msg = _tar_md5_valid(csc)
        if not ok:
            raise RuntimeError(f"CSC archive failed validation: {msg}")

        odin4 = _find_odin4()
        if not odin4:
            raise RuntimeError(
                "odin4 binary not found. Run bash /usr/share/flashpilot/scripts/"
                "fetch-odin4.sh (or put odin4 in ~/.local/bin) and retry."
            )

        d = _download_mode_device()
        if not d:
            log("Waiting for device in download mode...")
            d = _wait_download_mode(log, timeout=30)
        if not d:
            raise RuntimeError(
                "Device not in download mode. Power off, hold Vol Down + Power, "
                "then press Vol Up."
            )
        target = f"04e8:{d['pid']:04x}@{d['bus']}:{d['address']}"

        # Model gate: a CSC is model-specific. Verify against the device's own
        # PIT before flashing anything.
        csc_model = _model_from_firmware_name(os.path.basename(csc))
        device_model = ctx.get("device_pit_model")
        if not device_model:
            import tempfile
            pit_path = os.path.join(tempfile.gettempdir(), "samsung_dev.pit")
            try:
                bridge.odin_pit(target, pit_path, timeout=120)
                device_model = pit.parse_model(open(pit_path, "rb").read())
            except (bridge.BridgeError, OSError) as e:
                log(f"  (device PIT read failed - model gate skipped: {e})")
        if csc_model:
            log(f"  CSC model:          {csc_model}")
        if device_model:
            log(f"  Device model (PIT): {device_model}")
        match = _models_match(device_model, csc_model)
        if match is False:
            raise RuntimeError(
                f"Model mismatch: the CSC is for '{csc_model}' but the connected "
                f"device PIT says '{device_model}'. Refusing - a CSC must only be "
                "used on its matching model."
            )

        log("")
        log("  WARNING: this performs a FACTORY RESET - all user data is wiped")
        log("  and Google FRP is cleared.")
        log("")
        try:
            res = bridge.usb_detach_kernel(target, timeout=15)
            log(f"  Kernel drivers detached: {res.get('detached')}")
        except bridge.BridgeError as e:
            log(f"  (kernel detach skipped: {e})")

        log("Flashing CSC only (no AP/BL/CP)... DO NOT disconnect the cable!")
        cmd = [odin4, "-s", csc] + _odin4_reboot() + _odin4_verbose()
        log(f"Executing: {' '.join(cmd)}")
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        out = (proc.stdout or "") + (proc.stderr or "")
        if out:
            log(out[-3500:])
        if proc.returncode != 0:
            raise RuntimeError(
                f"CSC flash failed (rc={proc.returncode}). {_explain_odin4_failure(out)}"
            )
        log("")
        log("  CSC flash completed. The phone is factory-reset: the screen lock is")
        log("  gone and it boots to the setup wizard.")

    steps = [Step("screen_lock_csc", _run)]
    return Flow("screen lock remove (adb or CSC flash - factory reset)", steps)


def flow_recovery():
    """Recovery mode: stock recovery is for flashing/sideloading, not FRP."""

    def _run(ctx, log):
        log("Recovery mode (stock recovery) selected.")
        log("Enter with: power off, then Vol-Up + Home + Power (A-series/older) or")
        log("  Vol-Up + Power (no-Home-button models). Wipe/apply-from-adb menu.")
        log("In recovery, `adb sideload` works but `adb shell` is limited, so FRP")
        log("bypass here is not the supported path - use MTP/ADB mode instead.")
        d = mtp.find_samsung()
        if d:
            log(f"  usb: 04e8:{d['pid']:04x}@bus{d['bus']}:addr{d['address']}")
        else:
            log("  usb: no Samsung device detected")
        log(f"  adb: {bridge.adb_devices() or 'none'}")

    steps = [Step("recovery_info", _run)]
    return Flow("recovery mode", steps)


# ---------------------------------------------------------------------------
# MDM / device-owner unlock: shared constants and helpers.
#
# The ADB flows below are built like a commercial MDM unlocker: a pre-flight
# + full inventory, an ordered least-destructive-first removal ladder, a
# post-unlock verification verdict (UNLOCKED / PARTIAL / FAILED) and a saved
# report file. Everything here is real adb shell work (dpm / cmd device_policy
# / pm / settings / locksettings / su) - there is no fake "server-side" step.
# ---------------------------------------------------------------------------

# Package-name markers that identify third-party management agents.
_MDM_MARKERS = (
    "knox", "kme", "kgclient", "kg.client", "dpc", "mdm", "mobix",
    "licensemanagement", "suremdm", "miradore", "intune", "companyportal",
    "airwatch", "workspaceone", "zerotouch", "deviceowner", "managed",
    "soti", "maas360", "mobileiron", "citrix", "hexnode", "manageengine",
    "jamf", "zebra", "enterprise", "surelock", "testdpc", "oobconfig",
    "samsungems", "wcs", "sbrowser",
)

# Known commercial DPC packages -> vendor name (for the report).
_MDM_KNOWN_DPC = {
    "com.samsung.knox.kme": "Samsung KME (Knox Mobile Enrollment)",
    "com.samsung.android.kgclient": "Samsung KG (factory/KG lock)",
    "com.samsung.android.mdm": "Samsung MDM",
    "com.samsung.android.mdmagent": "Samsung MDM Agent",
    "com.samsung.android.knox.push": "Samsung Knox Push",
    "com.ldmobix.licensemanagement": "Mobix",
    "com.managed.profile.suremdm": "42Gears SureMDM",
    "com.miradore.management": "Miradore",
    "com.microsoft.intune": "Microsoft Intune",
    "com.microsoft.windowsintune.companyportal": "Microsoft Intune Company Portal",
    "com.airwatch.androidagent": "VMware AirWatch / Workspace ONE",
    "com.airwatch.mdm": "VMware AirWatch / Workspace ONE",
    "com.vmware.horizon": "VMware Workspace ONE",
    "com.soti.mobile.control": "SOTI MobiControl",
    "com.fiberlink.maas360": "IBM MaaS360",
    "com.mobileiron": "MobileIron",
    "com.citrix.mdx": "Citrix Endpoint Management",
    "com.hexnode.mdm": "Hexnode MDM",
    "com.manageengine.mobilecentral": "ManageEngine Mobile Central",
    "com.jamf.management": "Jamf Pro",
    "com.zebra.mdm": "Zebra MDM",
    "com.symbol.mdm": "Zebra (Symbol) MDM",
    "com.afwsamples.testdpc": "Test DPC (Google demo)",
    "com.google.android.apps.work.oobconfig": "Google Zero-Touch / Work",
    "com.google.android.apps.work": "Google Device Policy",
}

# Policy/lock DB files the root and recovery paths delete to drop a persisted
# device-owner record (Samsung keeps it in device_policies.xml / dpm.sqlite).
_MDM_POLICY_FILES = (
    "/data/system/device_policies.xml",
    "/data/system/device_policies.bak",
    "/data/system/device_policies_backup.xml",
    "/data/system/users/0/device_policies.xml",
    "/data/system/users/0/device_policies_backup.xml",
    "/data/system/dpm.sqlite",
    "/data/system/dpm.sqlite-wal",
    "/data/system/dpm.sqlite-shm",
)

# Device identity + security props used by the MDM report. Key = short name.
_MDM_PROPS = {
    "ro.product.model": "model",
    "ro.product.brand": "brand",
    "ro.product.manufacturer": "manufacturer",
    "ro.build.version.release": "android",
    "ro.build.version.sdk": "sdk",
    "ro.build.version.security_patch": "security_patch",
    "ro.build.fingerprint": "build",
    "ro.crypto.state": "encryption",
    "ro.boot.verifiedbootstate": "verified_boot",
    "ro.boot.vbmeta.device_state": "bootloader",
    "ro.boot.secureboot.lockstate": "secure_boot",
    "sys.oem_unlock_allowed": "oem_unlock",
    "ro.boot.warranty_bit": "warranty_bit",
    "ro.vendor.boot.warranty_bit": "warranty_bit_vendor",
    "ro.knox.sdk.version": "knox_sdk",
    "ro.config.knox": "knox",
    "ro.boot.rp_sw_type": "rp_sw_type",
    "ro.boot.kgstatus": "kg_status",
}


def _mdm_props(log):
    """Read device identity + security props into a dict {short: value} and
    print a compact device report. Used as the pre-flight of every MDM flow."""
    out = {}
    for prop, key in _MDM_PROPS.items():
        out[key] = _adb_getprop(prop)
    log(f"  Device: {out['model'] or 'unknown'} "
        f"({out['brand'] or '?'} / {out['manufacturer'] or '?'})")
    log(f"  Android: {out['android'] or 'unknown'} (API {out['sdk'] or '?'})"
        + (f", patch {out['security_patch']}" if out["security_patch"] else ""))
    log(f"  Encryption: {out['encryption'] or 'unknown'}")
    bits = []
    if out["bootloader"]:
        bits.append(f"bootloader={out['bootloader']}")
    if out["verified_boot"]:
        bits.append(f"verifiedboot={out['verified_boot']}")
    if out["oem_unlock"] != "":
        bits.append(f"oem_unlock={out['oem_unlock']}")
    if out["warranty_bit"] != "" or out["warranty_bit_vendor"] != "":
        bits.append("warranty_bit=" + (out["warranty_bit"] or out["warranty_bit_vendor"]))
    if bits:
        log("  " + "  ".join(bits))
    if out["knox_sdk"] or out["knox"]:
        log(f"  Knox: SDK {out['knox_sdk'] or '?'} "
            f"(config {out['knox'] or '?'})")
    return out


def _mdm_scan(sh, log):
    """Full management inventory through the caller's `sh` wrapper.
    sh(cmd, timeout=..., quiet=...) -> (ok, text). Returns a dict:
      owners:     {user_id: [component, ...]}
      admins:     {package: component}
      users:      {user_id: {name, flags}}
      work_users: set(user_id)   (secondary users = managed profiles)
      mdm_pkgs:   set(package)   (owners/admins + marker/known-DPC matches)
      vendors:    {package: vendor}
    """
    r = {"owners": {}, "admins": {}, "users": {}, "work_users": set(),
         "mdm_pkgs": set(), "vendors": {}}

    for cmd in ("dpm list-owners", "cmd device_policy list-owners"):
        ok, text = sh(cmd, quiet=True)
        if not ok:
            continue
        for line in text.splitlines():
            m = re.search(
                r"^(?:device|profile)\s+owner:\s*(\S+)\s*\(userId:\s*(\d+)\)",
                line, re.I)
            if m:
                r["owners"].setdefault(m.group(2), []).append(m.group(1))

    for cmd in ("dpm list-active-admins", "cmd device_policy list-admin"):
        ok, text = sh(cmd, quiet=True)
        if not ok:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            found = [m.group(1)
                     for m in re.finditer(r"ComponentInfo\{([^}]+)\}", line)]
            if not found:
                # Plain list form: "Admins: [com.x/.y]" (old dpm output).
                comp = line.split(":", 1)[1].strip("[] \t") if ":" in line else line
                if comp and "/" in comp and "{" not in comp:
                    found = [comp]
            for comp in found:
                comp = comp.strip()
                if comp:
                    r["admins"].setdefault(comp.split("/")[0], comp)

    ok, text = sh("pm list users", quiet=True)
    if ok:
        for line in text.splitlines():
            for m in re.finditer(r"UserInfo\{(\d+):([^:]+):([^}]*)\}", line):
                uid = m.group(1)
                r["users"][uid] = {"name": m.group(2), "flags": m.group(3)}
                if uid != "0":
                    r["work_users"].add(uid)

    ok, text = sh("pm list packages -3", timeout=30, quiet=True)
    if ok:
        for line in text.splitlines():
            pkg = line.replace("package:", "").strip()
            if not pkg:
                continue
            low = pkg.lower()
            for known, vendor in _MDM_KNOWN_DPC.items():
                if pkg == known or pkg.startswith(known):
                    r["vendors"][pkg] = vendor
                    r["mdm_pkgs"].add(pkg)
            if any(m in low for m in _MDM_MARKERS):
                r["mdm_pkgs"].add(pkg)

    for comps in r["owners"].values():
        for c in comps:
            pkg = c.split("/")[0]
            r["mdm_pkgs"].add(pkg)
            if pkg in _MDM_KNOWN_DPC:
                r["vendors"].setdefault(pkg, _MDM_KNOWN_DPC[pkg])
    for comp in r["admins"].values():
        pkg = comp.split("/")[0]
        r["mdm_pkgs"].add(pkg)
        if pkg in _MDM_KNOWN_DPC:
            r["vendors"].setdefault(pkg, _MDM_KNOWN_DPC[pkg])
    return r


def _mdm_report_lines(r, props):
    """Build the analysis report as a list of text lines.
    Returns (lines, managed_bool)."""
    lines = []
    lines.append("=" * 60)
    lines.append("MDM / DEVICE-OWNER ANALYSIS REPORT")
    lines.append("=" * 60)
    lines.append(f"Device         : {props['model'] or 'unknown'} "
                f"({props['brand'] or '?'} / {props['manufacturer'] or '?'})")
    lines.append(f"Android        : {props['android'] or 'unknown'} "
                f"(API {props['sdk'] or '?'})")
    if props["security_patch"]:
        lines.append(f"Security patch : {props['security_patch']}")
    if props["build"]:
        lines.append(f"Build          : {props['build'][:90]}")
    lines.append(f"Encryption     : {props['encryption'] or 'unknown'}")
    boot = []
    if props["bootloader"]:
        boot.append(f"bootloader={props['bootloader']}")
    if props["verified_boot"]:
        boot.append(f"verifiedboot={props['verified_boot']}")
    if props["oem_unlock"] != "":
        boot.append(f"oem_unlock={props['oem_unlock']}")
    if props["warranty_bit"] != "" or props["warranty_bit_vendor"] != "":
        boot.append("warranty_bit="
                    + (props["warranty_bit"] or props["warranty_bit_vendor"]))
    if boot:
        lines.append("Boot           : " + "  ".join(boot))
    if props["knox_sdk"] or props["knox"]:
        lines.append(f"Knox           : SDK {props['knox_sdk'] or '?'} "
                     f"(config {props['knox'] or '?'})")
    lines.append("")
    lines.append("Management state:")
    managed = bool(r["owners"] or r["admins"] or r["work_users"] or r["mdm_pkgs"])
    if r["owners"]:
        for uid, comps in sorted(r["owners"].items()):
            for c in comps:
                lines.append(f"  Device/profile owner (user {uid}): {c}")
    if r["admins"]:
        for pkg, comp in sorted(r["admins"].items()):
            lines.append(f"  Active admin                : {comp}")
    if r["work_users"]:
        for u in sorted(r["work_users"]):
            info = r["users"].get(u, {})
            lines.append(f"  Work/secondary user {u}     : "
                         f"{info.get('name', '')}  ({info.get('flags', '')})")
    if r["mdm_pkgs"]:
        for p in sorted(r["mdm_pkgs"]):
            vendor = r["vendors"].get(p, "")
            lines.append(f"  MDM/DPC package              : {p}"
                         + (f"  [{vendor}]" if vendor else ""))
    if not managed:
        lines.append("  None - the device is NOT managed.")
    lines.append("")
    return lines, managed


def _mdm_save_report(lines):
    """Persist the report to mdm_reports/ and return the path ('' on failure)."""
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        out_dir = os.path.normpath(os.path.join(base, "..", "..", "mdm_reports"))
        os.makedirs(out_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(out_dir, f"mdm_report_{stamp}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return path
    except OSError:
        return ""


def _mdm_verdict(log, v, vmanaged):
    """Print the professional post-unlock verdict for a re-scan `v`."""
    log("=" * 60)
    if not vmanaged:
        log("VERDICT: UNLOCKED - the device is no longer managed.")
        log("  Reboot (`adb reboot`) to finish, then set it up normally.")
        log("  If a Google/FRP screen appears, run the FRP bypass flows.")
    elif not (v["owners"] or v["admins"] or v["work_users"]):
        log("VERDICT: PARTIAL - owners/admins are gone but DPC packages remain")
        log("  installed (they are now disabled). Reboot, then re-run this flow")
        log("  or uninstall them from Settings -> Apps.")
    else:
        log("VERDICT: FAILED / PARTIAL - management state persists.")
        log("  This build gates `dpm` behind the shell user. Use the")
        log("  recovery-mode flow (no wipe) or root (Magisk) to delete the")
        log("  policy file directly.")
    log("=" * 60)


def flow_mdm_diagnostics():
    """Professional pre-flight MDM analysis (the 'diagnostics' tab a commercial
    unlocker shows before touching the device). Makes NO changes: reads the
    device, scans the full management state, writes a report file and
    recommends the unlock method for the detected management."""

    def _run(ctx, log):
        log("=" * 60)
        log("MDM DIAGNOSTICS / ANALYSIS")
        log("=" * 60)
        up = False
        try:
            up = any(d["state"] == "device" for d in bridge.adb_status())
        except bridge.BridgeError:
            pass
        if not up:
            log("No authorized ADB device yet - enabling USB debugging ...")
            _try_enable_adb(ctx, log)
            log("")
        log("Waiting for an AUTHORIZED ADB device ...")
        if not _wait_for_adb(ctx, log, timeout=90):
            raise RuntimeError("no adb device appeared - enable USB debugging first")

        def sh(cmd, timeout=30, quiet=True):
            try:
                out = bridge.adb_shell(cmd, timeout=timeout) or ""
            except bridge.BridgeError:
                return False, ""
            return True, out.strip()

        props = _mdm_props(log)
        log("")
        log("Scanning management state ...")
        r = _mdm_scan(sh, log)
        lines, managed = _mdm_report_lines(r, props)
        for ln in lines:
            log(ln)

        log("Recommended unlock path:")
        recs = []
        if managed:
            if r["owners"] or r["admins"]:
                recs.append("ADB smart unlock  (removes device/profile owner + admins)")
            if r["work_users"]:
                recs.append("ADB smart unlock  (also removes the work profiles)")
            if r["mdm_pkgs"] and not (r["owners"] or r["admins"]):
                recs.append("ADB smart unlock  (disables/clears the DPC packages)")
            recs.append("Recovery (no wipe) if ADB is blocked or the lock returns")
            recs.append("QR re-provision   to enroll a neutral DPC after a factory reset")
        else:
            recs.append("None - the device is clean; nothing to unlock.")
        for i, rec in enumerate(recs, 1):
            log(f"  {i}. {rec}")

        path = _mdm_save_report(lines)
        if path:
            log("")
            log(f"Report saved: {path}")

    steps = [Step("mdm_diagnostics", _run)]
    return Flow("mdm diagnostics / analysis", steps)


def flow_mdm_unlock_comprehensive():
    """Aggressive MDM / device-owner removal over ADB - the 'deep' path.

    Everything the smart flow does, plus: force-stops AND uninstalls the DPC
    packages, clears every management receiver it can find via cmd/dpm, handles
    Samsung KME / Knox-enrollment leftovers, clears the persisted policy DB
    (with root), and verifies the result with a professional
    UNLOCKED / PARTIAL / FAILED verdict. Ordered least-destructive-first; a
    phone that is already locked is handled by removing the management first
    and only then clearing the enforced lockscreen.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("MDM UNLOCK - COMPREHENSIVE / DEEP (ADB)")
        log("=" * 60)
        up = False
        try:
            up = any(d["state"] == "device" for d in bridge.adb_status())
        except bridge.BridgeError:
            pass
        if not up:
            log("No authorized ADB device yet - enabling USB debugging ...")
            _try_enable_adb(ctx, log)
            log("")
        log("Waiting for an AUTHORIZED ADB device ...")
        if not _wait_for_adb(ctx, log, timeout=90):
            raise RuntimeError("no adb device appeared - enable USB debugging first")

        def sh(cmd, timeout=30, quiet=False):
            if not quiet:
                log(f"  > adb shell {cmd}")
            try:
                out = bridge.adb_shell(cmd, timeout=timeout) or ""
            except bridge.BridgeError as e:
                if not quiet:
                    log(f"      ERROR: {e}")
                return False, ""
            text = out.strip()
            if text and not quiet:
                log(f"      {text[:500]}")
            return True, text

        # 0. pre-flight
        log("")
        log("Step 0/9 - pre-flight ...")
        props = _mdm_props(log)
        root = False
        ok, text = sh("su -c id", timeout=8)
        root = ok and "uid=0" in text
        log(f"  root available: {'yes' if root else 'no'}")
        log("")

        # 1. inventory
        log("Step 1/9 - inventory ...")
        r = _mdm_scan(sh, log)
        lines, managed = _mdm_report_lines(r, props)
        for ln in lines:
            log(ln)
        if not managed:
            log("Nothing to unlock - the device is not managed.")
            _mdm_save_report(lines)
            return
        log("")

        owners = r["owners"]
        admins = r["admins"]
        work = r["work_users"]
        pkgs = r["mdm_pkgs"]

        # 2. admins + owners via every supported CLI
        log("Step 2/9 - remove active admins and owners ...")
        targets = sorted(set(admins.values())
                         | {c for cs in owners.values() for c in cs})
        for comp in targets:
            pkg = comp.split("/")[0]
            log(f"  -> {comp}")
            sh(f"cmd device_policy remove-admin --user 0 {comp}",
               timeout=30, quiet=True)
            sh(f"dpm remove-active-admin {comp}", timeout=30, quiet=True)
            sh(f"am force-stop {pkg}", timeout=15, quiet=True)
            sh(f"pm clear --user 0 {pkg}", timeout=30, quiet=True)

        ok, text = sh("cmd device_policy get-device-owner", timeout=15, quiet=True)
        if ok and text.strip():
            comp = text.strip()
            log(f"  -> residual device owner: {comp}")
            sh(f"cmd device_policy remove-active-admin --user 0 {comp}",
               timeout=30, quiet=True)
            sh(f"dpm remove-active-admin {comp}", timeout=30, quiet=True)

        # 3. work profiles (no wipe)
        log("Step 3/9 - remove work profiles ...")
        for uid in sorted(work):
            log(f"  -> user {uid}")
            sh(f"pm remove-user {uid}", timeout=30, quiet=True)

        # 4. DPC packages - deep: disable, clear AND uninstall
        log("Step 4/9 - disable, clear and uninstall DPC packages ...")
        for pkg in sorted(pkgs):
            vendor = r["vendors"].get(pkg, "")
            log(f"  -> {pkg}" + (f"  [{vendor}]" if vendor else ""))
            sh(f"am force-stop {pkg}", timeout=15, quiet=True)
            sh(f"pm disable-user --user 0 {pkg}", timeout=30, quiet=True)
            sh(f"pm uninstall --user 0 {pkg}", timeout=30, quiet=True)
            sh(f"pm clear --user 0 {pkg}", timeout=30, quiet=True)

        # 5. Samsung KME / Knox-enrollment leftovers
        samsung_kme = sorted(p for p in pkgs
                             if "kme" in p.lower() or "kgclient" in p.lower()
                             or p == "com.samsung.android.mdm")
        if samsung_kme:
            log("Step 5/9 - Samsung KME / Knox-enrollment cleanup ...")
            for pkg in samsung_kme:
                log(f"  -> {pkg}")
                sh(f"am force-stop {pkg}", timeout=15, quiet=True)
                sh(f"pm clear --user 0 {pkg}", timeout=30, quiet=True)
                sh(f"pm disable-user --user 0 {pkg}", timeout=30, quiet=True)
            sh("dpm remove-active-admin com.samsung.knox.kme",
               timeout=30, quiet=True)
            sh("cmd device_policy remove-admin --user 0 "
               "com.samsung.knox.kme/com.samsung.knox.kme",
               timeout=30, quiet=True)
            log("  NOTE: KME devices often re-enroll from the server. After this")
            log("  flow, disable 'Knox enrollment' in Settings -> Accounts, or")
            log("  use the QR re-provision (neutral DPC) after a factory reset.")

        # 6. persisted policy files (root) + DPMS clear
        log("Step 6/9 - clear persisted policy files ...")
        if root:
            for p in _MDM_POLICY_FILES:
                sh(f"su -c 'rm -rf {p}'", timeout=15, quiet=True)
            log("  removed policy files (root).")
        else:
            log("  no root - relying on cmd/dpm removal.")
        sh("cmd device_policy stop-clear-data --user 0", timeout=30, quiet=True)

        # 7. provisioning flags
        log("Step 7/9 - reset provisioning flags ...")
        for s, k, v in (
            ("global", "device_provisioned", "1"),
            ("secure", "user_setup_complete", "1"),
            ("global", "setup_wizard_has_run", "1"),
            ("global", "package_verifier_enable", "1"),
            ("global", "verify_optional_upgrade", "1"),
        ):
            sh(f"settings put {s} {k} {v}", timeout=15, quiet=True)

        # 8. enforced lockscreen
        log("Step 8/9 - clear enforced lockscreen ...")
        sh("locksettings set-disabled true", timeout=15, quiet=True)
        sh("locksettings clear --old 0000", timeout=15, quiet=True)
        sh("locksettings clear --old 1234", timeout=15, quiet=True)

        # 9. verify + verdict + report
        log("Step 9/9 - verify ...")
        log("")
        v = _mdm_scan(sh, log)
        vlines, vmanaged = _mdm_report_lines(v, props)
        for ln in vlines:
            log(ln)
        log("")
        _mdm_verdict(log, v, vmanaged)
        path = _mdm_save_report(lines)
        if path:
            log(f"Report: {path}")

    steps = [Step("mdm_unlock_comprehensive", _run)]
    return Flow("mdm / device-owner unlock - comprehensive / deep", steps)


def flow_mdm_qr():
    """Generate Android Enterprise (DPC) provisioning QR codes.

    MDM enrollment on modern Android is driven by a provisioning QR: the
    setup wizard scans it and enrolls a Device Policy Controller as device
    owner. A tool that can WRITE that QR can also UN-ENROLL by re-provisioning
    the device with a neutral/benign DPC (Test DPC) after a factory reset,
    replacing the corporate controller.

    This flow builds the standard provisioning JSON
    (android.app.extra.PROVISIONING_* extras) and renders QR PNGs via `segno`:

      provisioning_qr_unenroll_testdpc.png - NEUTRAL DPC (Test DPC): the
                                             un-enroll QR - drops the corporate
                                             MDM after a factory reset
      provisioning_qr_google.png           - Google's demo DPC (oobconfig)
      provisioning_qr_custom.png           - only if MDM_DPC_COMPONENT is set

    Environment overrides (professional workflow):
      MDM_DPC_COMPONENT=com.vendor.app/.Receiver   custom DPC component
      MDM_DPC_APK_URL=https://...apk               custom DPC APK download source
      MDM_DPC_CERT_HASH=base64:sha256=...          optional APK certificate hash
    """

    def _run(ctx, log):
        log("=" * 60)
        log("MDM QR CODE GENERATOR (Android Enterprise provisioning)")
        log("=" * 60)
        log("Builds provisioning QRs used by the setup wizard to enroll a")
        log("Device Policy Controller - offline, no device needed. Scanning a")
        log("NEUTRAL-DPC QR after a factory reset removes the corporate MDM.")
        log("")

        try:
            import segno
        except ImportError:
            log("ERROR: the `segno` package is not installed.")
            log("  Fix:  .venv/bin/pip install segno")
            raise RuntimeError("segno is required for QR generation")

        def build_payload(component, download_url, cert_hash):
            payload = {
                "android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT": component,
                "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION":
                    download_url,
                "android.app.extra.PROVISIONING_SKIP_ENCRYPTION": True,
                "android.app.extra.PROVISIONING_LEAVE_ALL_SYSTEM_APPS_ENABLED": True,
                "android.app.extra.PROVISIONING_SKIP_EDUCATION_SCREENS": True,
            }
            if cert_hash:
                payload[
                    "android.app.extra."
                    "PROVISIONING_DEVICE_ADMIN_PACKAGE_CERTIFICATE_HASH"] = cert_hash
            return payload

        def emit(component, name, out_dir, out_pngs):
            pkg = component.split("/")[0]
            url = (os.environ.get("MDM_DPC_APK_URL") or
                   "https://play.google.com/store/apps/details?id=" + pkg)
            cert = os.environ.get("MDM_DPC_CERT_HASH", "").strip()
            payload_json = json.dumps(build_payload(component, url, cert), indent=2)

            out_json = os.path.join(out_dir, f"provisioning_{name}.json")
            out_png = os.path.join(out_dir, f"provisioning_qr_{name}.png")
            with open(out_json, "w", encoding="utf-8") as fh:
                fh.write(payload_json)

            qr = segno.make_qr(payload_json, error="m", boost_error=True)
            try:
                qr.save(out_png, scale=10, border=4, dark="000000", light="ffffff")
            except Exception:  # noqa: BLE001  (older segno: no dark/light kwargs)
                qr.save(out_png, scale=10, border=4)

            out_pngs.append((name, out_png))
            log(f"  {name}:")
            log(f"    component : {component}")
            log(f"    download  : {url}")
            if cert:
                log(f"    cert hash : {cert}")
            log(f"    JSON      : {out_json}")
            log(f"    QR PNG    : {out_png}")

        out_dir = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "mdm_qr"))
        if os.path.exists(out_dir) and not os.access(out_dir, os.W_OK):
            # Installed (read-only) layouts fall back to a user-writable dir.
            out_dir = os.path.join(os.path.expanduser("~"), "flashpilot", "mdm_qr")
        os.makedirs(out_dir, exist_ok=True)
        log(f"Output: {out_dir}")
        log("")

        # All generated QR PNGs: (label, path) for the in-app viewer.
        out_pngs = []

        # Neutral un-enroll QR (Test DPC replaces the corporate controller).
        emit("com.afwsamples.testdpc/.DeviceAdminReceiver",
             "unenroll_testdpc", out_dir, out_pngs)
        # Google demo DPC (default provisioning controller).
        emit("com.google.android.apps.work.oobconfig/.DevAdminReceiver",
             "google", out_dir, out_pngs)
        # Optional custom DPC from the environment.
        custom = os.environ.get("MDM_DPC_COMPONENT", "").strip()
        if custom:
            emit(custom, "custom", out_dir, out_pngs)

        # Surface the QRs to the GUI: primary single path (backward compat) plus
        # the full list so the in-app viewer can switch between all of them.
        if out_pngs:
            ctx["mdm_qr_png"] = out_pngs[0][1]
            ctx["mdm_qr_pngs"] = out_pngs

        log("")
        log("How to use:")
        log("  1. Factory-reset the managed phone (recovery wipe).")
        log("  2. During setup, tap the 4-dot grid / 'QR code' button and scan")
        log("     the PNG with the phone camera.")
        log("  3. 'unenroll_testdpc' enrolls the benign Test DPC instead of the")
        log("     corporate controller - the phone is effectively unmanaged.")
        log("")
        log("Custom DPC (professional):")
        log("  MDM_DPC_COMPONENT=com.vendor.app/.Receiver")
        log("  MDM_DPC_APK_URL=https://...apk   MDM_DPC_CERT_HASH=base64:sha256=...")
        log("  e.g.  MDM_DPC_COMPONENT=com.afwsamples.testdpc/.DeviceAdminReceiver")
        log("        .venv/bin/python main.py  ->  mdm_qr")

    steps = [Step("mdm_qr", _run)]
    return Flow("mdm qr code generator (Android Enterprise)", steps)


def flow_mdm_unlock():
    """Professional MDM / device-owner unlock over ADB - the 'smart' path a
    commercial unlocker runs first.

    Samsung devices managed by an employer or a remote-management service
    (Knox/DPC, device-owner apps like Mobix, SureMDM, Samsung KME, Intune...)
    are locked to a management profile that also enforces a lockscreen and can
    survive a factory reset. With authorized ADB this flow runs an ordered,
    least-destructive-first ladder and then VERIFIES the result:

      0. pre-flight   - device report + root check
      1. inventory    - full management scan (owners/admins/work profiles/DPC)
      2. remove       - active admins + device/profile owners (every CLI)
      3. profiles     - drop work profiles without wiping
      4. DPC packages - force-stop + disable + clear + uninstall
      5. policy files - delete persisted device_policies.xml / dpm db (root)
      6. flags        - reset provisioning flags
      7. lockscreen   - clear the enforced credential (locksettings)
      8. verify       - re-scan and print a UNLOCKED / PARTIAL / FAILED verdict

    A report file is saved to mdm_reports/ like a professional tool.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("MDM UNLOCK - SMART (ADB)")
        log("=" * 60)
        up = False
        try:
            up = any(d["state"] == "device" for d in bridge.adb_status())
        except bridge.BridgeError:
            pass
        if not up:
            log("No authorized ADB device yet - enabling USB debugging ...")
            _try_enable_adb(ctx, log)
            log("")
        log("Waiting for an AUTHORIZED ADB device ...")
        if not _wait_for_adb(ctx, log, timeout=90):
            raise RuntimeError("no adb device appeared - enable USB debugging first")

        def sh(cmd, timeout=30, quiet=False):
            if not quiet:
                log(f"  > adb shell {cmd}")
            try:
                out = bridge.adb_shell(cmd, timeout=timeout) or ""
            except bridge.BridgeError as e:
                if not quiet:
                    log(f"      ERROR: {e}")
                return False, ""
            text = out.strip()
            if text and not quiet:
                log(f"      {text[:500]}")
            return True, text

        # 0. pre-flight
        log("")
        log("Step 0/8 - pre-flight ...")
        props = _mdm_props(log)
        root = False
        ok, text = sh("su -c id", timeout=8)
        root = ok and "uid=0" in text
        log(f"  root available: {'yes' if root else 'no'}")
        log("")

        # 1. inventory
        log("Step 1/8 - inventory ...")
        r = _mdm_scan(sh, log)
        lines, managed = _mdm_report_lines(r, props)
        for ln in lines:
            log(ln)
        if not managed:
            log("Nothing to unlock - the device is not managed.")
            log("(If a Google/FRP screen shows instead, run the FRP bypass flows.)")
            _mdm_save_report(lines)
            return
        log("")

        owners = r["owners"]
        admins = r["admins"]
        work = r["work_users"]
        pkgs = r["mdm_pkgs"]

        # 2. admins + owners
        log("Step 2/8 - remove active admins and owners ...")
        targets = sorted(set(admins.values())
                         | {c for cs in owners.values() for c in cs})
        for comp in targets:
            pkg = comp.split("/")[0]
            log(f"  -> {comp}")
            sh(f"cmd device_policy remove-admin --user 0 {comp}",
               timeout=30, quiet=True)
            sh(f"dpm remove-active-admin {comp}", timeout=30, quiet=True)
            sh(f"am force-stop {pkg}", timeout=15, quiet=True)
            sh(f"pm clear --user 0 {pkg}", timeout=30, quiet=True)

        ok, text = sh("cmd device_policy get-device-owner", timeout=15, quiet=True)
        if ok and text.strip():
            comp = text.strip()
            log(f"  -> residual device owner: {comp}")
            sh(f"cmd device_policy remove-active-admin --user 0 {comp}",
               timeout=30, quiet=True)
            sh(f"dpm remove-active-admin {comp}", timeout=30, quiet=True)

        # 3. work profiles
        log("Step 3/8 - remove work profiles ...")
        for uid in sorted(work):
            log(f"  -> user {uid}")
            sh(f"pm remove-user {uid}", timeout=30, quiet=True)

        # 4. DPC packages
        log("Step 4/8 - disable, clear and uninstall DPC packages ...")
        for pkg in sorted(pkgs):
            vendor = r["vendors"].get(pkg, "")
            log(f"  -> {pkg}" + (f"  [{vendor}]" if vendor else ""))
            sh(f"am force-stop {pkg}", timeout=15, quiet=True)
            sh(f"pm disable-user --user 0 {pkg}", timeout=30, quiet=True)
            sh(f"pm uninstall --user 0 {pkg}", timeout=30, quiet=True)
            sh(f"pm clear --user 0 {pkg}", timeout=30, quiet=True)

        # 5. persisted policy files
        log("Step 5/8 - clear persisted policy files ...")
        if root:
            for p in _MDM_POLICY_FILES:
                sh(f"su -c 'rm -rf {p}'", timeout=15, quiet=True)
            log("  removed policy files (root).")
        else:
            log("  no root - skipping file deletion (cmd/dpm removal above is")
            log("  usually enough; use the recovery flow if the lock returns).")
        sh("cmd device_policy stop-clear-data --user 0", timeout=30, quiet=True)

        # 6. provisioning flags
        log("Step 6/8 - reset provisioning flags ...")
        for s, k, v in (
            ("global", "device_provisioned", "1"),
            ("secure", "user_setup_complete", "1"),
            ("global", "setup_wizard_has_run", "1"),
            ("global", "package_verifier_enable", "1"),
            ("global", "verify_optional_upgrade", "1"),
        ):
            sh(f"settings put {s} {k} {v}", timeout=15, quiet=True)

        # 7. enforced lockscreen
        log("Step 7/8 - clear enforced lockscreen ...")
        sh("locksettings set-disabled true", timeout=15, quiet=True)
        sh("locksettings clear --old 0000", timeout=15, quiet=True)
        sh("locksettings clear --old 1234", timeout=15, quiet=True)

        # 8. verify + verdict + report
        log("Step 8/8 - verify ...")
        log("")
        v = _mdm_scan(sh, log)
        vlines, vmanaged = _mdm_report_lines(v, props)
        for ln in vlines:
            log(ln)
        log("")
        _mdm_verdict(log, v, vmanaged)
        path = _mdm_save_report(lines)
        if path:
            log(f"Report: {path}")

    steps = [Step("mdm_unlock", _run)]
    return Flow("mdm / device-owner unlock - smart", steps)


# Recovery-shell binaries the MDM recovery flow probes for.  Stock Samsung
# recovery ships a bare toybox, so several may be missing - the flow adapts
# to what is actually there.
_RECOVERY_PROBE = (
    "mount", "umount", "rm", "find", "ls", "cat", "mkdir", "echo", "printf",
    "wipe", "format", "mkfs.ext4", "mkfs.f2fs", "dd", "toybox", "busybox",
    "reboot", "tune2fs", "blockdev",
)


def flow_mdm_unlock_recovery(wipe=False):
    """MDM / device-owner removal via RECOVERY MODE - works on locked phones.

    Recovery mode is the one place Android runs as root BEFORE the OS boots,
    so the lock screen does not matter. Two modes:

      wipe=False (default): user data is preserved. Mount /data read-write and
        delete the persisted policy files (device_policies.xml + backups, the
        DPMS sqlite DB, owner records) and the lock-credential files
        (gatekeeper keys + locksettings.db). The OS then boots like a fresh
        device with ALL user data intact.

      wipe=True: perform a real factory data reset from recovery. Tries the
        standard AOSP mechanism (write --wipe_data into /cache/recovery/command
        and let recovery perform the wipe on next boot), falling back to a
        direct format of the userdata partition (mkfs.ext4/f2fs on the block
        device). If NO wipe mechanism exists in the recovery shell, the flow
        "goes deeper into the system": it mounts /data and manually deletes
        the full management + lock + account state (device policies, dpm sqlite,
        knox dirs, locksettings/gatekeeper, accounts.xml, FRP props) so the
        device comes up fully unmanaged.

    Requirement: the device must boot into stock recovery. On Samsung that is
    Power off -> Volume Up + Power (hold both until the blue 'Installing
    system update'/'Recovery' screen). Recovery's adb shell is unauthenticated
    on Samsung, so no 'Allow USB debugging' is needed even on a locked phone.
    """

    _POLICY_FILES = (
        "/data/system/device_policies.xml",
        "/data/system/users/0/device_policies.xml",
        "/data/system/users/0/device_policies_backup.xml",
        "/data/system/device_policies_backup.xml",
        "/data/system/dpm.sqlite",
        "/data/system/dpm.sqlite-wal",
        "/data/system/dpm.sqlite-shm",
    )
    _LOCK_FILES = (
        "/data/system/gatekeeper.password.key",
        "/data/system/gatekeeper.pattern.key",
        "/data/system/locksettings.db",
        "/data/system/locksettings.db-wal",
        "/data/system/locksettings.db-shm",
        "/data/system/users/0/gatekeeper.password.key",
        "/data/system/users/0/gatekeeper.pattern.key",
        "/data/system/users/0/locksettings.db",
        "/data/system/users/0/locksettings.db-wal",
        "/data/system/users/0/locksettings.db-shm",
    )
    # Deeper system state cleared when no wipe mechanism exists - goes beyond
    # the policy/lock files into account + FRP + knox state.
    _DEEP_FILES = (
        "/data/system/device_policies.xml",
        "/data/system/device_policies_backup.xml",
        "/data/system/users/0/device_policies.xml",
        "/data/system/users/0/device_policies_backup.xml",
        "/data/system/dpm.sqlite",
        "/data/system/dpm.sqlite-wal",
        "/data/system/dpm.sqlite-shm",
        "/data/system/knox",
        "/data/system/knox/device_policy_manager*",
        "/data/system/users/0/accounts.xml",
        "/data/system/users/0/userlist.xml",
        "/data/system/sync/accounts.xml",
        "/data/property/persistent_properties",
    )

    def _probe(sh):
        """Return {command: available} for the recovery shell."""
        log("Step 1/3 - probing recovery shell capabilities ...")
        avail = {}
        for cmd in _RECOVERY_PROBE:
            _, out = sh(f"command -v {cmd} 2>/dev/null", quiet=True)
            avail[cmd] = bool(out.strip())
        have = [c for c in _RECOVERY_PROBE if avail[c]]
        missing = [c for c in _RECOVERY_PROBE if not avail[c]]
        log("  available: " + (", ".join(have) if have else "none"))
        log("  missing:   " + (", ".join(missing) if missing else "none"))
        return avail

    def _wipe_data(sh, log, avail):
        """Real factory reset from recovery. Returns True if one was started."""
        log("  Method 1: write /cache/recovery/command (--wipe_data) ...")
        sh("mount /cache", quiet=True)
        sh("mount -o rw,remount /cache", quiet=True)
        ok, out = sh(
            "printf -- '--wipe_data\\n--wipe_cache\\n' > /cache/recovery/command"
            " && cat /cache/recovery/command",
            quiet=True,
        )
        if ok and out.strip():
            log(f"    wrote {out.strip().strip()}")
            log("    rebooting - recovery will factory-reset, then boot fresh ...")
            sh("reboot", timeout=10, quiet=True)
            return True
        log("    cache command-file failed (read-only /cache or no printf).")

        log("  Method 2: direct format of the userdata partition ...")
        blk = None
        for probe in (
            "ls /dev/block/by-name/userdata 2>/dev/null",
            "ls /dev/block/bootdevice/by-name/userdata 2>/dev/null",
            "ls /dev/block/by-name/UDISK 2>/dev/null",
            "ls /dev/block/by-name/USERDATA 2>/dev/null",
        ):
            ok, out = sh(probe, quiet=True)
            if ok and out.strip():
                blk = out.strip().splitlines()[0]
                break
        if not blk:
            ok, out = sh("ls /dev/block/by-name/ 2>/dev/null", quiet=True)
            if ok:
                for cand in out.splitlines():
                    if re.search(r"(?i)userdata|udisk", cand):
                        blk = cand.strip()
                        break
        if blk:
            if avail.get("mkfs.ext4"):
                log(f"    formatting {blk} with mkfs.ext4 ...")
                ok, _ = sh(f"mkfs.ext4 -F {blk}", quiet=True)
                if ok:
                    sh("reboot", timeout=10, quiet=True)
                    return True
            if avail.get("mkfs.f2fs"):
                log(f"    formatting {blk} with mkfs.f2fs ...")
                ok, _ = sh(f"mkfs.f2fs -f {blk}", quiet=True)
                if ok:
                    sh("reboot", timeout=10, quiet=True)
                    return True
            log("    no mkfs binary in the recovery shell.")
        else:
            log("    could not locate the userdata block device.")

        log("  Method 3: manual factory reset (guided) ...")
        log("    On the phone, use Volume keys to select:")
        log("      'Wipe data/factory reset' -> 'Factory data reset'")
        log("      -> 'Reboot system now'.")
        return False

    def _deep_clean(sh, log):
        log("  Deep clean: deleting management + lock + account state ...")
        removed = 0
        for path in _DEEP_FILES:
            ok, _ = sh(f"rm -rf {path}", quiet=True)
            if ok:
                removed += 1
        log(f"    removed {removed}/{len(_DEEP_FILES)} deep system file(s).")
        for path in _LOCK_FILES:
            sh(f"rm -f {path}", quiet=True)
        log("    scanning /data/data for DPC package dirs ...")
        ok, text = sh("ls /data/data", quiet=True)
        if ok:
            for pkg in text.splitlines():
                pkg = pkg.strip()
                if pkg and any(m in pkg.lower() for m in
                               ("knox", "dpc", "mdm", "mobix", "suremdm",
                                "miradore", "intune", "airwatch", "samsungkme")):
                    log(f"      removing DPC data dir: {pkg}")
                    sh(f"rm -rf /data/data/{pkg}", quiet=True)
        return removed

    def _run(ctx, log):
        title = ("MDM UNLOCK - RECOVERY MODE (with user-data wipe)"
                 if wipe else "MDM UNLOCK - RECOVERY MODE (no data wipe)")
        log("=" * 60)
        log(title)
        log("=" * 60)
        if wipe:
            log("Boots to stock recovery and performs a real factory data")
            log("reset (falls back to deep system cleanup if recovery cannot")
            log("wipe). ALL user data will be ERASED.")
        else:
            log("Boots the phone to stock recovery and deletes the management")
            log("policy + lock files. User data is NOT touched.")
        log("")

        # ---- 1. get into recovery ----
        try:
            devs = bridge.adb_status()
        except bridge.BridgeError:
            devs = []
        if any(d["state"] == "device" for d in devs):
            log("ADB is authorized - rebooting to recovery ...")
            try:
                bridge.adb_shell("reboot recovery", timeout=10)
            except bridge.BridgeError as e:
                log(f"  reboot failed: {e}")
            log("")
        else:
            log("No authorized ADB (or device locked). You must enter recovery")
            log("manually:")
            log("  1. Power the phone OFF.")
            log("  2. Hold Volume Up + Power (add Home on models with one).")
            log("  3. Release when the recovery/blue screen appears.")
            log("  4. Do NOT tap anything in recovery - just leave it.")
            log("")

        log("Waiting for the device in RECOVERY (adb state = 'recovery') ...")
        deadline = time.time() + 180
        serial = None
        while time.time() < deadline:
            if cancel_requested():
                raise FlowCancelled("cancelled while waiting for recovery")
            try:
                for d in bridge.adb_status():
                    if d["state"] in ("recovery", "device"):
                        serial = d["serial"]
                        break
            except bridge.BridgeError:
                pass
            if serial:
                break
            time.sleep(2)
        if not serial:
            log("")
            log("No recovery device appeared. Notes:")
            log("  - Samsung stock recovery shows adb state 'recovery'.")
            log("  - If you see 'unauthorized', the screen lock blocked it -")
            log("    reboot to recovery again and the dialog is skipped there.")
            log("  - Plug a DATA cable, and use a rear USB port on the PC.")
            raise RuntimeError("device did not enter recovery mode")

        log(f"Recovery device: {serial}")
        # Give recovery a moment to finish booting adbd.
        time.sleep(4)
        log("")

        def sh(cmd, timeout=25, quiet=False):
            if not quiet:
                log(f"  > adb shell {cmd}")
            try:
                out = bridge.adb_shell(cmd, timeout=timeout) or ""
            except bridge.BridgeError as e:
                if not quiet:
                    log(f"      ERROR: {e}")
                return False, ""
            text = out.strip()
            if text and not quiet:
                log(f"      {text[:400]}")
            return True, text

        # ---- 2. probe what the recovery shell can do ----
        avail = _probe(sh)

        # ---- 3. mount /data rw ----
        log("Step 2/3 - mount /data read-write ...")
        for cmd in (
            "mount /data",
            "mount -o rw,remount /data",
            "mount -o rw,remount /",
        ):
            ok, _ = sh(cmd)
            if ok:
                break

        # ---- 4. wipe (if requested) or delete policy + lock files ----
        if wipe:
            log("Step 3/3 - wipe user data ...")
            if _wipe_data(sh, log, avail):
                log("")
                log("Factory reset was triggered from recovery. The device")
                log("will wipe and reboot as a brand-new, unmanaged phone.")
                log("Complete the setup wizard and pick 'Skip' at any")
                log("MDM / QR provisioning prompt.")
                return
            log("")
            log("No wipe mechanism available in this recovery shell -")
            log("going DEEPER into the system ...")
            _deep_clean(sh, log)
            log("")
            log("Rebooting to normal mode ...")
            sh("reboot", timeout=10)
            log("")
            log("Done (deep cleanup, manual wipe may still be needed).")
            log("  - If the MDM/QR provisioning prompt returns, do the")
            log("    recovery-menu factory reset (guided above).")
            return

        log("Step 3/3 - delete management policy and lock files ...")
        deleted = 0
        for path in _POLICY_FILES:
            ok, _ = sh(f"rm -f {path}", quiet=True)
            if ok:
                deleted += 1
        for path in _LOCK_FILES:
            sh(f"rm -f {path}", quiet=True)
        log(f"    removed {deleted}/{len(_POLICY_FILES)} policy file(s).")

        # Best-effort: purge any DPC app data dir under /data/data.
        log("  Scanning /data/data for DPC package dirs ...")
        ok, text = sh("ls /data/data", quiet=True)
        if ok:
            for pkg in text.splitlines():
                pkg = pkg.strip()
                if pkg and any(m in pkg.lower() for m in
                               ("knox", "dpc", "mdm", "mobix", "suremdm",
                                "miradore", "intune", "airwatch", "samsungkme")):
                    log(f"    removing DPC data dir: {pkg}")
                    sh(f"rm -rf /data/data/{pkg}", quiet=True)

        log("")
        log("Rebooting to normal mode ...")
        sh("reboot", timeout=10)

        log("")
        log("Done. On boot the phone should present as a personal device.")
        log("  - If it asks to set up a device owner / scan a QR, pick 'Skip'.")
        log("  - All photos/apps/accounts are intact - nothing was wiped.")
        log("  - If a Google FRP screen appears, use the FRP bypass flows.")

    steps = [Step("mdm_unlock_recovery_wipe" if wipe else "mdm_unlock_recovery",
                  _run)]
    return Flow("mdm / device-owner unlock - recovery "
                "(with user-data wipe)" if wipe
                else "mdm / device-owner unlock - recovery (no wipe)",
                steps)


def flow_repair_settings():
    """Fix the Samsung 'Settings app keeps crashing' bug without a factory
    reset (Galaxy A14 / SM-A145P and similar).

    On many A14s the Settings app enters a crash loop that also takes down
    other UI, and the commonly-known 'fix' is a factory reset. The real cause
    is corrupted Settings app state, so re-enabling any disabled system
    packages and clearing the Settings/SystemUI app data repairs it in place,
    keeping ALL user data.
    """

    _REENABLE = [
        ("Settings", "com.android.settings"),
        ("System UI", "com.android.systemui"),
        ("One UI Home (launcher)", "com.samsung.android.launcher"),
        ("Samsung Settings ext.", "com.samsung.android.app.settings.bixby"),
    ]
    _CLEAR = [
        ("Settings", "com.android.settings"),
        ("System UI", "com.android.systemui"),
    ]

    def _run(ctx, log):
        log("=" * 60)
        log("REPAIR SETTINGS / UI CRASH (no factory reset)")
        log("=" * 60)
        log("Fixes the A14 'Settings keeps crashing' loop by clearing the")
        log("corrupted Settings/SystemUI state and re-enabling any disabled")
        log("system packages. Keeps ALL user data - no factory reset.")

        up = False
        try:
            up = any(d["state"] == "device" for d in bridge.adb_status())
        except bridge.BridgeError:
            pass
        if not up:
            log("No authorized ADB device yet - enabling USB debugging ...")
            _try_enable_adb(ctx, log)
            log("")
        log("Waiting for an AUTHORIZED ADB device ...")
        if not _wait_for_adb(ctx, log, timeout=90):
            log("")
            log("No authorized ADB yet. On this phone the USB-mode picker routes")
            log("through the crashed Settings app, and the PC cannot force the")
            log("USB mode on a modern single-config device. Forceable ways to get")
            log("authorized ADB, no firmware, in order:")
            log("")
            log("  1) *#0808# DIALER CODE (easiest, no PC): open the Phone app")
            log("     and dial *#0808# - it opens Samsung's hidden 'USB Settings'")
            log("     screen (the SEPARATE com.sec.usbsettings app, not Settings).")
            log("     Select 'MTP + ADB', reboot, unlock the screen, plug the data")
            log("     cable in, and the 'Allow USB debugging' dialog appears.")
            log("")
            log("  2) CLEAR STALE ADB AUTH IN RECOVERY: Power off -> hold Vol-Up +")
            log("     Power -> in recovery run `adb shell rm /data/misc/adb/adb_keys`")
            log("     (recovery adb is usually not gated), then reboot - the dialog")
            log("     reappears on next boot.")
            log("")
            log("  3) NO-DIALOG AUTHORIZE VIA RECOVERY: boot to recovery and run:")
            log("       adb shell mount /data")
            log("       adb push ~/.android/adbkey.pub /data/misc/adb/adb_keys")
            log("       adb shell 'chmod 0640; chown system:shell;")
            log("             chcon u:object_r:adb_keys_file:s0 /data/misc/adb/adb_keys'")
            log("     then `adb reboot` - ADB is authorized with no dialog.")
            log("")
            log("  If all that fails, the firmware route (no data loss) exists:")
            log("  MTK mode -> 'flash combination firmware (odin4)' to boot a")
            log("  COMBINATION_A145F... test build (adb with no auth dialog),")
            log("  re-run this flow, then flash normal stock firmware back. Odin")
            log("  does not touch /data, so user data is preserved.")
            raise RuntimeError(
                "no authorized adb device (see forceable routes above)"
            )

        serial = ctx.get("serial", "")
        log(f"Device serial: {serial}")
        model = _adb_getprop("ro.product.model")
        android_version = _adb_getprop("ro.build.version.release")
        if model:
            log(f"Model: {model}")
        log(f"Android: {android_version or 'unknown'}")

        log("")
        log("Step 1/3 - check for disabled system packages ...")
        try:
            disabled = bridge.adb_shell("pm list packages -d", timeout=30)
        except bridge.BridgeError as e:
            disabled = ""
            log(f"  `pm list packages -d` failed: {e}")
        reenabled = []
        for name, pkg in _REENABLE:
            if pkg in disabled:
                log(f"  {name} ({pkg}) is DISABLED - re-enabling ...")
                try:
                    out = bridge.adb_shell(f"pm enable {pkg}", timeout=20)
                    reenabled.append(pkg)
                    log(f"      {out.strip()[:120]}")
                except bridge.BridgeError as e:
                    log(f"      failed: {e}")
        if not reenabled:
            log("  no disabled packages found")

        log("")
        log("Step 2/3 - clear corrupted app state (cache + data) ...")
        for name, pkg in _CLEAR:
            log(f"  {name}: pm clear {pkg}")
            try:
                out = bridge.adb_shell(f"pm clear {pkg}", timeout=30)
                log(f"      {out.strip()[:120]}")
            except bridge.BridgeError as e:
                log(f"      {e}")

        log("")
        log("Step 3/3 - restart System UI and launch Settings to verify ...")
        try:
            bridge.adb_shell("am crash com.android.systemui", timeout=15)
        except bridge.BridgeError:
            pass
        time.sleep(3)
        try:
            out = bridge.adb_shell("am start -a android.settings.SETTINGS", timeout=15)
            log(f"  settings launch: {out.strip()[:200]}")
        except bridge.BridgeError as e:
            log(f"  settings launch failed: {e}")
        log("")
        log("  Check the phone: Settings should open normally now. If the phone")
        log("  still misbehaves, reboot it (`adb reboot`) - the cleared state")
        log("  persists. No factory reset was needed.")
        log("")
        log("  NOTE: this clears Settings/SystemUI app data only - apps, photos,")
        log("  accounts and system settings are untouched.")

    steps = [Step("repair_settings", _run)]
    return Flow("repair settings app crash (A14 / A145P etc.)", steps)


def flow_fix_adb_auth():
    """Fix an ADB device stuck at 'unauthorized' with no 'Allow USB debugging'
    dialog - typical when the phone is booted in 'Charging only' USB mode
    (ADB interface present, MTP not) or the screen is locked.

    On modern Samsung phones the USB mode is owned by Android's USB service
    and cannot be forced from the PC (single USB config, no AT port while
    booted, ADB not authorized yet). The switch lives in the notification
    shade - NOT Settings - so a crashed Settings app does not block it. This
    flow diagnoses the mode, attempts a USB reset to re-trigger re-enumeration
    + the auth dialog, and gives the exact steps.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("FIX ADB AUTHORIZATION (device shows 'unauthorized')")
        log("=" * 60)
        try:
            usb = bridge.detect_usb()
        except bridge.BridgeError as e:
            usb = []
            log(f"  usb detect failed: {e}")
        d = mtp.find_samsung()
        if not d:
            log("  no Samsung device detected - plug the phone in with USB")
            log("  debugging enabled (the phone must be BOOTED to the home")
            log("  screen, not in download/recovery mode).")
            raise RuntimeError("no Samsung device on USB")
        t = mtp.target(d)
        ifaces = d.get("interfaces", [])
        log(f"  device: {t}")
        log(f"  configs: {d.get('configs')} (active {d.get('active_config')})")
        for i in ifaces:
            log(f"  iface {i['number']}: class {i['class']} "
                f"sub {i.get('subclass')} proto {i.get('protocol')}")

        has_adb_iface = any(
            i.get("class") == 255 and i.get("subclass") == 66 for i in ifaces
        )
        has_mtp = any(i.get("class") == 6 for i in ifaces)
        has_acm = any(
            i.get("class") == 2 and i.get("subclass") == 2 for i in ifaces
        )

        if not has_adb_iface:
            log("")
            log("  No ADB interface present. Turn ON 'USB debugging' on the")
            log("  phone (Developer options) - this phone shows no ADB device")
            log("  while it is off.")
            raise RuntimeError("ADB interface not exposed by the phone")

        log("  USB debugging: ON (ADB interface detected)")
        if has_mtp:
            log("  USB mode: File transfer / MTP (good) - the auth dialog should")
            log("  appear once the screen is UNLOCKED.")
        elif has_acm:
            log("  USB mode: diag/AT present")
        else:
            log("  USB mode: ADB-only ('Charging' USB mode)")
            log("")
            log("  This is the problem: in Charging-only mode Samsung suppresses")
            log("  the 'Allow USB debugging' dialog even though the ADB interface")
            log("  is up. Switch the USB mode to MTP + ADB:")
            log("")
            log("  FORCEABLE WAY (no Settings app needed): the *#0808# dialer code.")
            log("  On Samsung it opens the hidden 'USB Settings' screen, which is")
            log("  the SEPARATE com.sec.usbsettings app - NOT the crashed Settings")
            log("  app. Works on the A14 5G / A14.")
            log("")
            log("    a. On the phone open the DIALER (Phone app) - it works even")
            log("       though Settings is broken.")
            log("    b. Dial:   *#0808#")
            log("    c. Select 'MTP + ADB' (or 'RNDIS + ACM + DM + ADB' on newer")
            log("       One UI) and confirm / reboot when asked.")
            log("    d. Fully UNLOCK the phone screen (a locked screen never shows")
            log("       the dialog), keep it on the home screen.")
            log("    e. Plug in the DATA cable, then unplug + re-plug once.")
            log("")
            log("  Alternative if the code is blocked: the notification shade -")
            log("  pull down twice -> tap the 'Charging this device via USB'")
            log("  notification. NOTE: on some One UI builds that routes into the")
            log("  Settings app (which crashes on this phone) - if so, only the")
            log("  dialer code above works.")
            log("")
            log("  Trying a USB reset now to re-trigger re-enumeration + dialog ...")
            try:
                r = bridge.usb_config(t, 1, timeout=30)
                log(f"  reset: {r}")
            except bridge.BridgeError as e:
                log(f"  reset failed: {e}")
            time.sleep(3)

        log("")
        log("  Waiting for the device to authorize (up to 45s) ...")
        if _wait_for_adb(ctx, log, timeout=45):
            log("")
            log("  ADB AUTHORIZED. Re-run 'Fix Settings / UI crash' -> ADB now.")
            return
        log("")
        log("  Still unauthorized. First re-check the *#0808# route above (select")
        log("  'MTP + ADB', reboot, unlock the screen, re-plug). If the dialog")
        log("  STILL never appears it usually means authorization was previously")
        log("  revoked/dismissed and One UI silently rejects without prompting.")
        log("")
        log("  Two ways to reset that 'no-dialog' state, in order:")
        log("")
        log("  1) Revoke authorizations WITHOUT Settings: boot to RECOVERY")
        log("     (Power off -> hold Vol-Up + Power until the blue menu), plug in,")
        log("     and run `adb shell rm /data/misc/adb/adb_keys` (then reboot).")
        log("     Recovery adb on Samsung is usually NOT authorization-gated, so")
        log("     this clears the stale RSA key list and the 'Allow USB debugging'")
        log("     dialog reappears on the next normal boot. If `rm` fails, reboot")
        log("     to recovery and try 'Wipe cache partition' first (keeps data).")
        log("")
        log("  2) Authorize WITHOUT any dialog (if recovery adb works): boot to")
        log("     recovery, then:")
        log("       adb shell mount /data")
        log("       adb push ~/.android/adbkey.pub /data/misc/adb/adb_keys")
        log("       adb shell 'chmod 0640 /data/misc/adb/adb_keys;")
        log("       adb shell 'chown system:shell /data/misc/adb/adb_keys;")
        log("       adb shell 'chcon u:object_r:adb_keys_file:s0 /data/misc/adb/adb_keys'")
        log("     then `adb reboot` - the PC is now authorized with no dialog,")
        log("     and 'Fix Settings / UI crash' -> ADB will work.")
        log("")
        log("  Also: use a DATA cable (charge-only cables stay unauthorized")
        log("  forever) and keep the phone screen unlocked during the whole thing.")

    steps = [Step("fix_adb_auth", _run)]
    return Flow("fix adb authorization (unauthorized, no dialog)", steps)


def flow_screen_lock_recovery():
    """Screen lock removal via recovery mode (factory reset).

    WARNING: This wipes ALL user data.

    A real factory reset removes the pattern/PIN/password, but it does NOT
    clear Google FRP or Samsung 'Reactivate lock' (Find My Mobile). If either
    is enabled the phone boots to the Setup Wizard and demands the previous
    Google/Samsung account - that remaining block is NOT a screen lock and
    needs the FRP bypass flows or combination firmware via Odin.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("SCREEN LOCK REMOVAL - RECOVERY MODE")
        log("=" * 60)
        log("WARNING: This method will WIPE ALL USER DATA on the device.")
        log("This is the most reliable method for encrypted devices.")
        log("")
        log("Enter recovery mode:")
        log("  1. Power off the device")
        log("  2. Press and hold: Volume Up + Power (no Home button)")
        log("     OR Volume Up + Home + Power (with Home button)")
        log("  3. Release when Samsung logo appears")
        log("  4. Use volume keys to navigate, Power to select")
        log("")
        
        if not _wait_for_adb(ctx, log, timeout=60):
            raise RuntimeError("no adb device appeared - ensure device is in recovery mode")
        
        serial = ctx.get("serial", "")
        log(f"Device serial: {serial}")
        
        # Check if device is in recovery mode
        try:
            recovery_check = bridge.adb_shell("getprop ro.bootmode", timeout=10).strip()
            log(f"Boot mode: {recovery_check}")
        except bridge.BridgeError:
            log("Could not detect boot mode, assuming recovery mode")
        
        log("")
        log("=" * 60)
        log("HOW TO WIPE (no working 'format data' adb command exists here)")
        log("=" * 60)
        log("Samsung stock recovery does NOT let `adb shell` run the wipe -")
        log("`format data`, `wipe cache` and `--wipe_data` simply print")
        log("'not found'. The wipe can ONLY be triggered from the on-screen")
        log("recovery MENU:")
        log("")
        log("    Wipe data/factory reset")
        log("    Yes (confirm)")
        log("    Reboot system now")
        log("")
        log("  Navigate with Volume keys, select with Power. Once you pick it,")
        log("  the wipe runs automatically and the phone reboots - this tool")
        log("  cannot press the menu buttons for you.")
        log("")

        log("=" * 60)
        log("WHAT TO EXPECT AFTER THE RESET")
        log("=" * 60)
        log("  - The pattern/PIN/password IS gone: the keyguard is removed.")
        log("  - BUT the phone then boots to the SETUP WIZARD, and if Google FRP")
        log("    or Samsung 'Reactivate lock' (Find My Mobile) is enabled, it")
        log("    will ask for the PREVIOUS Google / Samsung account. That is NOT")
        log("    a screen lock, and a factory reset does NOT clear it.")
        log("")
        log("  If you still see a lock after the reset, run:")
        log("    FRP bypass > ADB   (with the phone sitting on the Setup Wizard)")
        log("  or flash combination firmware (COMBINATION_FA80_*) via Odin.")
        log("")
        log("  To reboot now: 'adb reboot' (or Power button in recovery)")

    steps = [Step("screen_lock_recovery", _run)]
    return Flow("screen lock remove (Recovery)", steps)


def flow_screen_lock_edl():
    """Screen lock removal via EDL mode (Emergency Download Mode).
    
    This method uses EDL mode for Qualcomm-based Samsung devices.
    Requires device-specific firehose loaders and payloads.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("SCREEN LOCK REMOVAL - EDL MODE")
        log("=" * 60)
        log("EDL mode is for Qualcomm-based Samsung devices.")
        log("This method requires device-specific firehose loaders.")
        log("")
        log("Enter EDL mode:")
        log("  1. Power off the device")
        log("  2. Connect to PC while holding Volume Up + Volume Down")
        log("  3. Device should show 'EDL Mode' or be detected as Qualcomm HS-USB")
        log("")
        
        try:
            usb = bridge.detect_usb()
            samsung = [d for d in usb if d.get("is_samsung")]
            if not samsung:
                log("No Samsung device detected in EDL mode.")
                log("Ensure device is properly connected in EDL mode.")
                return
            
            first = samsung[0]
            log(f"Device detected: 04e8:{first['pid']:04x}")
            
            # Check if it's a Qualcomm EDL device
            is_edl = any(i["class"] == 255 for i in first["interfaces"])
            if is_edl:
                log("Device appears to be in EDL mode (Qualcomm HS-USB).")
            else:
                log("Device may not be in EDL mode. PID suggests normal mode.")
        except bridge.BridgeError as e:
            log(f"Error detecting device: {e}")
            return
        
        log("")
        log("=" * 60)
        log("EDL MODE SCREEN LOCK REMOVAL")
        log("=" * 60)
        log("EDL mode screen lock removal requires:")
        log("  1. Device-specific firehose loader (prog_emmc_firehose_xxxx.mbn)")
        log("  2. Device-specific partition table (rawprogram0.xml)")
        log("  3. Screen lock removal payload (modem.bin or similar)")
        log("")
        log("These files are proprietary and vary by:")
        log("  - Device model (e.g., SM-G965F, SM-A505FN)")
        log("  - Android version / security patch")
        log("  - Qualcomm chipset version")
        log("")
        log("To use this method:")
        log("  1. Obtain the correct firehose loader for your device")
        log("  2. Use Qualcomm QPST or QFIL tools")
        log("  3. Flash the screen lock removal payload")
        log("  4. Reboot the device")
        log("")
        log("This framework provides EDL detection only.")
        log("For actual screen lock removal via EDL, use:")
        log("  - Qualcomm QFIL (Qualcomm Flash Image Loader)")
        log("  - Commercial tools with EDL support")
        log("  - Device-specific research from GSMHosting/XDA")

    steps = [Step("screen_lock_edl", _run)]
    return Flow("screen lock remove (EDL)", steps)


def flow_screen_lock_comprehensive():
    """Comprehensive screen lock removal - tries multiple methods.
    
    This flow attempts multiple screen lock removal methods in sequence,
    starting with the least destructive and progressing to more drastic measures.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("COMPREHENSIVE SCREEN LOCK REMOVAL")
        log("=" * 60)
        log("This will attempt multiple methods in sequence.")
        log("Start with the least destructive method first.")
        log("")
        
        # Check device state
        try:
            usb = bridge.detect_usb()
            samsung = [d for d in usb if d.get("is_samsung")]
            if not samsung:
                log("No Samsung device detected. Connect device first.")
                return
            
            first = samsung[0]
            log(f"Device: 04e8:{first['pid']:04x}")
            
            # Detect mode
            mode = _detect_mode(samsung)
            log(f"Mode: {mode}")
        except bridge.BridgeError as e:
            log(f"Error detecting device: {e}")
            return
        
        log("")
        log("=" * 60)
        log("AVAILABLE METHODS:")
        log("=" * 60)
        log("1. ADB Method (least destructive)")
        log("   - Requires USB debugging enabled")
        log("   - Limited success on encrypted devices")
        log("   - No data loss")
        log("")
        log("2. Download Mode Method (combination firmware via odin4)")
        log("   - Requires device in download mode")
        log("   - Requires a combination firmware (.tar) + odin4 binary")
        log("   - No data loss")
        log("")
        log("3. Recovery Mode Method")
        log("   - Requires device in recovery mode")
        log("   - WIRES ALL USER DATA")
        log("   - Most reliable for encrypted devices")
        log("")
        log("4. EDL Mode Method")
        log("   - Requires Qualcomm device in EDL mode")
        log("   - Requires firehose loader and payload")
        log("   - Can be destructive if wrong payload used")
        log("")
        log("=" * 60)
        log("RECOMMENDATION:")
        log("=" * 60)
        
        if "ADB ENABLED" in mode:
            log("Device has ADB enabled.")
            log("Try: Screen lock remove > ADB")
            log("If that fails, try: Screen lock remove > Recovery mode")
        elif "DOWNLOAD MODE" in mode:
            log("Device is in download mode.")
            log("Try: Screen lock remove > Download mode")
            log("Note: uses combination firmware + adb clear (needs odin4 + .tar)")
        elif "RECOVERY" in mode or "recovery" in mode.lower():
            log("Device is in recovery mode.")
            log("Try: Screen lock remove > Recovery mode")
            log("Warning: This will wipe all data")
        else:
            log("Device is in normal mode without ADB.")
            log("Options:")
            log("  1. Enable USB debugging and try ADB method")
            log("  2. Boot to download mode and try Odin method")
            log("  3. Boot to recovery mode and try recovery method")
        
        log("")
        log("To try a specific method, select it from the Operations panel.")

    steps = [Step("screen_lock_comprehensive", _run)]
    return Flow("screen lock remove (Comprehensive)", steps)


FLOWS = {
    "detect": flow_detect,
    "download_mode_info": flow_download_mode_info,
    "fastboot": flow_fastboot,
    "fastboot_read": flow_fastboot_getvar,
    "fastboot_devices": flow_fastboot_devices,
    "fastboot_getvar": flow_fastboot_getvar,
    "fastboot_flash": flow_fastboot_flash,
    "fastboot_erase": flow_fastboot_erase,
    "fastboot_format": flow_fastboot_format,
    "fastboot_unlock": flow_fastboot_unlock,
    "fastboot_lock": flow_fastboot_lock,
    "fastboot_frp": flow_fastboot_frp,
    "fastboot_wipe": flow_fastboot_wipe,
    "fastboot_reboot": flow_fastboot_reboot,
    "fastboot_reboot_bootloader": flow_fastboot_reboot_bootloader,
    "fastboot_recovery": flow_fastboot_recovery,
    "fastboot_set_active": flow_fastboot_set_active,
    "fastboot_oem": flow_fastboot_oem,
    "fastboot_continue": flow_fastboot_continue,
    "reboot_recovery": flow_reboot_recovery,
    "reboot_download": flow_reboot_download,
    "reboot_normal": flow_reboot_normal,
    "reboot_edl": flow_reboot_edl,
    "reboot_bootloader": flow_reboot_bootloader,
    "factory_reset": flow_factory_reset,
    "setup_wizard": flow_setup_wizard,
    "test_mode": flow_test_mode,
    "at_info": flow_at_info,
    "at_method": flow_at_control,
    "download_frp": flow_download_mode_frp,
    "odin_enable_adb": flow_odin_enable_adb,
    "mtk_download_info": flow_mtk_download_info,
    "mtk_combo_flash": flow_mtk_combo_flash,
    "mtk_recovery_reset": flow_mtk_recovery_reset,
    "mtk_brom_info": flow_mtk_brom_info,
    "mtk_brom_backup": flow_mtk_brom_backup,
    "carrier_lock_status": flow_carrier_lock_status,
    "carrier_lock_mtk": flow_carrier_lock_mtk,
    "adb_frp": flow_adb_frp,
    "frp_browser": flow_frp_browser,
    "frp_emergency": flow_frp_emergency,
    "frp_settings": flow_frp_settings,
    "adb_info": flow_adb_info,
    "kg_state_check": flow_kg_state_check,
    "kg_remove": flow_kg_remove,
    "screen_lock_remove": flow_screen_lock_remove,
    "screen_lock_locksettings": flow_screen_lock_locksettings,
    "enable_adb": flow_enable_adb,
    "screen_lock_download": flow_screen_lock_download,
    "screen_lock_csc": flow_screen_lock_csc,
    "screen_lock_recovery": flow_screen_lock_recovery,
    "screen_lock_edl": flow_screen_lock_edl,
    "screen_lock_comprehensive": flow_screen_lock_comprehensive,
    "repair_settings": flow_repair_settings,
    "fix_adb_auth": flow_fix_adb_auth,
    "mdm_unlock": flow_mdm_unlock,
    "mdm_unlock_comprehensive": flow_mdm_unlock_comprehensive,
    "mdm_diagnostics": flow_mdm_diagnostics,
    "mdm_unlock_recovery": lambda: flow_mdm_unlock_recovery(wipe=False),
    "mdm_unlock_recovery_wipe": lambda: flow_mdm_unlock_recovery(wipe=True),
    "mdm_qr": flow_mdm_qr,
    "recovery": flow_recovery,
    "edl_frp": lambda: flow_edl(detect_only=False),
    "edl_detect": lambda: flow_edl(detect_only=True),
    "odin_flash_tar": flow_odin_flash_tar,
    "odin_check_tar": flow_odin_check,
    "odin_list_devices": flow_odin_list,
    "odin_advanced_flash": flow_odin_advanced_flash,
    "odin_preflight": flow_preflight,
    "odin_pit_tools": flow_odin_pit_tools,
    "odin_flash_partition": flow_odin_flash_partition_gui,
    "odin_flash_multi": flow_odin_flash_multi,
    "odin_send_pit": flow_odin_send_pit,
    "odin_vbmeta": flow_odin_vbmeta,
    "odin_efs_backup": flow_efs_backup,
    "odin_efs_restore": flow_efs_restore,
    "odin_sales_code": flow_change_sales_code,
}

# Fixed transport modes, identical for every job (user request):
#   ADB  - phone runs Android with USB debugging; locksettings / FRP clears
#   MTP  - Media Transfer Protocol; used to reach the modem/AT channel and to
#          ENABLE USB debugging from the PC side
#   Download mode - Samsung download mode (partition flashing)
#   Samsung BROM - Samsung BootROM low-level state (04e8:685c); same download-mode tools
#   MTK  - MediaTek download agent / DA (A05/A06) - needs the leaked odin4 binary
#   MTK BROM - MediaTek BootROM held state (0e8d:2000) - chip-id / preloader read
#   FASTBOOT - not a Samsung transport (kept for UI parity; see flow_fastboot)
#   EDL  - Qualcomm Emergency Download (Snapdragon models only)
MODES = ["ADB", "MTP", "Download mode", "Samsung BROM", "MTK", "MTK BROM", "FASTBOOT", "EDL"]

# job -> mode -> list of flow keys (the "methods" shown under each mode).
JOBS = {
    "Odin Flashing (Advanced)": {
        "ADB": ["odin_preflight", "odin_advanced_flash", "odin_flash_tar", "odin_check_tar", "odin_efs_backup", "odin_efs_restore", "odin_sales_code"],
        "MTP": ["odin_preflight", "odin_advanced_flash", "odin_flash_tar", "odin_check_tar", "odin_list_devices"],
        "Download mode": ["odin_preflight", "odin_advanced_flash", "odin_flash_tar", "odin_check_tar", "odin_list_devices", "odin_pit_tools", "odin_flash_partition", "odin_flash_multi", "odin_send_pit", "odin_vbmeta", "reboot_normal"],
        "Samsung BROM": ["odin_preflight", "odin_advanced_flash", "odin_flash_tar", "odin_check_tar", "odin_list_devices", "odin_pit_tools", "odin_flash_partition", "odin_flash_multi", "odin_send_pit", "odin_vbmeta"],
        "MTK": [],
        "MTK BROM": [],
        "FASTBOOT": [],
        "EDL": [],
    },
    "FRP bypass": {
        "ADB": ["adb_frp", "frp_browser", "frp_emergency", "frp_settings"],
        "MTP": ["at_method", "enable_adb", "test_mode"],
        "Download mode": ["download_frp", "odin_enable_adb"],
        "Samsung BROM": ["download_frp", "odin_enable_adb"],
        "MTK": ["mtk_combo_flash"],
        "MTK BROM": [],
        "FASTBOOT": ["fastboot_frp", "fastboot_unlock", "fastboot_wipe"],
        "EDL": ["edl_frp"],
    },
    "Screen lock remove": {
        "ADB": [
            "screen_lock_locksettings",
            "screen_lock_csc",
            "screen_lock_recovery",
            "screen_lock_comprehensive",
        ],
        "MTP": ["enable_adb", "test_mode"],
        "Download mode": ["screen_lock_download", "screen_lock_csc", "odin_enable_adb"],
        "Samsung BROM": ["screen_lock_download", "screen_lock_csc", "odin_enable_adb"],
        "MTK": ["mtk_recovery_reset", "mtk_combo_flash"],
        "MTK BROM": [],
        "FASTBOOT": ["fastboot_wipe", "fastboot_erase", "fastboot_frp"],
        "EDL": ["screen_lock_edl"],
    },
    "Read device info": {
        "ADB": ["adb_info", "kg_state_check", "recovery"],
        "MTP": ["at_info", "enable_adb", "test_mode"],
        "Download mode": ["download_mode_info", "kg_state_check"],
        "Samsung BROM": ["download_mode_info"],
        "MTK": ["mtk_download_info", "mtk_brom_info", "mtk_brom_backup"],
        "MTK BROM": ["mtk_brom_info", "mtk_brom_backup"],
        "FASTBOOT": ["fastboot_devices", "fastboot_getvar", "fastboot"],
        "EDL": ["edl_detect"],
    },
    "Detect": {
        "ADB": ["detect"],
        "MTP": ["detect"],
        "Download mode": ["detect"],
        "Samsung BROM": ["detect"],
        "MTK": ["mtk_download_info", "mtk_brom_info", "mtk_brom_backup"],
        "MTK BROM": ["mtk_brom_info", "mtk_brom_backup"],
        "FASTBOOT": ["fastboot_devices", "fastboot_getvar", "fastboot"],
        "EDL": ["detect"],
    },
    "Reboot device": {
        "ADB": [
            "reboot_recovery",
            "reboot_download",
            "reboot_normal",
            "reboot_edl",
            "reboot_bootloader",
        ],
        "MTP": ["reboot_recovery", "reboot_download", "reboot_normal"],
        "Download mode": ["reboot_normal"],
        "Samsung BROM": ["reboot_normal"],
        "MTK": ["reboot_normal"],
        "MTK BROM": [],
        "FASTBOOT": ["fastboot_reboot", "fastboot_reboot_bootloader",
                     "fastboot_recovery", "fastboot_continue"],
        "EDL": ["reboot_normal"],
    },
    "Fix Settings / UI crash": {
        "ADB": ["repair_settings", "fix_adb_auth"],
        "MTP": ["enable_adb", "test_mode"],
        "Download mode": [],
        "Samsung BROM": [],
        "MTK": [],
        "MTK BROM": [],
        "FASTBOOT": [],
        "EDL": [],
    },
    "Carrier lock": {
        "ADB": ["carrier_lock_status"],
        "MTP": [],
        "Download mode": [],
        "Samsung BROM": [],
        "MTK": [],
        "MTK BROM": ["carrier_lock_mtk"],
        "FASTBOOT": [],
        "EDL": [],
    },
    "MDM unlock": {
        "ADB": [
            "mdm_diagnostics",
            "mdm_unlock",
            "mdm_unlock_comprehensive",
            "mdm_unlock_recovery",
            "mdm_unlock_recovery_wipe",
            "mdm_qr",
        ],
        "MTP": ["enable_adb", "test_mode"],
        "Download mode": [],
        "Samsung BROM": [],
        "MTK": [],
        "MTK BROM": [],
        "FASTBOOT": ["fastboot_wipe", "fastboot_frp"],
        "EDL": [],
    },
}


def list_jobs():
    return list(JOBS.keys())


def modes_for(job):
    """Every job offers the same modes: ADB / MTP / Download mode / Samsung BROM /
    MTK / MTK BROM / FASTBOOT / EDL."""
    return list(MODES)


def methods_for(job, mode):
    """Flow keys available under job+mode (the 'methods' the user picks)."""
    return list(JOBS[job].get(mode, []))


def flow_for(job, mode, method):
    return FLOWS[method]()


def list_methods():
    return sorted(FLOWS.keys())
