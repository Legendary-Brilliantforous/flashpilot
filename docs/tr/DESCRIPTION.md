# FlashPilot 1.2.1 — Kararlı (Stable)

Language switcher: [English](../../DESCRIPTION.md) · [Français](../fr/DESCRIPTION.md) · [Español](../es/DESCRIPTION.md) · [Deutsch](../de/DESCRIPTION.md) · [简体中文](../zh/DESCRIPTION.md) · [Русский](../ru/DESCRIPTION.md) · [Português](../pt/DESCRIPTION.md) · [日本語](../ja/DESCRIPTION.md) · [العربية](../ar/DESCRIPTION.md) · [हिन्दी](../hi/DESCRIPTION.md) · **Türkçe**

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

Açık kaynaklı, Android cihazlar için Linux flash ve onarım çalışması masası — ticari Windows flash paketlerinin ücretsiz eşdeğeri. **1.2.0 bir kararlılık + ilerleme sürümüdür: `cargo check` 0 uyarı, `cargo test` 60 + `pytest` 149 geçti, canlı GitHub yayın kanalı ve denetlenebilir geçmiş.**

Yerel bir **Rust** çekirdeği (`flashpilot-bridge`, ~9.300 satır kod, dahili libusb) önyükleyici (bootloader) protokolleriyle doğrudan konuşur — Samsung Odin/HID, MediaTek BROM/DA, Qualcomm Sahara/Firehose, Spreadtrum/UNISOC BSL — ve cilalanmış bir **PyQt6** stüdyosu 9 taşıma, 13 iş kategorisi ve ~120 işlem sunar: flash, FRP bypass, ekran kilidi kaldırma, MDM kilit açma, bölüm araçları, cihaz bilgisi, yeniden başlatma, ayrıca herhangi bir ADB cihazında batarya/ağ onarımı.

**1.2.0 kararlı sürümündeki yenilikler:**
- **0 uyarı köprü** — 18 ölü yol bağlandı: AT `Context` tutma ve `vid` doğrulama (`+DEBUGLVC` sonrası `AT/control` yeniden numaralandırma), USB `EndpointConfig.max_packet_size` parçalama ve `open_target/read_exact/info`, SPD `BSL_CMD`/`BSL_REP` + `iface` + `flush/read_flash/chip_uid/power_off`, `ProgressReporter` → gerçek flash %, Qualcomm `QcomDeviceInfo`/`FirehosePacket`, MTK `read16/write16` — `-80KB` `lto`, tanıtıcı (handle) sızıntısı yok.
- **Dinamik sürüm** — yüklü `importlib.metadata`'dan `APP_VERSION` (deb `pyproject.toml` hakiki kaynak), `_display_version` `1.2.0→1.2` / `1.2.1→1.2.1`, canlı GitHub `latest stable` (asla kodla sabitlenmiş), logoda/başlık çubuğunda BETA rozeti.
- **Birleşik büyük diyaloglar** — 620px ortalanmış sürüklenebilir kartlar (320px toast yerine) yüksek kontrastlı `#e2e8f0` metin, `✕` + `X` sürükleme, p­ing renkleri: `MTK amber`, `QCOM red`, `SPD violet`, `SAMSUNG blue`; beta geçidi `I accept` onay kutusu ister (sürüm başına kalıcı, `first_install` öntanımlı / `every_boot` toggle Ayarlar → Güncellemeler), `Exit` uygulamayı kapatır, kararlı `UPDATE/AHEAD/PATCH` aynı büyük diyalogu kullanır, flash/FRP onay katmanları pinstances degradesi kullanır.
- **Tek küresel STOP** — başlık çubuğunda (kart dışında) tek `⏹ STOP`, 150ms `_FLOW_LABEL` ile senkron, *tüm* Samsung/MTK/QC/SPD akışlarını durdurur; eski çip başına Stop'lar gizlendi.
- **Yönetişim** — `dev`/`main` korumalı: `strict` CI `Rust+Python`, `1` inceleme, `dismiss_stale`, `require_last_push_approval`, `linear_history`, `force_push:false`; `devin-ai-integration[bot]` geçmiş/tag `v1.2.1-beta.1` → `55c0da3` üzerinden kaldırıldı.

- **Platform:** Linux
- **Dil:** Rust (çekirdek) + Python 3.10+ / PyQt6 (UI)
- **Lisans:** MIT
- **Durum:** kararlı 1.2.0 — katkıda bulunanlar hoş geldiniz

Yalnızca sahip olduğunuz veya hizmet vermeye yetkili olduğunuz cihazlarda kullanın.