# motorola_unlock.md — Motorola unlock, Valeria, patcher, firmware

Moto-M Tool 4.2.2'nin resmî Motorola bootloader unlock, sunucu odaklı "Valeria" LK-swap unlock/FRP, ROM patcher, firmware mirrorlar ve QR tabanlı ADB kaydı nasıl yaptığını açıklar.

## Resmî Motorola web unlock (`start_unlock`, L2643)

### Akış

```
start_unlock
 └─ update_labels(state_mode='locked')          # cihaz bilgisi doldurur, is_penangf_device ayarlar
 └─ data = get_unlock_data(is_penangf_device)   # ≥4 parçaya sahip olmalı
 ├─ [PenangF] → start_penangf_unlock(data)      # aşağıya bak
 └─ [Normal Motorola]
     1. GET https://en-us.support.motorola.com/cc/productRegistration/
              verifyPhone/{data[0]}/{data[3]}/{data[2]}/
        headers: {'Cookie': '; '.join(f'{k}={v}')}     # oturum çerezleri
        200 + body içinde 'Phone qualifies' varsa OK; 'Not qualified' → iptal
     2. cookies = load_cookies()                       # GitHub blob + Fernet
     3. send_request_and_set_timestamp (thread):
        - sync_time_windows()                          # Windows NTP yeniden eşitleme
        - request_timestamp = now(UTC)
        - GET .../unlockPhone/{data[0]}/{data[3]}/{data[2]}/ with Cookie header
        - 200 → success_timestamp = now
     4. POST https://studiomaiky.com/get-unlock-candidates
        {"server_id": 1, "request_timestamp": <epoch>, "success_timestamp": <epoch>,
         "consume": true}
        ← {'candidates': [{'code': ...}, ...]} → dedupe, strip, upper
     5. for each code (0.3 s pause on failure):
        fastboot oem unlock <code>
        success = ('successful' AND 'unlocked') in output OR 'already unlocked'
```

### Önemli gerçekler

- URL şablonları data sırası **0/3/2** kullanır (0/1/2 değil) `fastboot oem get_unlock_data` çıktısının 4 parçasından (`get_unlock_data`, L2490; regex `^\(bootloader\)\s(.*)$` MULTILINE, `Unlock data:` temizleme, `#` ile split).
- **IMAP ölü koddur**: `IMAP_SERVER = 'imap.gmail.com'` (L77) ve `load_config()` (Fernet ile şifrelenmiş Gmail `email`+`app_password`, L2302) v4.2.2'de asla çağrılmaz. Daha eski sürümler OTP e-postasını IMAP aracılığıyla okur; v4.2.2 bunu ücretli `/get-unlock-candidates` çağrısıyla değiştirdi. Açık kaynak yeniden uygulama, kullanıcı tarafından sağlanan app password ile OTP e-postasını doğrudan IMAP üzerinden okuyabilir.
- Çerezler `https://raw.githubusercontent.com/Maikyxd/Cookie/main/cookies_moto3.json` (yedek `cookies_moto1.json`) kaynağından gelir, Fernet ile sunucu anahtarıyla şifresi çözülür (`GET /get-key` → `{'key': ...}`), ardından `json.loads` ile parse edilir (`load_cookies`, L2331).
- PenangF cihazlar (Moto G23/G13, `ro.product.device == 'penangf'`) `fastboot oem get_key` kullanır (`get_unlock_data(is_penangf_device)`).

### PenangF unlock (`start_penangf_unlock`, L4062)

```
key = unlock_data.strip()                # tam 32 hex karakter
POST /generate-oem-key  {"key": "<32-char>"}  ← {'oem_key': '...'}
fastboot oem key <oem_key>               # OKAY yazmalı
fastboot flashing unlock                 # OKAY yazmalı
fastboot reboot
```

## Valeria — sunucu odaklı LK-swap unlock/FRP (`run_valeria_operation`, L3325)

Uç nokta: `POST https://studiomaiky.com/val-protocol` ile
`{'action': <action>, **payload}`, herkese açık başlıklar
(`HWID/TIMESTAMP/VERSION-HASH`).

### Yük (tüm eylemler)

```python
{'operation': 'unlock'|'frp'|'unlock_frp',
 'serialno': <fastboot getvar serialno>,
 'codename': device_info['Codename'], 'model': device_info['Model'],
 'android_version': ..., 'secure_state': ..., 'frp_active': ...,
 'noise': {                       # anti-abuse fingerprint (L2891)
   'cid_prov_req': fastboot oem cid_prov_req output (last 4000 chars),
   'unlock_data':  fastboot oem get_unlock_data output,
   'read_sv':      fastboot oem read_sv output }}
```

### Eylemler

| Eylem | Gönderilen | Alınan |
|---|---|---|
| `quote` | payload | `{'operation_id', 'cost'/'required_credits', ...}` (timeout 180); UI confirm dialog |
| `check_credits` | payload | `{'required_credits', 'available_credits'}` |
| `patched_lk` | payload | **ham ikili yamalanmış LK** (streamed, 256 KB parçalar) |
| `frp_command` | payload | `{'command': 'fastboot ...', 'charged_credits'}` |
| `unlock_key` | payload | `{'key': '...', 'charged_credits'}` |
| `original_lk` | payload | **ham ikili stok LK** (geri yükleme için) |
| `upload_log` | `{'operation_id', 'log_text', 'status'}` | best-effort (timeout 30) |

### İşlem akışı

```
1. update_labels (fastboot device info)
2. Guards:
   - unlock & already unlocked → stop; unlock & not locked → stop
   - frp & unlocked bootloader → stop; frp & FRP not active → stop
   - MTK gate: fastboot oem partition → must contain 'nvram'   (L2820)
3. quote → check_credits → patched_lk
4. flash patched LK → lk_a/lk_b/lk (mevcut slot seçilir; L3144)
5. fastboot reboot bootloader (wait ≤90 s)
6. [frp]      frp_command → run server command (120 s) → check frp-state;
              still active → restore original LK + reboot; else success
   [unlock*]  unlock_key → fastboot oem unlock <key> (user: Vol-down + power)
              success string tolerance ('bootloader is unlocked',
              'rebooting to fastboot' vb., L3206) → wait disconnect ≤8 s,
              reconnect ≤90 s → check state → not unlocked → restore LK
7. restore original_lk on EVERY exit path (_valeria_restore_original, L3240)
8. upload_log (logs/valeria_{ts}.log)
```

LK flashing, pyfastboot streaming ile yapılır (`_valeria_flash_lk`, L3176):
`_protocol.SendCommand(b'download', b'%08x' % size)` +
`HandleDataSending(source, size, info_cb)` + `Flash(partition)` —
özünde `fastboot download` + `fastboot flash lk_a` ancak RAM patlamadan.

Durum setleri (L2769): `VALERIA_UNLOCKED_STATES = {'1','yes','true','enable',
'unlocked','engineering','oem_unlocked','flashing_unlocked','non-secure'}`;
`VALERIA_LOCKED_STATES = {'0','no','false','locked','secure','oem_locked',
'flashing_locked'}`.

**Tasarım noktası**: yamalanmış LK (imza doğrulamasını atlatır) sadece geçici olarak yazılır — stok LK her yolda geri yüklenir. Yamalı/stok LK imajları sunucudan cihaz bazlı gelir.

## ROM patcher (`_patcher_patch_rom_flow`, L3859)

```
1. _load_erofs_api('MTool_EROFS.dll')    # pythonnet reflection → MToolErofsApi
2. find super image: super.img|super.bin, or super.img_sparsechunk.N series
3. workdir = source_folder (patch in place) OR <dest>/<name>_patched (copytree)
4. xml = flashfile.xml — find, else generate from scatter.txt (MTK) or
   update_flash.bat (SPD) (_patcher_ensure_flashfile_xml, L3719)
5. _patcher_normalize_boot_gki: rename boot-gki.img → boot.img (L3700)
6. _patcher_clean_unused_files: delete files not referenced in <step> (L3744)
7. POST /patcher-rom {'action': 'get_assets'}
   ← {'hosts_rules': str, 'apk_list_json': str, 'default_signature': str}
8. signature = custom or default or 'Moto-M Tool Power'
9. MToolErofsApi.PatchRom(target_super, signature, hosts_path, apk_list_path)
   # .NET EROFS patch: injects hosts file + APKs + signature into super
10. POST /patcher-rom {'action': 'register', 'codename', 'signature'}
   ← {'rom_id', 'decrypt_key': '<hex>'}
11. encrypt modified files (super chunks only) with AES key from decrypt_key
12. write mtool_rom.json = {'rom_id': ..., 'encrypted_files': [basenames]}
```

### Şifreleme şeması (`_patcher_encrypt_file_in_place`, L3817)

- **AES-256-CTR**, yeni `os.urandom(16)` nonce dosyanın **ilk 16 baytı** olarak yazılır, ardından ham ciphertext; 4 MiB parçalar halinde akışlı (`_PATCHER_AES_CHUNK_SIZE = 4194304`); atomik `os.replace`.
- Ters işlem (`_patcher_decrypt_file_chunks`, L3844): 16 bayt nonce oku → CTR decryptor → parça parça decrypt.
- Yamalı ROM flash (`_patcher_flash_rom_flow`, L4011): `mtool_rom.json` gerektirir → `POST /patcher-rom {'action': 'get_key', 'rom_id',
  'codename'}` → `{'decrypt_key'}` → tüm flashfile.xml adımlarını pyfastboot streaming ile sırayla flash eder; super parçaları sparse streaming olarak yeniden paketlenir (`_produce_super_subimages`, L7295).

### Üretilen flashfile XML (scatter → flashfile, L3443)

```xml
<flashing><header>
  <phone_model model="Moto-M_Tool"/>
  <software_version version="Moto-M_Tool_Power"/>
  <cid_value value="0x0032"/>
  <sparsing enabled="true" max-sparse-size="536870912"/>   <!-- 512 MiB -->
  <interfaces><interface name="AP"/></interfaces>
  <steps interface="AP"> flash steps from scatter (skip lk, lk_a)
        + <step operation="erase" partition="userdata"/>
        + <step operation="erase" partition="metadata"/> </steps>
```

Sparse görüntü sabitleri (L6983): sihir `0xED26FF3A`, 28 bayt dosya başlığı,
12 bayt chunk başlığı, chunk türleri RAW=51905, FILL=51906, DONTCARE=51907,
CRC32=51908.

## Firmware mirrorlar (`get_base_url`, L6270)

Model yılına göre ("Moto G54 5G" gibi model adından kodename üzerinden):

```
≥2022:  https://mirrors.lolinet.com
2020–2021: https://mirrors-obs-1.lolinet.com
≤2019: https://mirrors-obs-2.lolinet.com
```

`download_firmware` (L6296): çalışma dizini `./Cleanfirm`; taşıyıcılar sıralı denenir `[<device carrier>, 'RETUS', 'RETAIL']`; indeks URL
`{base}/firmware/lenomola/{year}/{codename}/official/{carrier}/`;
BeautifulSoup scrape → `a[href$='.zip']`; build-version regex
`([A-Za-z0-9]+\.[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+)` değilse en eski; aiohttp indirme ile Range resume (`sync_download_with_aiohttp`, L715).

Blankflash (L6507): `{base}/firmware/lenomola/{year}/{codename}/blankflash/`
→ en yeni `lastmod` seçilir → `./Blankflash/<codename>/` içine indirilir → çıkarılır (zip/py7zr) → `blank-flash.bat` çalıştırılır (`cmd /c`) → 5 s sonra thread `fastboot reboot` tetikler.

## QR kodu / ADB kaydı (`generate_qr`, L6688; `get_temporary_link`, L6653)

```
GET /get-download-link  → {'url': '<temporary APK link>'}
```

QR yükü (Android cihaz-sahibi provisioning JSON):

```json
{"android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME":
    "com.motomtool.motomtool/.Hubris",
 "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION": "<temporary link>",
 "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_CHECKSUM": "1Rt3KUAT4o46zO7pWaQa6j_GNb_UDgNhdgHFglp2zwU",
 "android.app.extra.PROVISIONING_SKIP_ENCRYPTION": true,
 "android.app.extra.PROVISIONING_LEAVE_ALL_SYSTEM_APPS_ENABLED": true,
 "android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE": {}}
```

Checksum sabitlenmiş base64url SHA-256'sıdır. `generate_qr`: `qrcode.QRCode(box_size=10, border=2)`, renkler `motoicon.ico` içindeki iki baskın rengin tonları, simge ¼ boyutunda ortalanır, 500×500 çıktı. Pencere başlıkları: "Scan to Enable ADB" / "Scan In Setup Wizard".

FlashPilot'ın kendi MDM QR akışı `python/gui/` + `build/mdm_qr/` içinde yaşar — aynı provisioning-anahtar fikri, kendi uygulaması.

## CVE-2016-10277 / initroot — fastboot FRP stratejisi (FlashPilot, kendi araştırması)

Unlock-token yolu emekliye ayrıldı: 20 karakterlik kod cihaz bazlı, sunucu tarafından verilmiş (Motorola portalı), üretilemez veya genellenemez — araç düzeyi token stratejisi gerçek cihazlarda bir çıkmaz.

Strateji bunun yerine **CVE-2016-10277** kullanır (genel araştırma: alephsecurity/initroot — Roee Hay / Aleph Research, HCL Technologies; Motorola bootloader içindeki `fsg-id` UTAG üzerinden kernel cmdline enjeksiyonu):

```
1. fastboot oem config fsg-id ""                       # UTAG oku — gate
2. fastboot oem config fsg-id "a initrd=<ADDR>,<SIZE>"  # cmdline injection
3. fastboot flash foo initroot-<device>.cpio.gz         # ADDR'de bufferlanır
   (Invalid partition name hatası beklenir — amaç payload bootloader indir bufferında kalmaktır)
4. fastboot continue                                    # enjeksiyonu başlatır
   → kernel injected initramfs'i yükler → ADB daemon root (uid 0),
   yetkilendirme istemi yok, dm-verity devre dışı
5. root ADB: dd if=/dev/zero of=/dev/block/bootdevice/by-name/frp
   + reboot → FRP yok
```

Dürüst gate'ler `flow_moto_frp_fastboot` içinde uygulanmıştır (Rust):

- **Version gate**: `getvar version-bootloader` — enjeksiyon Kernel-3.10/3.18 bootloader ailesine hedeflenir (Moto G4/G5/X/Z dönemi). Daha yeni bootloader'lar (G6 ve sonrası) UTAG'ı genellikle korur; akış bunu okur ve raporlar.

- **UTAG liveness gate**: `oem config fsg-id` geri okumada `protected="false"` döndürmeli; aksi halde akış durur ve CVE'nin burada yamalanmış olduğunu söyler.
- **No shipped exploit images**: cihaz bazlı initramfs (`initroot-<device>.cpio.gz`) asla uygulama ile dağıtılmaz — akış `--file <initramfs> --partition <scratch_addr>` bekler ve üretimi için kamuya açık araştırmaya işaret eder (scratch adresleri cihaz bazlıdır: 0xA2100000 cedric, 0x92000000 athene, initroot README'ye göre).

Exploit tabanlı stratejileri nasıl ele alır (gelecek CVE'ler için çerçeve):

1. **Aşama zincirini hazırla** — her adım, transkript içindeki kendi akış adımıdır; kullanıcı her komutu çalıştırmadan önce görür.
2. **Dürüst kapı kullan** — exploit için gereken her ön koşul açıkça kontrol edilir (UTAG koruması, bootloader sürümü, cihaz bazlı yük mevcutluğu); başarısız kapı, başarı gibi davranmak yerine rehberlik içeren şekilde DURUR.
3. **Payload asla teslim etme** — model özel exploit varlıkları uygulamanın içinde kalmaz; akış kullanıcı tarafından sağlanan yolları kabul eder ve kamu kaynaklarını belgeler.
4. **Yedek her zaman belirtilir** — bir exploit kapısı başarısız olursa akış gerçekçi alternatifi adlandırır (ör. ADB etkinleştirildikten sonra ADB yolu) ve araştırma backlog'u sonraki doğrulanan vektör için hazır tutar.

## Kendi DPC üzerinden sahte giriş (FlashPilot, kendi uygulaması)

TestDPC tarzı akışlar Google'ın Play Store örnek uygulamasına bağımlıdır.
FlashPilot bunun yerine kendi minimal device-owner uygulamasını sunar:

- Kaynak: `android/FlashPilotDPC/` (`org.flashpilot.dpc`, minSdk 24,
  targetSdk 28, G6 çağının uyumuna göre). Destek kütüphanesi yok; yönetici XML dışında kaynak yok — SDK cmdline araçlarıyla derlenir
  (`android/FlashPilotDPC/build.sh`: aapt2 -> javac -> d8 ->
  zipalign -> apksigner).
- `FpAdminReceiver.completeSetup()` (idempotent) "sahte giriş" işlevi görür:
  `USER_SETUP_COMPLETE=1` (Secure), `DEVICE_PROVISIONED=1` (Global),
  `ADB_ENABLED=1` (Global), `com.google.android.setupwizard` +
  `com.motorola.setupwizard` gizler ve `setApplicationHidden` çağırır,
  ardından `setUserSetupComplete()` çağırır. `ACTION_PROFILE_PROVISIONING_COMPLETE` üzerinde otomatik çalışır ve MainActivity düğmesinden manuel olarak da çalıştırılabilir.
- Akış `frp_fake_login` (Rust): APK'yı çözer (`--file` / FRP_DPC_APK ortamı / varsayılan `mdm_qr/serve/flashpilot-dpc.apk`, eksik olursa yapıcı talimatlarla dürüst hata), QR için v1 imza sertifikası checksum'ini (SHA-256, base64url) hesaplar, indirme URL'si için LAN IP'yi tespit eder (FRP_DPC_APK_URL geçersiz kılmayı destekler), QR'ı paylaşılan provisioning yardımcı ile üretir, APK dizinini :8000 portunda servis eder (best-effort, canlı sunucuyu yeniden kullanır), DPC'nin etkinleştirdiği yetkili ADB oturumunu 10 dakika kadar bekler, ardından standart FRP-temizleme adımlarını çalıştırır ve yeniden başlatır.
- GUI: Motorola FRP REMOVE menüsünde "Fake Login · QR" satırı, akışı ("Remove FRP", "ADB") altında çalıştırır.

## Aşamalı fastboot yükleri — sunucu olmadan FRP kaldırma (FlashPilot, kendi uygulaması)

G6 (ali) için EDL yolu yok: `oem edl` desteklenmiyor, 05c6:9026 bileşim diag/Android tarafı (Sahara değil), ve EDL akışı (`moto_edl_adb`) emekliye ayrıldı — anahtarı artık `moto_fb_frp` işaret eden bir işaretçiye dönüştü. Kalan şey fastboot, Moto-M şekli, tümü yerel.
Akış `moto_fb_frp` (kayıt: Remove FRP / FASTBOOT; GUI: Motorola →
FRP REMOVE → Fastboot Staged FRP):

```
Stage 0 (--firmware-dir, required): flash signed stock firmware in
  flashfile.xml order over fastboot. Every image MD5-verified first;
  refusals (downgrade/validation) abort with the device's own lines.
Stage 1 (up to 3 cycles): reboot, then act per the mode ACTUALLY seen —
  ADB authorized -> wipe (moto_adb_frp_wipe) -> reboot -> done;
  ADB unauthorized -> prompt the on-phone tap (Moto-M style), wipe on
  success; fastboot back -> state check + cache clear + reboot again;
  dark -> cable/button guidance.
Exhausted (no ADB in 3 cycles): honest stop naming QR fake-login
  (frp_fake_login*), which needs no exploit at all.
```

İlk canlı çalıştırmanın dersleri (Ekim 2026): ilk sürüm, reddetmeler sonrası yazmaya devam etti ve ardından veri bölgesini silmeye çalıştı — yararı olmayan bir silme. Şimdi bir cihaz-FAILED flash bayrağı koyar ve sonraki tüm silme adımlarını atlar (transkript içinde anlatılır), silme banner'ı hiçbir şey çalıştırılmadan önce yazdırılır. Live result on ali: 8.0 set refused throughout on downgrade/validation (9.0 fuses), modem/fsg/dsp/logo OK, userdata wiped, cycles saw nothing on USB — exited honestly naming QR.

Akış ve burada net şekilde belirtilen kapsam: her komut belgelenmiş yerel fastboot/ADB komutudur. Moto-M'nin per-boot payload baytları sunucudan gelir ve istemci tarafında görünmezdi, bu yüzden kopyalanmadılar — ve temiz imzalı flash + yeniden başlatma kendiliğinden ADB'yi etkinleştirmez. Akış bunun gibi davranmaz.

Why fastboot writes are closed on ali (all proven live on the G6,
MBM-2.1-32ffece02ed-200416, oem_locked) — kept as the record:

- `fastboot flash boot` (patched, 23 MB): `Image size exeeded partition
  limits` + `Preflash validation failed`.
- `fastboot flash boot` (signed stock 8.0): `Security version
  downgrade` + `Image boot failed validation` (phone runs 9.0 fuses).
- Same (trimmed to 11 MB content): `Image boot failed validation`.
- `fastboot erase cache`: OKAY (erase path works, per-partition ACL).
- `fastboot erase frp`: `Permission denied` — the exact partition is
  ACL-protected over fastboot.
- Unsigned boot images could never boot here anyway: a locked
  bootloader verifies boot.img at every startup.

Supporting pieces (all local, all verified against real ali files):

- `boot-patch-adb --prop-file`: ali's ramdisk `default.prop` is a
  SYMLINK into /system — the patcher now detects this: without
  --prop-file it errors honestly (instead of corrupting the link);
  with it, the link becomes a regular file holding the real system
  props + forced `ro.adb.secure=0 ro.secure=0 ro.debuggable=1
  persist.sys.usb.config=mtp,adb`. Verified byte-level on the real
  OPS27.82-19-4 boot.img (mode 000081A4, fingerprint intact, system
  untouched so dm-verity stays happy). (Kept as a general tool; the
  staged flow no longer needs it — unsigned images can't boot locked.)
- EDL-only helpers (`moto-extract-programmer`, `moto-extract-prop`,
  Sahara upload) were removed with the retired flow; the findings stay
  above as the record.

Dürüst kapılar: aşamalı akış `--firmware-dir` gerektirir (imzalı stok); sürüm uyuşmazlığı olan bir set, cihazın kendi downgrade/validation satırları nedeniyle iptal olur. 3 döngü içinde ADB görünmezse durur ve QR fake-login'i adlandırır.

## Canlı tarama notları (Moto G6 ali, MBM-2.1-32ffece02ed-200416, oem_locked)

Bu bootloader üzerinde `fastboot oem help` şunları listeler: config, hw, partition,
fb_mode_set/clear, bp-tools-on/off, qcom-on/off, unlock, lock,
get_unlock_data, cid_prov_req, read_sv, off-mode-charge, show_screen — EDL komutu yok. Canlı sonuçlar:

- `fastboot oem edl` → `FAILED ('edl' is not a supported oem command)`.
- `fastboot oem qcom-on` / `qcom-off` → OKAY ama fastboot içinde USB değişmez (05c6 anahtarı yok, ttyUSB yok); temiz şekilde geri alındı.
- `fastboot boot` → reddedildi (locked); initrd `fsg-id` enjeksiyonu → bu 2020 build üzerinde filtrelendi; unlock kodu geçerli ama Android tarafı OEM-unlock anahtarı tarafından engellendi.
- Önceki `05c6:9026` bileşimi bir diag/Android tarafı modudur, Sahara değildir — Firehose gerçek 9008/900E gerekir.

Yani bu ünite üzerinde her yazılım EDL girişi kapalıdır; aşamalı akış EDL kapısına kadar çalışır ve bekler. Giriş bir test noktası (veya EDL kablosu) adımıdır, ardından zincir sessizce devam eder.

## Üçlü DPC sahte giriş (FlashPilot, kendi uygulaması)

Yazılım, QR provisioning için üç device-owner seçeneği sunar; tümü tek bir akış üzerinden çalıştırılır (`frp_fake_login`, `--dpc ours|testdpc|adp`, FRP_DPC_CHOICE env, her biri için ayrı kayıt satırı):

1. **ours** — `org.flashpilot.dpc/.FpAdminReceiver`
   (`android/FlashPilotDPC/`, APK `mdm_qr/serve/flashpilot-dpc.apk`).
   Kayıt sırasında sahte girişi kendisi yapar. minSdk 26, targetSdk 28
   (Android 8 ile 14 arası): sürüm korumalı çağrılar (gizli yedek ile askıya alma, DPM + doğrudan ADB yazıları, `setUserSetupComplete` yalnızca 28+ üzerinde, `android:exported` 31+ için ayarlanmış). E-posta kapısı: erişim e-postası derleme zamanında gömülüdür (`FP_ACCESS_EMAIL`, varsayılan `flashpilot@local` -> oluşturulan `AccessConfig.java`); QR bunu `PROVISIONING_ADMIN_EXTRAS_BUNDLE.fp_email` içinde taşır, böylece uygulama önceden doldurur ve girilmesi provisioning'i açar. Cihaz-sahibi otomatik çalıştırma kapıyı atlar (kayıtın kendisi yetkilendirmedir).
2. **testdpc** — `com.afwserv.testdpc/.DeviceAdminReceiver`, yerel
   `mdm_qr/serve/testdpc.apk` tercih edilir (LAN URL + v1 sertifika checksum), dosya yoksa Play Store URL yedeği.
3. **adp** — `com.google.android.apps.work.oobconfig/.DevAdminReceiver`
   (Android Device Policy), Play Store URL (yerel APK yok, sertifika yok, servis adımı yok).

"Bilgisayarda çevrimiçi ayarla": akış :8000 üzerinde yerel APK dizinini servis eder (best-effort, canlı sunucuyu yeniden kullanır) ve telefon adımlarını yazdırmadan önce portun yanıt vermesini bekler; böylece indirme URL'si canlı doğrulanır.
Extras, FRP_DPC_EXTRAS_JSON ile birleştirilir (genel, geriye dönük uyumlu).
