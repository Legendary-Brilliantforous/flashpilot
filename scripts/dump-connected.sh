#!/usr/bin/env bash
# Dump the live ADB-connected device firmware for reverse engineering.
#
# Without root we cannot `dd /dev/block/sda*` directly (shell can't read
# /dev/block/*), but we CAN pull the live mounted filesystems which are
# exactly the partition contents for our purposes. This is what commercial
# tools (UFI, SP Flash Tool's "Readback" without root) also do when no
# loader is available: read the user-space view, not raw sectors.
#
# If the device goes into SPD BROM (VID 1782), the spd-readback command
# does the raw sector dump properly. This script is the ADB-only path.
#
# Usage: ./scripts/dump-connected.sh [serial] [out_root]
# Defaults: serial from `adb devices` first row; out_root = cache/dumps/<model>_<codename>_<timestamp>

set -euo pipefail

SERIAL="${1:-}"
OUT_ROOT="${2:-}"

if [[ -z "$SERIAL" ]]; then
    SERIAL=$(adb devices -l | awk '/\bdevice\b/ {print $1; exit}')
    if [[ -z "$SERIAL" ]]; then
        echo "no authorized ADB device found; authorize USB debugging first" >&2
        exit 1
    fi
fi

if [[ -z "$OUT_ROOT" ]]; then
    INFO=$(adb -s "$SERIAL" shell "getprop ro.product.brand; getprop ro.product.model; getprop ro.product.device" | tr -d '\r' | head -3)
    BRAND=$(echo "$INFO" | sed -n 1p | tr -d ' ' | tr -d '\n')
    MODEL=$(echo "$INFO" | sed -n 2p | tr ' ' '_' | tr -d '\n')
    CODE=$(echo "$INFO" | sed -n 3p | tr -d '\n')
    STAMP=$(date +%Y%m%d_%H%M%S)
    OUT_ROOT="cache/dumps/${MODEL:-unknown}_${CODE:-unknown}_${STAMP}"
fi

mkdir -p "$OUT_ROOT"/{partitions,system,vendor,product,system_ext,data,metadata,cache,prodnv,tranfs,apex,buildprops,props,sepolicy,perms}
echo "==> dumping to $OUT_ROOT"

run() { echo "+ $*" >&2; "$@"; }
adbs() { adb -s "$SERIAL" shell "$*"; }
adbsu() { adb -s "$SERIAL" shell "su 0 sh -c \"$*\"" 2>/dev/null || adbs "$*"; }
adbp() { adb -s "$SERIAL" pull "$1" "$2" >/dev/null 2>&1; }

# --- device identity ---------------------------------------------------------
{
    echo "serial=$SERIAL"
    adb -s "$SERIAL" shell "getprop ro.build.fingerprint; getprop ro.build.id; \
        getprop ro.product.brand; getprop ro.product.model; getprop ro.product.device; \
        getprop ro.product.codename; getprop ro.board.platform; getprop ro.chipname; \
        getprop ro.hardware; getprop ro.build.version.release; getprop ro.build.version.sdk; \
        getprop ro.build.version.security_patch; getprop ro.bootloader; \
        getprop ro.serialno; getprop gsm.version.baseband" | tr -d '\r'
} > "$OUT_ROOT/identity.txt"
cat "$OUT_ROOT/identity.txt" >&2

# --- full getprop dump --------------------------------------------------------
echo "==> full getprop"
adb -s "$SERIAL" shell getprop > "$OUT_ROOT/props/getprop.txt"

# --- build.props (one per partition) -----------------------------------------
echo "==> build.props"
for src in /system/build.prop /vendor/build.prop /odm/build.prop /product/build.prop /system_ext/build.prop; do
    out_name=$(basename "$src")
    adb -s "$SERIAL" shell "cat '$src' 2>/dev/null" > "$OUT_ROOT/buildprops/${out_name}" || true
done
find "$OUT_ROOT/buildprops" -type f -size 0 -delete 2>/dev/null || true

# --- filesystem tree dumps via adb exec-out tar over adb pull (streaming) ---
# adb pull streams but doesn't always handle special files; tar over exec-out
# is the cleanest user-space dump. The result is a .tar file per partition
# you can extract locally for grep/analysis.
dump_partition_dir() {
    local src="$1"      # absolute remote path
    local label="$2"    # local tarball name
    local out="$OUT_ROOT/${label}.tar"
    if [[ -e "$out" ]]; then
        echo "  skip $label (already exists)" >&2
        return 0
    fi
    # We try multiple methods in order: tar | stdout, then find -print0 tar, then individual dirs.
    # 1) streaming tar via exec-out
    if adb -s "$SERIAL" exec-out "tar -cf - -C '$src' . 2>/dev/null" > "$out" 2>/dev/null && \
       [[ -s "$out" ]] && [[ $(stat -c %s "$out") -gt 0 ]]; then
        local sz=$(stat -c %s "$out")
        echo "  ok $label (${sz} bytes, tar)" >&2
        return 0
    fi
    # 2) cp into /sdcard then pull (fallback)
    echo "  fallback: copying $src to /sdcard/dump_tmp" >&2
    local remote_tmp="/sdcard/dump_${label}.tar"
    adb -s "$SERIAL" shell "rm -f '$remote_tmp'; cd '$src' && tar -cf - . 2>/dev/null > '$remote_tmp'; ls -l '$remote_tmp'" 2>&1
    adb -s "$SERIAL" pull "$remote_tmp" "$out" >/dev/null 2>&1 || true
    adb -s "$SERIAL" shell "rm -f '$remote_tmp'" 2>/dev/null || true
    if [[ -s "$out" ]]; then
        echo "  ok $label ($(stat -c %s "$out") bytes, tar-via-sdcard)" >&2
    else
        echo "  FAIL $label" >&2
        rm -f "$out"
    fi
}

# Always-mounted read-only partitions (the meat of the firmware):
echo "==> /system (read-only erofs)"
dump_partition_dir "/system" "system"
echo "==> /vendor (read-only erofs)"
dump_partition_dir "/vendor" "vendor"
echo "==> /product (read-only erofs)"
dump_partition_dir "/product" "product"
echo "==> /system_ext (read-only erofs)"
dump_partition_dir "/system_ext" "system_ext"

# We also want APEX info but apexes are loop-mounted, so dump the apex dirs:
echo "==> /apex/* (apexes; each is a bind-mount of /system/apex/<name>)"
for apex in /apex/*; do
    [[ -d "$apex" ]] || continue
    name=$(basename "$apex")
    dump_partition_dir "$apex" "apex/${name}"
done

# Writable /data: dump specific writable directories. /data is f2fs with
# per-user permissions; we only need the parts the device engineer can see.
# For the FRP/MDM/lock flows these matter: /data/property, /data/system, /data/vold
echo "==> /data (key directories only — privacy, encryption, locksettings)"
for sub in property system vold misc storage media tmp; do
    adb -s "$SERIAL" exec-out "cd '/data/$sub' 2>/dev/null && tar -cf - . 2>/dev/null" > "$OUT_ROOT/data/${sub}.tar" 2>/dev/null || true
    if [[ -s "$OUT_ROOT/data/${sub}.tar" ]]; then
        echo "  ok data/${sub} ($(stat -c %s "$OUT_ROOT/data/${sub}.tar") bytes)" >&2
    else
        rm -f "$OUT_ROOT/data/${sub}.tar"
    fi
done

# /metadata: ext4 rw. Holds persistent device-wide properties (FRP-flag host).
echo "==> /metadata (FRP flag host)"
dump_partition_dir "/metadata" "metadata"

# /cache, /prodnv, /tranfs: small ext4 partitions.
echo "==> /cache /prodnv /tranfs"
for sub in cache prodnv tranfs; do
    adb -s "$SERIAL" exec-out "cd '/$sub' 2>/dev/null && tar -cf - . 2>/dev/null" > "$OUT_ROOT/${sub}/${sub}.tar" 2>/dev/null || true
    [[ -s "$OUT_ROOT/${sub}/${sub}.tar" ]] && echo "  ok $sub ($(stat -c %s "$OUT_ROOT/${sub}/${sub}.tar") bytes)" >&2
done

# --- sepolicy / SELinux --------------------------------------------------------
echo "==> sepolicy + SELinux contexts"
adbsu "ls -la /sys/fs/selinux/policy" > "$OUT_ROOT/sepolicy/policy_file.txt" 2>/dev/null || \
    adb -s "$SERIAL" shell "ls -la /sys/fs/selinux/policy 2>/dev/null" > "$OUT_ROOT/sepolicy/policy_file.txt"
adbs "ls /sys/fs/selinux/class /sys/fs/selinux/initial_contexts 2>/dev/null" > "$OUT_ROOT/sepolicy/selinux_listing.txt" 2>/dev/null || true
# Try to dump actual policy binary (requires root usually)
adbs "cat /sys/fs/selinux/policy 2>/dev/null" > "$OUT_ROOT/sepolicy/policy.bin" 2>/dev/null || true
# If policy.bin is empty, try /vendor/etc/selinux/ which has the compiled policy split
for src in /vendor/etc/selinux /system/etc/selinux /odm/etc/selinux; do
    adb -s "$SERIAL" exec-out "cd '$src' 2>/dev/null && tar -cf - . 2>/dev/null" > "$OUT_ROOT/sepolicy/$(basename $src).tar" 2>/dev/null || true
done
find "$OUT_ROOT/sepolicy" -type f -size 0 -delete 2>/dev/null || true

# --- init scripts (the most useful FRP/USB reverse-engineering artifacts) -----
echo "==> init scripts + .rc files"
mkdir -p "$OUT_ROOT/initrc"
for src in /system/init /init /system/etc/init /system_ext/etc/init /vendor/etc/init /odm/etc/init; do
    if [[ -d "$src" ]] || [[ -f "$src" ]]; then
        label=$(echo "$src" | sed 's#/#_#g')
        adb -s "$SERIAL" exec-out "cd '$src' 2>/dev/null && find . -type f -name '*.rc' 2>/dev/null" > "$OUT_ROOT/initrc/${label}_rc_listing.txt" || true
    fi
done

# --- init.environ.rc and friends (try a few known paths) --------------------
echo "==> init.environ.rc + boot init artifacts"
for src in /system/etc/init.environ.rc /init.environ.rc /init.rc; do
    label=$(basename "$src")
    adb -s "$SERIAL" shell "cat '$src' 2>/dev/null" > "$OUT_ROOT/initrc/${label}" || true
done
find "$OUT_ROOT/initrc" -type f -size 0 -delete 2>/dev/null || true

# --- netpolicy / service / package DB (live config) -------------------------
echo "==> live config dumps"
mkdir -p "$OUT_ROOT/live_config"
adb -s "$SERIAL" shell "dumpsys deviceidle" > "$OUT_ROOT/live_config/deviceidle.txt" 2>/dev/null || true
adb -s "$SERIAL" shell "dumpsys device_policy" > "$OUT_ROOT/live_config/device_policy.txt" 2>/dev/null || true
adb -s "$SERIAL" shell "dumpsys lock_settings" > "$OUT_ROOT/live_config/lock_settings.txt" 2>/dev/null || true
adb -s "$SERIAL" shell "dumpsys package com.google.android.gms" > "$OUT_ROOT/live_config/gms.txt" 2>/dev/null || true
adb -s "$SERIAL" shell "pm list packages -f" > "$OUT_ROOT/live_config/packages.txt" 2>/dev/null || true
adb -s "$SERIAL" shell "dumpsys account" > "$OUT_ROOT/live_config/accounts.txt" 2>/dev/null || true
find "$OUT_ROOT/live_config" -type f -size 0 -delete 2>/dev/null || true

# --- permissions / SELinux mapping -------------------------------------------
echo "==> /etc/permissions + mac_permissions"
for src in /system/etc/permissions /vendor/etc/permissions /product/etc/permissions; do
    if adbsu "test -d '$src'" 2>/dev/null; then
        adb -s "$SERIAL" exec-out "cd '$src' 2>/dev/null && tar -cf - . 2>/dev/null" > "$OUT_ROOT/perms/$(basename $src).tar" 2>/dev/null || true
    fi
done
adb -s "$SERIAL" shell "cat /system/etc/permissions/platform.xml 2>/dev/null" > "$OUT_ROOT/perms/platform.xml" 2>/dev/null || true
find "$OUT_ROOT/perms" -type f -size 0 -delete 2>/dev/null || true

# --- fingerprint summary ------------------------------------------------------
echo "==> fingerprint summary"
{
    echo "# Fingerprint summary"
    grep -E "fingerprint|chipname|board.platform|hardware|product" "$OUT_ROOT/identity.txt" || true
    echo
    echo "# Captured partitions (.tar files):"
    find "$OUT_ROOT" -name "*.tar" -exec du -h {} \; | sort -k2
    echo
    echo "# Captured live_config files:"
    ls -la "$OUT_ROOT/live_config" 2>/dev/null
    echo
    echo "# Captured build.props:"
    ls -la "$OUT_ROOT/buildprops" 2>/dev/null
    echo
    echo "# Captured initrc artifacts:"
    ls -la "$OUT_ROOT/initrc" 2>/dev/null
    echo
    echo "# Captured SELinux/sepolicy:"
    ls -la "$OUT_ROOT/sepolicy" 2>/dev/null
} > "$OUT_ROOT/SUMMARY.md"
cat "$OUT_ROOT/SUMMARY.md"

echo
echo "Dump complete. Output: $OUT_ROOT"
echo "Extraction: cd $OUT_ROOT && for f in *.tar apex/*.tar data/*.tar; do [ -f \"\$f\" ] && tar -tf \"\$f\" > \"\${f%.tar}.list\"; done"
echo "Then: for f in *.tar; do [ -f \"\$f\" ] && mkdir -p \"\${f%.tar}\" && tar -xf \"\$f\" -C \"\${f%.tar}\"; done"
