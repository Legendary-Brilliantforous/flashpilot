# operations/frp/generic_frp/
#
# Genel FRP yedekleri (ADB yetkili, her cihaz) — gerçek uygulama
# Rust akış kayıt defterinde yaşar (src/flows.rs, `flow-run <key>`). Bu
# akışlar motor-agnostik olup USB hata ayıklama yetkili olduğu sürece
# her Android telefonda çalışır.
#
# Kaydedilen akış anahtarları (doğrulamak için `flow-list` kullanın):
#   adb_frp                   — ayarları yaz + pm devre dışı bırak + pm temizle (evrensel)
#   frp_browser               — cihaz üzerinde: tarayıcı aç, chrome://settings/, hesabı kaldır
#   frp_emergency             — cihaz üzerinde: Ayarlar'a giden Acil arama çevirici yolu
#   frp_settings              — cihaz üzerinde: bildirim gölgesi üzerinden Ayarlar'ı aç
#   frp_fake_login (+testdpc/+adp) — cihaz sahibi DPC ile QR sağlama,
#                               ardından etkin ADB üzerinden FRP temizleme
#   factory_reset / recovery  — kurtarma tarafı silme yolları
#   (kaldırılmış) python/core/flows/{frp,info}.py (asla piyasaya sürülmedi)
#
# Belirli bir cihaz için genel yol yerine motor özel yolunu tercih edin
# (mtk_* / edl_frp / qcom_* / samsung + frp_* / spd_*) — genel yol,
# Google hesabının ADB üzerinden kaldırılabilir olmasını gerektirir; bu OEM
# politikasına göre engellenebilir.
