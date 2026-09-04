# Nokia G20 — MT6765 (Helio P35/G35) — FRP
Chip: MT6765 (Helio P35/G35)
Engine: mtk
VID: 0e8d
Status: researched
Actions: frp, info, backup, flash
FRP: mmcblk0p4 (frp), instant BROM DA erase via mtk-frp-gpt (no combo, no Odin), DA MT6765, preloader 0e8d:0003 → BROM 0e8d:2000
Dump: cache/dumps/Nokia_G20_RNN_sprout_20260831_174601/ (system 1.5G, product 1.6G, vendor 175M, system_ext 223M, getprop, partitions)
Build: Ronin_00WW/RNN_sprout:11/RP1A.200720.011/00WW_1_100, Android 11, patch 2021-06-05, baseband MOLY.LR12A
Notes: BROM dump pending (preloader 0e8d:0003 needs crash to 2000), ADB tar done 2025-08-31, instant FRP via BROM DA zero frp partition.
