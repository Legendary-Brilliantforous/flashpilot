# adb Cheat Sheet

Day-to-day adb operations for reverse engineering. Use forward slashes for on-device paths; quote host paths with spaces.

---

## Command-source taxonomy (where commands come from)

`|`, `>`, `&&` etc. are **shell** syntax, not adb. Commands you run through adb come from four different layers:

| Source | Examples | How to get help |
|--------|----------|-----------------|
| adb itself | `push`, `pull`, `install` | `adb help` |
| Android-specific tools | `pm`, `am`, `dumpsys` | `adb shell pm help`, `adb shell am help`, `adb shell dumpsys --help` |
| Linux base commands (toybox) | `ls`, `chmod`, `cat`, `grep` | `adb shell toybox`, `adb shell toybox <cmd> --help` |
| Magisk (third party) | `su` | `adb shell su --help` |

```bash
adb shell toybox            # list all available Linux commands
adb shell toybox ls --help  # usage of a specific one
```

---

## Multiple devices

```bash
adb devices                              # list serials
adb -s <serial> push file /data/local/tmp/
```

---

## push / pull — copy files

`adb push` copies host → device (does **not** install). `adb pull` copies device → host.

```bash
adb push <host-path> <device-path>
adb pull <device-path> <host-path>

# examples
adb push frida-server /data/local/tmp/
adb push C:\scripts\ /sdcard/scripts/        # whole folder
adb pull /sdcard/Download/test.apk .         # "." = current host dir
adb pull /sdcard/DCIM/ ./backup/             # whole folder
```

Common device targets:

| Path | Use |
|------|-----|
| `/data/local/tmp/` | tools (frida-server, etc.); runnable as root |
| `/sdcard/` | general files, app-accessible |
| `/sdcard/Download/` | downloads |

After pushing an executable, add the exec bit: `adb shell chmod +x /data/local/tmp/<file>`.

Useful pull flags: `-a` (preserve timestamps/mode), `-z` (compressed transfer: brotli/lz4/zstd).

Files under `/data/data/` are not readable by the shell user — copy out as root first, then pull:

```bash
adb shell su -c "cp /data/data/com.example.app/databases/data.db /sdcard/"
adb pull /sdcard/data.db .
```

---

## install / uninstall

```bash
adb install your_app.apk         # install
adb install -r your_app.apk      # reinstall/overwrite, keep data
adb uninstall com.example.app    # NOTE: package name, not file path
```

`Success` means it worked. `adb install` is not subject to the "unknown sources" toggle (that only gates tapping an APK in a file manager).

---

## Pull an installed APK off the device (for analysis)

```bash
# 1. find the package name
adb shell pm list packages                 # list all
adb shell pm list packages | grep <keyword># search

# 2. find the APK path on disk (no root needed)
adb shell pm path com.example.app
# package:/data/app/~~abc/com.example.app-xyz/base.apk

# 3. pull it
adb pull /data/app/~~abc/com.example.app-xyz/base.apk .
```

For apps installed as **split APKs** (Play Store / AAB), `pm path` prints several lines (`base.apk`, `split_config.*.apk`) — pull all of them.

---

## Delete files on-device

```bash
adb shell rm /sdcard/test.txt
adb shell rm -rf /sdcard/some_folder/
adb shell su -c "rm /data/local/tmp/frida-server"   # root-owned path
```

`-r` recursive, `-f` force. `rm` is irreversible — confirm the path. `/sdcard/` needs no root; `/data/` usually does.

---

## Writing files on-device (no editor available)

Android's adb shell has **no vim/nano** (it ships toybox). Options:

```bash
# echo + redirection (simple content)
adb shell "echo 'hello' > /sdcard/Documents/test.txt"   # overwrite
adb shell "echo 'second line' >> /sdcard/Documents/test.txt"  # append
adb shell "printf 'a\nb\nc\n' > /sdcard/Documents/test.txt"   # multi-line

# better for complex content: edit on the host, then push
adb push C:\work\test.txt /sdcard/Documents/
```

If you genuinely need an on-device editor, install Termux and `pkg install vim`.

---

## Other frequently used commands

```bash
adb shell getprop                          # all system properties
adb shell mount                            # partition mounts
adb shell dumpsys package com.example.app | grep permission
adb reboot bootloader                      # into fastboot
adb shell su -c "cat /proc/<pid>/maps"     # process memory map (root)
adb logcat | grep com.example.app          # filter app logs
```
