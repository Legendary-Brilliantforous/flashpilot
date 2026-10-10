"""ADB helpers — thin delegates over the native Rust transport (bridge).

Historically this module shelled out to the system `adb` binary directly
(no `-s` serial pinning). All USB ADB now goes through `bridge.adb_*`
(target-pinned, kernel-driver detach, uniform cancel/timeout).
"""

from . import bridge

# Backwards-compat alias (was raised here before the native transport).
AdbError = bridge.BridgeError


def connected_serial():
    for d in bridge.adb_status():
        if d.get("state") == "device":
            return d.get("serial")
    return None


def shell(cmd, timeout=20):
    return bridge.adb_shell(cmd, timeout=timeout).strip()


def getprop(name):
    try:
        return shell(f"getprop {name}").strip() or None
    except bridge.BridgeError:
        return None


def device_info():
    return {
        "model": getprop("ro.product.model"),
        "name": getprop("ro.product.name"),
        "device": getprop("ro.product.device"),
        "android": getprop("ro.build.version.release"),
        "sdk": getprop("ro.build.version.sdk"),
        "firmware": getprop("ro.build.version.incremental"),
        "security_patch": getprop("ro.build.version.security_patch"),
        "frp_state": getprop("ro.frp.pst"),
        "usb_config": getprop("sys.usb.config"),
    }


def current_focus():
    try:
        out = shell("dumpsys window windows | grep -E 'mCurrentFocus'")
        return out.strip() or None
    except bridge.BridgeError:
        return None
