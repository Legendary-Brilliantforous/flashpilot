# FlashPilot 1.2.1 — Estable

Language switcher: [English](../../DESCRIPTION.md) · [Français](../fr/DESCRIPTION.md) · **Español**

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

Banco de trabajo open source de flasheo y reparación para dispositivos Android en Linux — el equivalente gratuito de las suites comerciales de flasheo para Windows. **1.2.0 es una versión de estabilidad + avance: `cargo check` con 0 advertencias, `cargo test` 60 + `pytest` 149 pasan, canal de release en GitHub en vivo e historial auditable.**

Un núcleo nativo **Rust** (`flashpilot-bridge`, ~9 300 LOC, libusb incluido) habla directamente con los protocolos de bootloader — Samsung Odin/HID, MediaTek BROM/DA, Qualcomm Sahara/Firehose, Spreadtrum/UNISOC BSL — mientras que un estudio **PyQt6** pulido presenta 9 transportes, 13 categorías de jobs y ~120 operaciones: flasheo, bypass FRP, eliminación de bloqueo de pantalla, desbloqueo MDM, herramientas de partición, info de dispositivo, reinicio y reparación de batería/red en cualquier dispositivo ADB.

**Novedades de 1.2.0 estable:**
- **Puente con 0 advertencias** — se cablearon 18 rutas muertas: retención del `Context` AT y validación `vid` (re-enumeración `AT/control` tras `+DEBUGLVC`), troceado `EndpointConfig.max_packet_size` y `open_target/read_exact/info`, SPD `BSL_CMD`/`BSL_REP` + `iface` + `flush/read_flash/chip_uid/power_off`, `ProgressReporter` → % real de flasheo, Qualcomm `QcomDeviceInfo`/`FirehosePacket`, MTK `read16/write16` — `lto` -80 KB, sin fugas de handles.
- **Versión dinámica** — `APP_VERSION` desde `importlib.metadata` instalado (el `pyproject.toml` del deb es la verdad), ` _display_version` `1.2.0→1.2` / `1.2.1→1.2.1`, GitHub `latest stable` en vivo (nunca codificado a mano), píldora BETA en logo/barra de título.
- **Grandes diálogos unificados** — tarjetas centradas de 620 px arrastrables (frente al toast de 320 px) con texto de alto contraste `#e2e8f0`, arrastrar por `✕` + `X`, colores de chip: `MTK ámbar`, `QCOM rojo`, `SPD violeta`, `SAMSUNG azul`; la puerta beta requiere casilla `I accept` (persiste por versión, `first_install` por defecto / toggle `every_boot` en Ajustes → Actualizaciones), `Exit` cierra la app, stable `UPDATE/AHEAD/PATCH` usan el mismo gran diálogo, las superposiciones de confirmación de flasheo/FRP usan el gradiente del chip.
- **Un solo STOP global** — un único `⏹ STOP` en la barra de título (fuera de cualquier tarjeta), sincronización en 150 ms hacia `_FLOW_LABEL`, detiene *cualquier* flujo Samsung/MTK/QC/SPD; los Stops antiguos por chip quedan ocultos.
- **Gobernanza** — `dev`/`main` protegidas: CI `strict` `Rust+Python`, `1` revisión, `dismiss_stale`, `require_last_push_approval`, `linear_history`, `force_push:false`; `devin-ai-integration[bot]` eliminado del historial/tag `v1.2.1-beta.1` → `55c0da3`.

- **Plataforma:** Linux
- **Lenguaje:** Rust (núcleo) + Python 3.10+ / PyQt6 (UI)
- **Licencia:** MIT
- **Estado:** stable 1.2.0 — bienvenidos los contribuidores

Úsalo en dispositivos que posees o estás autorizado a reparar.