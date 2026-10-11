# operations/frp/samsung_frp/
#
# Samsung FRP (non-Odin) — actual implementation lives in:
#   src/flows.rs registry  (frp_emergency, frp_browser, frp_qr_provision,
#                           frp_alliance — on-device methods, no PC needed
#                           beyond ADB; run via `flow-run <key>`)
#   mtk_brom_info / mtk_brom_backup rows (Samsung MTK BROM FRP for
#                           A05/A06 Helio G85: read BROM chip id, BROM DA
#                           erase of frp / nvdata)
#   (retired) python/core/flows/{frp,brom,oem_odin}.py (never shipped;
#             Odin download mode is flashing only, no FRP erase path)
#
# Per-device notes go in operations/frp/devices/samsung/ once a real recipe
# is found (example: see ../devices/samsung/galaxy_a14_*.md for the A145F
# variant note).
