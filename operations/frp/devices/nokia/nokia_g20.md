# Nokia G20 — MT6765 (Helio P35/G35) — FRP
Çip: MT6765 (Helio P35/G35)
Motor: mtk
VID: 0e8d
Durum: araştırıldı
Eylemler: frp, bilgi, backup, flash
FRP: mmcblk0p4 (frp), `mtk-frp-gpt` üzerinden anlık BROM DA silme (combo yok, Odin yok), DA MT6765, preloader 0e8d:0003 → BROM 0e8d:2000
Döküm: cache/dumps/Nokia_G20_RNN_sprout_20260831_174601/ (system 1.5G, product 1.6G, vendor 175M, system_ext 223M, getprop, partitions)
Derleme: Ronin_00WW/RNN_sprout:11/RP1A.200720.011/00WW_1_100, Android 11, patch 2021-06-05, baseband MOLY.LR12A
Notlar: BROM dökümü bekleniyor (preloader 0e8d:0003, 2000'e çöküş gerektiriyor), ADB tarı 2025-08-31 tamamlandı, BROM DA ile `frp` bölümünü sıfırlayarak anlık FRP etkinleşti.
