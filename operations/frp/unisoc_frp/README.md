# operations/frp/unisoc_frp/
#
# UNISOC / SPD FRP motoru — gerçek uygulama şurada yaşar:
#   src/spd.rs                       (BSL protokolü: BSL_CMD_*/BSL_REP_*, FDL1/FDL2)
#   src/flows.rs kaydı               (spd_* satırları: spd_detect_info, pac_extract/pac_pack, ofp_extract)
#   (kaldırılmış) python/core/spd_adb.py (boot-image ADB-enable yaması — Python motoru kaldırıldı;
#                                     SPD ADB-enable artık iş istasyonu flaş akışları üzerinden yürütülür)
#   (kaldırılmış) python/core/flows/{screenlock,mdm}.py (asla piyasaya sürülmedi; mantık Rust akışlarında yaşıyor)
#
# Bridge CLI komutları (flashpilot-bridge):
#   spd-detect            (1782:4d00 / 4d02 / 4e00 bul)
#   spd-info              (BootROM el sıkışması + çip kimliği)
#   spd-partitions        (FDL2 bölüm tablosu)
#   spd-frp               (BROM üzerinden frp / frp_a / misc / userdata sil)
#   spd-format            (tam BROM fabrika biçimlendirme)
#   spd-magic-pack        (imza korumalı UMS9620 SPL yaması)
#   spd-reset             (BROM NORMAL_RESET)
#
# Per-device UMS9230/SC9863A tarifi için, aşağıdakileri elde ettiğinizde
# operations/frp/devices/<brand>/<model>.md içinde araştırma notu bırakın:
#   1. FDL1 / FDL2 ikili dosyaları
#   2. FDL1 / FDL2 temel adresleri
#   3. "frp" / "frp_a" bölüm adı (değişir: frp, frp_a, userdata)
#   4. Tam silme deseni (tek bölüm veya frp+userdata)
