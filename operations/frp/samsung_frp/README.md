# operations/frp/samsung_frp/
#
# Samsung FRP (non-Odin) — actual implementation lives in:
#   python/core/flows/frp.py        (Samsung account-bypass, emergency call,
#                                   TalkBack, browser methods)
#   python/core/flows/brom.py        (Samsung MTK BROM FRP for A05/A06 Helio G85)
#   python/core/flows/oem_odin.py    (Download mode flashing — NOT for FRP;
#                                   Odin is flashing only, no FRP erase path)
#
# Flow keys registered:
#   flow_samsung_emergency_call    (on-device, no PC needed)
#   flow_samsung_talkback           (on-device, no PC needed)
#   flow_samsung_account_bypass     (on-device, no PC needed)
#   flow_mtk_brom_info              (read BROM chip id on A05/A06 Helio G85)
#   flow_mtk_brom_backup            (BROM DA erase of frp / nvdata — A05/A06)
#
# Per-device notes go in operations/frp/devices/samsung/ once a real recipe
# is found (example: see ../devices/samsung/galaxy_a14_*.md for the A145F
# variant note).
