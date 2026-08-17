 #!/usr/bin/env python3
"""Validate the commercial MTP/AT FRP method against a connected Samsung J3.

Runs the exact chain commercial tools (SamFw / FRP King) use and reports at
every step, so we know whether this firmware supports it:

    [1/4] detect phone in MTP mode (04e8:6860)
    [2/4] switch USB to diag/modem config (reset + set_configuration 2)
    [3/4] ping the AT port and enable USB debugging via Samsung AT commands
    [4/4] wait for adb, then the GUI bypass is known-good

Usage:  .venv/bin/python validate_mtp_at.py
"""
import sys
import time

sys.path.insert(0, ".")

from python.core import bridge, frp, mtp


def main():
    print("Samsung FRP - MTP/AT method validation")
    print("=" * 54)
    print("PHONE:")
    print("  1) power it on to the Welcome / verify-account screen")
    print("  2) plug the USB cable into the PC")
    print("  3) keep the screen awake (not sleeping)")
    input("  press Enter once it's plugged in and showing the Welcome screen...\n")

    d = mtp.find_samsung()
    if d is None:
        print("FAIL: no Samsung device on USB - check cable/port, re-plug, try a")
        print("      different USB port (the phone must be ON and booted).")
        sys.exit(1)
    print(f"OK: Samsung detected 04e8:{d['pid']:04x} bus={d['bus']} addr={d['address']}")
    if d["pid"] != mtp.MTP_PID:
        print(f"NOTE: pid != 04e8:{mtp.MTP_PID:04x} (MTP mode). If it is in another")
        print("      mode, reboot the phone to system so it boots to the Welcome screen.")

    print("\n[1/4] switching USB to diag/modem config (reset + retry loop)...")
    try:
        t = mtp.switch_to_diag()
        print(f"  OK: switched -> {t}")
    except mtp.MtpError as e:
        print(f"  FAIL: {e}")
        print("  This is the make-or-break step for the config-switch method.")
        print("  If it keeps failing, the AT port cannot be exposed this way and")
        print("  we must fall back to the download-mode path.")
        sys.exit(1)

    print("\n[2/4] pinging AT port (bare 'AT' -> expects 'OK')...")
    alive = False
    for attempt in range(6):
        r = mtp.at("", t)
        if r.get("ok"):
            print(f"  OK: AT alive on attempt {attempt + 1}  reply={r.get('reply')!r}")
            alive = True
            break
        print(f"  no OK (attempt {attempt + 1}): reply={r.get('reply')!r}")
        if attempt == 1:
            print("  PHONE: on the Welcome screen tap Emergency call and dial")
            print("    *#0*#   (or   **#   on some firmwares), then press call/enter.")
        time.sleep(2)
    if not alive:
        print("  FAIL: AT port never answered 'OK'.")
        print("  If it never answers even after test mode, the diag port is closed")
        print("  on this firmware.")
        sys.exit(1)

    print("\n[3/4] sending Samsung AT commands to enable USB debugging...")
    print("NOTE: AT+DEBUGLVC drops the USB link (expected) - reconnecting...")
    t, lines = mtp.enable_adb_via_at(t)
    for ln in lines:
        print(f"  {ln}")
    print("  PHONE: tap 'Always allow' + OK on the 'Allow USB debugging' dialog")
    print("  (if it does not appear, unplug and re-plug the cable)")

    print("\n[4/4] waiting for adb device (up to 90s)...")
    ctx = {}
    if not frp._wait_for_adb(ctx, print, timeout=90):
        print("  FAIL: no adb device appeared.")
        sys.exit(1)
    serial = ctx["serial"]
    print(f"  OK: adb online: {serial}")

    print("\nVALIDATION PASSED - the MTP/AT method works on this firmware.")
    print("The GUI 'FRP bypass' -> 'MTP mode' flow is now known-good for this phone.")


if __name__ == "__main__":
    main()
