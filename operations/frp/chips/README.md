# operations/frp/chips/
#
# Çip bazlı FRP işleyicileri burada değil, Rust motorunda yaşar.
# Bu dizin, FRP ağacının çip özel notlar / araştırma dökümleri için
# yer bulması içindir; dağıtım akış bazlıdır:
#
#   MediaTek (Helio / Dimensity / MT6765 / vb.)  →  `mtk_*` satırları `src/flows.rs` içinde
#   Qualcomm (Snapdragon / SD 695 / SD 8 Gen1)   →  `edl_*` / `qcom_*` satırları `src/flows.rs` içinde
#   Samsung Exynos (850 / 1330)                   →  Odin flaşlama yalnızca (FRP silme yolu yok)
#   UNISOC / Spreadtrum (SC9863A / T606 / UMS9230) →  `spd_*` satırları `src/flows.rs` içinde
#   HiSilicon (Kirin 710)                          →  akış yok (HW tersine mühendislik yapılmadı)
#
# (Kaldırılmış: `python/core/flows/{brom,frp,oem_odin}.py` hiç piyasaya sürülmedi.)
#
# Model bazlı arama için (model → çip → motor → eylem), bakınız
# operations/frp/INDEX.md ve python/gui/supported_devices.json.
#
# Çip bazlı tarif eklemek için:
#   1. Çip girişini supported_devices.json içine ekleyin (çip + motor)
#   2. Motor yeni bir akış gerektiriyorsa, bunu src/flows.rs içinde kaydedin
#      ve `flashpilot-bridge flow-list` ile doğrulayın
#   3. Yalnızca cihazın genel akışın kapsamadığı manuel bir geçici çözüm
#      gerektirdiği durumda burada araştırma notu bırakın (ofset, zamanlama,
#      pinout). Kısa tutun ve akışa bağlantı verin
