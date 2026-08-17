#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sudo install -m 0644 "$DIR/60-odin4.rules" /etc/udev/rules.d/60-odin4.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
echo "USB rules installed. Replug the phone in Download Mode."