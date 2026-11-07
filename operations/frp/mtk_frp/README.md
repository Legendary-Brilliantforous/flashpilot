# operations/frp/mtk_frp/
#
# MediaTek FRP motoru — gerçek uygulama şurada yaşar:
#   src/flows.rs kaydı  (mtk_download_info, mtk_brom_info,
#                       mtk_brom_backup, mtk_combo_flash,
#                       mtk_recovery_reset, mtk_crash_brom, mtk_verify,
#                       mtk_auth_flash — `flow-run <key>` ile çalıştırılır)
#   src/mtk_da.rs          (DA protokolü + taşıyıcı/SIM kilit yamaları)
#   src/mtk_exploit.rs     (kamakiri2 + BROM kimlik doğrulama atlatma)
#   python/core/mtk.py     (USB yardımcıları: find_mtk(), çip kimliği yönlendirme)
#   (kaldırılmış) python/core/flows/{brom,screenlock,mdm}.py (asla piyasaya sürülmedi)
#
# Bridge CLI (flashpilot-bridge):
#   mtk-detect / mtk-da-upload / mtk-frp / mtk-bypass / mtk-brom-exploit
#   (adları `flashpilot-bridge --help` ile doğrulayın; akışlar tercih edilir)
#
# Çip bazlı DA/loader çiftleri (helio_g85, dimensity_8020, mt6765, vb.)
# BROM el sıkışmasında bildirilen çip kimliğine göre python/core/mtk.py
# tarafından otomatik seçilir. src/mtk.rs dosyasına bakın.
#
# Her model için gerçek bir FRP tarifi olduğunda operations/frp/devices/<brand>/ altına
# model bazlı bir araştırma notu ekleyin (ör. "mmcblk0p4 = frp, anında BROM DA silme").
