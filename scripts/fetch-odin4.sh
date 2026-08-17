#!/usr/bin/env bash
set -euo pipefail
# Fetches the Samsung Odin v4 for Linux binary into root/tools/odin4.
#
# odin4 is Samsung's proprietary Linux download-mode tool and is NOT
# redistributable here, so we pull it from a public mirror at setup time.
# Verify the checksum before trusting a source.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$DIR/root/tools/odin4"
MIRROR="${ODIN4_URL:-https://raw.githubusercontent.com/leaked-odin4/odin4-linux/main/odin4}"

if [ -x "$OUT" ]; then
    echo "odin4 already present at $OUT"
    exit 0
fi

echo "Downloading odin4 from $MIRROR ..."
curl -fL --progress-bar "$MIRROR" -o "$OUT"
chmod +x "$OUT"
"$OUT" --help >/dev/null 2>&1 && echo "OK: odin4 ready at $OUT" || {
    echo "Downloaded file does not look like odin4; remove it and try again."
    rm -f "$OUT"
    exit 1
}