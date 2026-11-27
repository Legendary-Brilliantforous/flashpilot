"""Known failure causes the advisor can explain without guessing.

Each entry maps a pattern that appears in FlashPilot's real output (Rust
bridge messages, ADB errors, libusb errors) to *why* it happens and *what to
do next*. This is the grounding that lets the advisor answer "why did this
happen" from a log tail instead of inventing a cause.

The catalogue is deliberately small and hand-checked: every pattern below is
a string the bridge or the ADB path can actually emit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Cause:
    """One explainable failure mode."""

    pattern: str
    title: str
    why: str
    fix: str
    risk: str = ""

    def matches(self, line: str) -> bool:
        return re.search(self.pattern, line, re.IGNORECASE) is not None


CAUSES: tuple[Cause, ...] = (
    Cause(
        r"not authorized|unauthori[sz]ed|adb.*auth",
        "ADB is not authorised on the device",
        "The device shows an RSA prompt that was never accepted, or the host "
        "key changed. Until the transport is AUTHORIZED, every ADB flow "
        "(FRP, info, reboot) is refused before it starts.",
        "Unlock the screen, replug the cable, tap 'Allow' on the device "
        "(tick 'Always allow'), then re-run Detect. If no prompt appears, "
        "revoke USB debugging authorisations in Developer options and replug.",
    ),
    Cause(
        r"\bno device( found| matched)?\b|device not found|no usb device",
        "The target device is no longer on the bus",
        "The device re-enumerated (mode switch, reboot, or a USB reset) and "
        "the stored vid:pid@bus:addr went stale. FlashPilot resolves targets "
        "fresh before opening, but a scan that lands inside the re-enumeration "
        "window can still miss it.",
        "Re-run Detect, confirm the device still shows in the connection bar, "
        "then repeat the flow. If it alternates between two USB modes, wait "
        "for the mode to settle before starting.",
    ),
    Cause(
        r"claim interface failed|kernel driver active|LIBUSB_ERROR_ACCESS|"
        r"resource busy|LIBUSB_ERROR_BUSY",
        "Another process (or the kernel driver) holds the USB interface",
        "libusb cannot claim an interface that adb, ModemManager, a mounted "
        "MTP session or a kernel driver already owns. FlashPilot delegates to "
        "the ADB server or retries, but a foreign holder blocks both.",
        "Close other flashing tools, stop ModemManager if the device is a "
        "modem, unmount any MTP mount, then retry. ADB-only operations can "
        "run through the ADB server without claiming the interface.",
    ),
    Cause(
        r"LIBUSB_ERROR_NO_DEVICE|device disconnected|no such device",
        "The device was unplugged or reset mid-operation",
        "The USB handle became invalid — cable, hub, or a mode change during "
        "the transfer. Never unplug during a flash: a half-written partition "
        "is how devices bootloop.",
        "Reconnect directly to a rear USB port (no hub), re-enter the required "
        "mode, and re-run the same flow. Verify the partition state before "
        "flashing again.",
        "A partial write can leave the device unbootable until re-flashed.",
    ),
    Cause(
        r"checksum mismatch|verification failed|hash mismatch|verify.*fail",
        "Read-back verification did not match",
        "FlashPilot re-reads the written region and compares SHA-256. A "
        "mismatch means the write did not land intact: bad cable, unstable "
        "power, failing eMMC/UFS, or the wrong image for the partition.",
        "Do not reboot into the system. Re-flash the same partition, then "
        "verify again. If it fails twice, treat the storage as suspect.",
        "Booting a partition that failed verification can brick the device.",
    ),
    Cause(
        r"timed out|timeout|time out",
        "A stage timed out",
        "Handshakes (Odin, BROM, Sahara, BSL) and transfers have deadlines. "
        "Timeouts usually mean the device stopped answering: wrong mode, "
        "sleeping device, or a USB link that dropped packets.",
        "Keep the screen awake, use a known-good cable and a rear port, and "
        "retry the stage. For BROM, re-enter BROM before retrying.",
    ),
    Cause(
        r"not in (download|preloader|fastboot|edl) mode|wrong mode|expected .*got",
        "The device is in the wrong bootloader mode",
        "Each engine speaks one protocol. Odin needs Download mode, MTK needs "
        "BROM/preloader, Qualcomm needs EDL, SPD needs BSL. The flow refuses "
        "rather than sending the wrong protocol to a live device.",
        "Put the device in the mode the flow names, confirm the mode badge "
        "matches, then re-run. Do not force a flow across modes.",
    ),
    Cause(
        r"handshake failed|unexpected response|protocol error|invalid response",
        "The bootloader handshake was rejected",
        "The device answered, but not with the expected protocol frame: a "
        "different vendor mode, an already-open session, or a firmware/loader "
        "version the engine does not recognise.",
        "Power-cycle the device into the correct mode, close other tools, and "
        "retry once. If it persists, capture the console tail — the frame "
        "mismatch identifies which side spoke the wrong protocol.",
    ),
    Cause(
        r"scatter parse error|partition not found|missing required|invalid argument",
        "The firmware/scatter package does not match the device",
        "Partition names and offsets come from the scatter/PIT inside the "
        "package. A package for another model or region names partitions this "
        "device does not have.",
        "Use the firmware built for this exact model and region. Never "
        "repartition to make a foreign package fit.",
        "Flashing a mismatched package can hard-brick the device.",
    ),
    Cause(
        r"invalid credentials|signature|sla|secure boot|auth.*fail",
        "The bootloader is protected (SLA / secure boot)",
        "Protected MediaTek and Samsung units require signed download agents "
        "or an unlocked bootloader. The engine refuses unsigned sessions "
        "instead of risking the device.",
        "Confirm the bootloader state and use the vendor-signed payload path. "
        "On locked units, no BROM write will succeed — that is expected.",
    ),
    Cause(
        r"babble|overflow|overrun",
        "The USB link produced corrupt data",
        "Babble means the device sent more bytes than the endpoint packet "
        "size allows — a signal-integrity or hub problem, not a protocol bug.",
        "Replace the cable, drop any hub, and try a different port. Re-run "
        "the flow; the guard discards the bad transfer instead of writing it.",
    ),
    Cause(
        r"unsupported command|unsupported|not supported",
        "The device or firmware does not implement this command",
        "The engine sent a valid command for the protocol, but this "
        "loader/firmware revision does not support it (common on older "
        "preloaders and vendor-customised units).",
        "Use the flow variant intended for this generation, or the ADB path "
        "when the device boots. Report the exact command from the log.",
    ),
    Cause(
        r"unknown (command|flow|job|operation|action)|command not found|no such "
        r"(flow|command|job|operation)|invalid (command|flow|job|argument|action)",
        "The command or flow key does not exist",
        "FlashPilot flow keys are short snake_case identifiers declared in "
        "src/flows.rs; a typo or invented key is rejected before any USB traffic "
        "happens. The user-facing entry is `flashpilot-bridge flow-run <key>` and "
        "the real keys print via `flashpilot-bridge flow-list`.",
        "Run `flashpilot-bridge flow-list` (or open the matching GUI page) and use "
        "the exact key from there. A wrong key never reaches the device, so this "
        "cannot brick anything — just fix the key.",
    ),
    Cause(
        r"model mismatch|region mismatch|csc mismatch|firmware mismatch|image "
        r"mismatch|wrong (firmware|model|region|device|build|partition|firmware image)",
        "The firmware package does not match this device",
        "AP/BL/CP/CSC payloads and the scatter/PIT must match the exact model, region "
        "and build; a package for another device or region names partitions this "
        "device does not have, so the write is refused instead of riskily adapting.",
        "Flash the firmware built for this exact model and region and verify the CSC "
        "before writing.",
        "Forcing a mismatched package can hard-brick the device.",
    ),
    Cause(
        r"screen (is )?(locked|locked down)|frp (is )?(still )?active|factory reset "
        r"protection|lockout",
        "The device screen is locked / FRP protection is active",
        "ADB and fastboot lock-removal methods need the bootloader reachable; with "
        "FRP active the screen lock can block the ADB path even when the bootloader "
        "state itself is removable.",
        "Pick the flow for the current transport and mode — browser/settings bypass "
        "methods avoid the locked-screen requirement, BROM/EDL methods target locked "
        "bootloaders. Do not retry a method whose prerequisites are unmet.",
    ),
    Cause(
        r"permission denied|operation not permitted|access is denied|denied by|usb "
        r"(permission|access|driver)|udev",
        "The USB device is not accessible (permissions / udev)",
        "The user or the adb server could not claim the interface — on Linux this is "
        "usually the missing FlashPilot root udev rules.",
        "Install the FlashPilot udev rules and re-run Detect; ADB-only operations can "
        "run through the ADB server without claiming the interface.",
        "",
    ),
    Cause(
        r"battery|low voltage|power level|power (draw|fail|drop)",
        "Insufficient power for a write",
        "Flash/write operations need a stable power rail; a low battery or brownout "
        "during a write can corrupt the partition.",
        "Charge above 50%, keep the screen awake, and retry the stage.",
        "A partial write can leave the device unbootable until re-flashed.",
    ),
)


def match(log_text: str, limit: int = 3) -> list[tuple[Cause, str]]:
    """Return up to *limit* ``(cause, matching_line)`` pairs for *log_text*.

    Newest lines win: the log is scanned bottom-up so the failure that ended
    the operation is reported before an earlier, unrelated warning.
    """
    if not log_text:
        return []
    lines = [line for line in str(log_text).splitlines() if line.strip()]
    found: list[tuple[Cause, str]] = []
    seen: set[str] = set()
    for line in reversed(lines):
        for cause in CAUSES:
            if cause.title in seen:
                continue
            if cause.matches(line):
                seen.add(cause.title)
                found.append((cause, line.strip()[:300]))
                if len(found) >= limit:
                    return found
    return found


def render(log_text: str, limit: int = 3) -> str:
    """Render matched causes as a compact prompt block (empty when none)."""
    hits = match(log_text, limit=limit)
    if not hits:
        return ""
    out = ["Known failure causes matched in the console tail:"]
    for cause, line in hits:
        out.append(f"- {cause.title}")
        out.append(f"  Why: {cause.why}")
        out.append(f"  Fix: {cause.fix}")
        if cause.risk:
            out.append(f"  Risk: {cause.risk}")
        out.append(f"  Matched line: {line}")
    return "\n".join(out)
