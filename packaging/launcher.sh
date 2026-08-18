#!/bin/sh
# Brilliant Flashing Tool launcher.
# Runs on the bundled venv (PyQt6 + segno) shipped at /usr/lib/brilliant/venv;
# the Rust bridge is installed alongside it and python ships read-only in
# /usr/share/brilliant/.
export BRILLIANT_BRIDGE="${BRILLIANT_BRIDGE:-/usr/lib/brilliant/brilliant-bridge}"
VENV_PY=/usr/lib/brilliant/venv/bin/python
if [ -x "$VENV_PY" ]; then
    exec "$VENV_PY" /usr/share/brilliant/main.py "$@"
fi
exec /usr/bin/python3 /usr/share/brilliant/main.py "$@"
