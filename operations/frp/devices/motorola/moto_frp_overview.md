# Motorola / Lenovo — FRP sıfırlama (FlashPilot uygulaması)

Durum: uygulandı
Çip: Qualcomm Snapdragon (çoğu Moto G/E/Edge serisi) veya MediaTek (bazı G/Edge)
VID: 22b8 (Motorola)
Taşıyıcılar: ADB, FASTBOOT

## Akışlar

| Akış anahtarı | Taşıyıcı | Ne yapar |
|---|---|---|
| `moto_frp_adb` | ADB | `frp` güvenli ayarını sıfırlar, kurulumun tamamlandığını / cihazın sağlandığını işaretler, kalıcı FRP deposunu kaldırır, Google + Motorola kurulum sihirbazlarını devre dışı bırakır. |
| `moto_frp_fastboot` | FASTBOOT | CVE-2016-10277 (initroot) zinciri: sürüm + `fsg-id` UTAG kapıları, kullanıcı tarafından sağlanan initramfs eklenmesiyle çekirdek komut satırı enjeksiyonu (`--file` + `--partition` çalışma adresi, hiç piyasaya sürülmedi), ardından kök ADB'ye geçiş ve ADB silme. |
| `frp_fake_login` / `frp_fake_login_testdpc` / `frp_fake_login_adp` | Sihirbaz → ADB | QR sağlama ile DPC / TestDPC / Android Device Policy kullanımı: kurulum sihirbazında cihaz sahibi olarak kaydolur (6 dokunuşlu QR tarayıcı), kurulumu tamamlar, ADB'yi etkinleştirir ve yetki verildiğinde FRP'yi temizler. |

Kilit açma token akışı (`moto_oem_unlock_token`) kaldırıldı: 20 karakterlik kod cihaz başına özeldir ve sunucu tarafından üretilir; bu nedenle araç düzeyinde token stratejisi işe yaramaz bir yoldur. Önyükleyici kilidini açma işlemi yine `fastboot_unlock --code` üzerinden çalışır, Android tarafındaki OEM kilit açma anahtarı açık olduktan sonra.

Bu akışlar **marka genelidir, model bazlı değildir**: Motorola → Tüm Motorola / Lenovo (evrensel) altında görünürler ve her Moto modeli sayfasında yer alırlar; satıcı çalışma zamanında tespit edilir. Fastboot kolları **yerel Rust fastboot taşıyıcısı** üzerinden çalışır (`fastboot-cmd`, hedef sabitlenmiş `vid:pid@bus:addr`, kernel sürücüsü ayrımı) ve köprü eşleşen cihaz bulamadığında yalnızca sistem `fastboot` ikili dosyasına geri döner.

## Teknik notlar (temiz oda, kamuya açık Motorola fastboot/ADB davranışlarından türetilmiş)

- **ADB yolu**, diğer Android cihazlarda kullanılan aynı türden bir sağlama sıfırlama yöntemidir (`settings put secure frp 0`, `user_setup_complete`, `device_provisioned`, `setup_wizard_has_run`, `/data/system/frp` kaldırma ve kurulum sihirbazını devre dışı bırakma). Motorola ayrıca `com.motorola.setupwizard` paketini devre dışı bırakma imkânı sunar. Bu yalnızca yetkili bir ADB kabuğu zaten varsa çalışır.

- **Fastboot yolu** CVE-2016-10277 (initroot) zinciridir; dürüst kapılarla aşamalı biçimde çalışır: önyükleyici sürüm kontrolü, `fsg-id` UTAG canlılığı okuma (`protected="false"` veya dur), kullanıcı tarafından sağlanan cihaz bazlı initramfs, ardından `oem config fsg-id a initrd=<addr>,<size>` + tampon içeriğine indirme + kök ADB oturumuna `continue` giriş. Kamuya açık araştırma: alephsecurity/initroot. Daha yeni önyükleyiciler enjeksiyonu içerik filtresiyle engeller — akış bunun yerine bunu bildirir.
- **QR yolu**, Google/FRP kontrolünü atlayarak cihaz sahibi sağlama yapar: oluşturulan QR'yi kurulum sihirbazının Hoş Geldiniz ekranında tarayın, kaydı kabul edin, ADB isteminde Tamam'ı dokunun, akış yetki verildiğinde FRP'yi temizler.

## Dürüst sınırlar

- **Önyükleyici kilit açma kodu cihaz bazlı olarak sunucudan üretilir** (Motorola portalı; Verizon/AT&T/Tracfone modelleri uygun değildir). Çevrimdışı üretebilecek hiçbir yerel araç — FlashPilot dahil — yoktur. `fastboot_unlock --code` iki adımlı onayı otomatikleştirir ancak Android tarafındaki OEM kilit açma anahtarı önce AÇIK olmalıdır.
- **initrd enjeksiyonu daha yeni önyükleyicilerde düzeltilmiştir** (2020+ derlemelerde `initrd=` bile korunmasız UTAG ile birlikte içerik filtresi uygulanır). Akış UTAG'ı okur ve bunu raporlar; realist alternatif QR yoludur.
- Bazı **taşıyıcı varyantları `oem unlock` özelliğini tamamen devre dışı bırakır**; bu durumda ADB yolu tek rota olur ve zaten yetkili bir ADB kabuğu gerekir.
- Sizinkine ait olmayan veya bakımını yetkisiz biçimde yaptığınız bir cihazda FRP kaldırma, yargı alanınıza göre yasadışı olabilir.

## İlgili cihaz notları

- `moto_g6.md` — Moto G6 (SDM450), eski Android 8/9 tarayıcı/acil durum FRP.
- `../mdm/devices/motorola/` — Motorola MDM akışları.
