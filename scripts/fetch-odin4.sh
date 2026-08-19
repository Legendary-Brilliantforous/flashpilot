#!/usr/bin/env bash
set -euo pipefail
# Fetches the Samsung Odin v4 for Linux binary into root/tools/odin4.
#
# odin4 is Samsung's proprietary Linux download-mode tool and is NOT
# redistributable here, so we pull it from a public mirror at setup time.
# The download is verified against the pinned SHA-256 below, and the tool
# re-verifies that digest before every flash (see python/core/frp.py).
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$DIR/root/tools/odin4"
# Installed layouts (read-only /usr/share/flashpilot) fall back to a
# user-writable path so the script still works after packaging.
if [ ! -d "$(dirname "$OUT")" ] || [ ! -w "$(dirname "$OUT")" ]; then
    OUT="${XDG_BIN_HOME:-$HOME/.local/bin}/odin4"
    mkdir -p "$(dirname "$OUT")"
fi
MIRROR="${ODIN4_URL:-https://raw.githubusercontent.com/leaked-odin4/odin4-linux/main/odin4}"
# SHA-256 of the known-good odin4 build. Update this (and ODIN4_SHA256 in
# python/core/frp.py) only when you have verified a new binary.
ODIN4_SHA256="${ODIN4_SHA256:-a35199f8a3f1b07c79eaf1f0f675e94f45a5edc9e75c79a1e45b01d423ac9644}"

if [ -x "$OUT" ]; then
    echo "odin4 already present at $OUT"
    exit 0
fi

echo "Downloading odin4 from $MIRROR ..."
curl -fL --progress-bar "$MIRROR" -o "$OUT"
chmod +x "$OUT"

echo "Verifying SHA-256 of downloaded odin4 ..."
if ! printf '%s  %s\n' "$ODIN4_SHA256" "$OUT" | sha256sum -c --status; then
    echo "ERROR: downloaded odin4 does not match the pinned SHA-256." >&2
    echo "  expected: $ODIN4_SHA256" >&2
    echo "  actual:   $(sha256sum "$OUT" | cut -d' ' -f1)" >&2
    echo "Remove it and retry. Only override ODIN4_SHA256 if you trust the source." >&2
    rm -f "$OUT"
    exit 1
fi

# Lightweight smoke test (odin4 returns 0 for '-l' even with no device).
"$OUT" -l >/dev/null 2>&1 && echo "OK: odin4 ready at $OUT" || {
    echo "Downloaded file does not look like odin4; remove it and try again." >&2
    rm -f "$OUT"
    exit 1
}
