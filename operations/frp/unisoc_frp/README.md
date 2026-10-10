# operations/frp/unisoc_frp/
#
# UNISOC / SPD FRP engine — actual implementation lives in:
#   src/spd.rs                       (BSL protocol: BSL_CMD_*/BSL_REP_*, FDL1/FDL2)
#   python/core/spd_adb.py           (boot-image ADB-enable patch)
#   python/core/flows/screenlock.py  (calls spd-format via bridge)
#   python/core/flows/mdm.py         (BROM partition erase via spd-format)
#
# Bridge CLI commands (flashpilot-bridge):
#   spd-detect            (find 1782:4d00 / 4d02 / 4e00)
#   spd-info              (BootROM handshake + chip-id)
#   spd-partitions        (FDL2 partition table)
#   spd-frp               (erase frp / frp_a / misc / userdata via BROM)
#   spd-format            (full BROM factory-format)
#   spd-magic-pack        (signature-preserving UMS9620 SPL patch)
#   spd-reset             (BROM NORMAL_RESET)
#
# For a per-device UMS9230/SC9863A recipe, drop a research note in
# operations/frp/devices/<brand>/<model>.md once you have:
#   1. The FDL1 / FDL2 binaries
#   2. The FDL1 / FDL2 base addresses
#   3. The "frp" / "frp_a" partition name (varies: frp, frp_a, userdata)
#   4. The exact erase pattern (single partition, or frp+userdata)
