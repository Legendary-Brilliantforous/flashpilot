# FlashPilot 1.2.1 — Стабильный релиз

Language switcher: [English](../../DESCRIPTION.md) · [Français](../fr/DESCRIPTION.md) · [Español](../es/DESCRIPTION.md) · [Deutsch](../de/DESCRIPTION.md) · [简体中文](../zh/DESCRIPTION.md) · **Русский** · [Português](../pt/DESCRIPTION.md) · [日本語](../ja/DESCRIPTION.md) · [العربية](../ar/DESCRIPTION.md) · [हिन्दी](../hi/DESCRIPTION.md) · [Türkçe](../tr/DESCRIPTION.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

Открытая Linux-мастерская для прошивки и ремонта Android-устройств — бесплатный
аналог коммерческих Windows-пакетов прошивки. **1.2.0 — релиз стабильности и
развития: `cargo check` 0 предупреждений, `cargo test` 60 + `pytest` 149 зелёных,
живой канал релизов GitHub и аудируемая история.**

Нативное **Rust**-ядро (`flashpilot-bridge`, ~9 300 LOC, встроенный libusb)
говорит с загрузчиками напрямую — Samsung Odin/HID, MediaTek BROM/DA,
Qualcomm Sahara/Firehose, Spreadtrum/UNISOC BSL, — а отполированная **PyQt6**
студия показывает 9 транспортов, 13 категорий задач и ~120 операций: прошивка,
обход FRP, снятие блокировки экрана, разблокировка MDM, инструменты разделов,
информация об устройстве, перезагрузка, ремонт батареи и сети на любом
ADB-устройстве.

**Что нового в стабильном 1.2.0:**
- **0 предупреждений в мосту** — подключено 18 мёртвых путей: удержание `Context` AT и валидация `vid` (повторное перечисление `AT/control` после `+DEBUGLVC`), chunking `EndpointConfig.max_packet_size` USB и `open_target/read_exact/info`, SPD `BSL_CMD`/`BSL_REP` + `iface` + `flush/read_flash/chip_uid/power_off`, `ProgressReporter` → реальный % прошивки, Qualcomm `QcomDeviceInfo`/`FirehosePacket`, MTK `read16/write16` — `-80KB` `lto`, утечек дескрипторов нет.
- **Динамическая версия** — `APP_VERSION` из установленного `importlib.metadata` (deb `pyproject.toml` — истина), `_display_version` `1.2.0→1.2` / `1.2.1→1.2.1`, живой GitHub `latest stable` (никогда не захардкожен), значок BETA на логотипе/заголовке.
- **Единые большие диалоги** — центрированные карточки 620px (против тоста 320px) с высококонтрастным текстом `#e2e8f0`, `✕` + перетаскивание `X`, цвета чипов: `MTK amber`, `QCOM red`, `SPD violet`, `SAMSUNG blue`; бета-шлюз требует чекбокс `I accept` (запоминается на версию, переключатель `first_install` по умолчанию / `every_boot` в Настройки → Обновления), `Exit` закрывает приложение, стабильные `UPDATE/AHEAD/PATCH` используют тот же большой диалог, оверлеи подтверждения прошивки/FRP используют градиент чипа.
- **Единый глобальный STOP** — один `⏹ STOP` в заголовке (вне любой карточки), синхронизация за 150 мс в `_FLOW_LABEL`, останавливает *любой* поток Samsung/MTK/QC/SPD; устаревшие STOP на каждом чипе скрыты.
- **Управление** — защищены `dev`/`main`: CI `strict` Rust+Python, 1 ревью, `dismiss_stale`, `require_last_push_approval`, `linear_history`, `force_push:false`; `devin-ai-integration[bot]` удалён из истории/тега `v1.2.1-beta.1` → `55c0da3`.

- **Платформа:** Linux
- **Язык:** Rust (ядро) + Python 3.10+ / PyQt6 (UI)
- **Лицензия:** MIT
- **Статус:** стабильный 1.2.0 — контрибьюторы приветствуются

Используйте на устройствах, которыми владеете или имеете право обслуживать.