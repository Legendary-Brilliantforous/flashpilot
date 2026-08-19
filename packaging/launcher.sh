#!/bin/sh
# FlashPilot launcher.
# Runs on the bundled venv (PyQt6 + segno) shipped at /usr/lib/flashpilot/venv;
# the Rust bridge is installed alongside it and python ships read-only in
# /usr/share/flashpilot/.
export flashpilot_BRIDGE="${flashpilot_BRIDGE:-/usr/lib/flashpilot/flashpilot-bridge}"
VENV_PY=/usr/lib/flashpilot/venv/bin/python
if [ -x "$VENV_PY" ]; then
    exec "$VENV_PY" /usr/share/flashpilot/main.py "$@"
fi
exec /usr/bin/python3 /usr/share/flashpilot/main.py "$@"
