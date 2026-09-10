#!/usr/bin/env python3
"""Watch for Samsung USB devices appearing/disappearing (for key-combo modes).

Uses the Rust bridge (`detect`) instead of parsing `lsusb` output, so the
same enumeration the GUI sees is what this script reports — no text scraping,
no lsusb dependency.
"""
import argparse
import sys
import time

sys.path.insert(0, ".")

from python.core import bridge


def lsusb_samsung():
    try:
        devs = bridge.detect_all() or []
    except Exception:
        return []
    out = []
    for d in devs:
        if not isinstance(d, dict) or d.get("vid") != 0x04E8:
            continue
        try:
            line = (
                f"Bus {int(d['bus']):03d} Device {int(d['address']):03d}: "
                f"ID 04e8:{int(d['pid']):04x} "
                f"{d.get('manufacturer') or ''} {d.get('product') or ''}".strip()
            )
        except (KeyError, TypeError, ValueError):
            continue
        out.append(line)
    return out


def main(timeout=120):
    print(f"watching for Samsung USB changes for {timeout}s... (do the key combo now)")
    known = set(lsusb_samsung())
    deadline = time.time() + timeout
    while time.time() < deadline:
        now = set(lsusb_samsung())
        if now != known:
            print("\n--- USB change detected ---")
            print("before:")
            for l in sorted(known):
                print(" ", l)
            print("after:")
            for l in sorted(now):
                print(" ", l)
            known = now
        time.sleep(0.5)
    print("\nwatching stopped.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args()
    main(args.timeout)
