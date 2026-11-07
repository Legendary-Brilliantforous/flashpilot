# Moto G6 (ali) — SDM450 — FRP
Çip: Snapdragon 450 (SDM450)
Motor: qcom (fastboot)
VID: 22b8 (canlı olarak gözlendi: 22b8:2e80 fastboot · 22b8:2e2c MTP · 22b8:2eb7 mass-storage)
Durum: araştırıldı
Eylemler: frp, bilgi, flaş, screen_lock
Canlı: ZY322PSBZ2, fastboot 22b8:2e80@2:9, MTP 22b8:2e2c, FRP kilidinde ADB yok
FRP: Sihirbaz içindeki QR sahte oturum açma (MDM ▸ QR oluştur → cihaz-sahibi kaydı → ADB yetkilendirme → FRP temizleme), önyükleyici initrd filtresi öncesi CVE-2016-10277 zinciri (ali'nin 2020 MBM içeriği filtreler — akış dürüstçe bildirir), fabrika önyükleme döngüsü (fb_mode_set → reboot ×3 → yetkiyi dokun → silme, bayrak geri yüklenir), veya tarayıcı/acil durum sihirbazı kaçışları (Android 8/9 Verify account). `erase frp` için kilidi açık bir önyükleyici gerekir (cihaz bazlı sunucu tarafından verilen kod; Android tarafındaki OEM kilit açma anahtarı AÇIK olmalıdır).
Notlar: EDL 9008 test noktası yalnızca; MTK gibi BROM/DA yok.
