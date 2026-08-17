import subprocess


class AdbError(RuntimeError):
    pass


def _run(args, timeout=20):
    proc = subprocess.run(
        ["adb", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc


def connected_serial():
    proc = _run(["devices"])
    for line in proc.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            return parts[0]
    return None


def shell(cmd, timeout=20):
    proc = _run(["shell", cmd], timeout=timeout)
    if proc.returncode != 0:
        raise AdbError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout.strip()


def getprop(name):
    try:
        return shell(f"getprop {name}").strip() or None
    except AdbError:
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
    except AdbError:
        return None
