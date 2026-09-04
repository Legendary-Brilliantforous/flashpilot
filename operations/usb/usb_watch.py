#!/usr/bin/env python3
"""Watch for Samsung USB devices appearing/disappearing (for key-combo modes)."""
import argparse
import subprocess
import sys
import time


def lsusb_samsung():
    out = subprocess.run(["lsusb"], capture_output=True, text=True).stdout
    devs = []
    for line in out.splitlines():
        if "04e8" in line:
            devs.append(line)
    return devs


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
