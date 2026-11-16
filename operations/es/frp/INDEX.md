Language switcher: [English](../../frp/INDEX.md) · [Français](../../fr/frp/INDEX.md) · **Español** · [Deutsch](../../de/frp/INDEX.md) · [简体中文](../../zh/frp/INDEX.md) · [Русский](../../ru/frp/INDEX.md) · [Português](../../pt/frp/INDEX.md) · [日本語](../../ja/frp/INDEX.md) · [العربية](../../ar/frp/INDEX.md) · [हिन्दी](../../hi/frp/INDEX.md) · [Türkçe](../../tr/frp/INDEX.md)

> English is the canonical source. This page is a translation; help wanted — see [`../../../docs/TRANSLATION.md`](../../../docs/TRANSLATION.md).

# operations/frp/ — Protección de restablecimiento de fábrica (Factory Reset Protection, solo Android)

> Los dispositivos Apple no tienen FRP (Apple usa bloqueo de activación / iCloud en su
> lugar) — ver `operations/apple/`.

Este directorio contiene **árboles de documentación por motor** para el bypass de FRP.
El código real viven en `src/flows.rs` (Rust). Cuando tengas una receta real para un
dispositivo (chip, par de FDL, offsets de partición, etc.) dejas una nota corta de
investigación en `devices/<brand>/<model>.md`. El README en la raíz de este archivo
asigna cada flujo FRP del codebase a dónde vive y qué necesita.

## Mapa de motores

| Motor | Cuándo usarlo | Código | CLI del puente |
|---|---|---|---|
| **Genérico (ADB)** | Primer intento en cualquier teléfono con depuración USB activada | Flujos Rust (`adb_frp`, `frp_*` filas en `src/flows.rs`) | `flow-run adb_frp` / `adb shell ...` vía `bridge.adb_shell` |
| **MTK BROM** | MediaTek (Helio / Dimensity / MT6765) — apaga → mantén Vol-/+ → enchufa USB | Flujos Rust (`mtk_*` filas en `src/flows.rs`) | `flow-run mtk_brom_info` (CLI: `mtk-detect`, `mtk-da-upload`, `mtk-frp`, `mtk-bypass`) |
| **MTK DA** | MTK BROM que sobrevivió a la subida de DA (chips con bloqueo de estado) | Flujos Rust (`mtk_brom_backup`, `mtk_auth_flash`) | `flow-run mtk_brom_backup` |
| **Qualcomm EDL** | Descarga de emergencia 9008 (Snapdragon) | Flujos Rust (`edl_*`, `qcom_*` filas) | `flow-run edl_frp` (CLI: `qcom-*`) |
| **Samsung Exynos** | A14 (Exynos 850/1330), A15/A16 — el modo Download Odin es solo flasheo, NO para FRP | Filas Rust `frp_*` (bypass de cuenta Samsung) | (principalmente en el dispositivo, sin puente) |
| **Samsung MTK (A05/A06)** | A05/A06 con Helio G85 — usa MTK BROM (arriba) | Flujos Rust (`mtk_brom_info`, `mtk_brom_backup`) | `flow-run mtk_brom_backup` |
| **UNISOC/SPD** | 1782:4d00 FDL1+FDL2 (SC9863A, T606/UMS9230) | Flujos Rust (`spd_*` filas) + `src/spd.rs` | `flow-run spd_detect_info` (CLI: `spd-detect`, `spd-frp`, `spd-format`, `spd-magic-pack`) |
| **HiSilicon Kirin** | 12d1 — aún sin flujo abierto (no ingeniería inversa) | (ninguno aún) | (ninguno) |

(Los antiguos módulos `python/core/flows/*.py` de motor nunca se publicaron;
`mtk-brom-backup` es la fila de flujo `mtk_brom_backup`. Verifica cualquier clave
con `flow-list`.)

## Mapa clave de flujo → función

Todos los flujos que las acciones FRP de la GUI pueden llamar. Las claves son filas del
registro Rust (`src/flows.rs`, `flow-list` para verificar); la GUI las enruta por
(job, mode) y el puente las ejecuta vía `flow-run <key> [target]`.

| Clave de flujo | Motor | Qué hace |
|---|---|---|
| `adb_frp` | ADB genérico | `settings put secure frp 0` + desactivar asistentes de configuración + limpiar datos de GMS |
| `frp_browser` | ADB genérico | Abrir `chrome://settings/` en el dispositivo vía intent |
| `frp_emergency` | ADB genérico | Abrir Ajustes vía el dialer de llamada de emergencia (en el dispositivo) |
| `frp_settings` | ADB genérico | Abrir Ajustes vía la ruta del panel de notificaciones (en el dispositivo) |
| `frp_fake_login` (+`_testdpc`, `+_adp`) | ADB genérico | Provisionamiento QR con un DPC de propietario de dispositivo, luego limpieza de FRP |
| `at_info` | Samsung MTP/AT | Leer modo + devconinfo vía canal AT (Samsung pre-Android 8) |
| `at_method` | Samsung MTP/AT | AT+DEBUGLVC para habilitar ADB por el puerto diag |
| `download_frp` | Modo Download Samsung | Eliminación de FRP con firmware CSC/Combination (contrato de seguridad PIT) |
| `odin_enable_adb` | Modo Download Samsung | Habilitar ADB desde el modo download vía tarball Odin |
| `mtk_combo_flash` | MTK Download | Flasheo de firmware Combination (PIT + DA) |
| `mtk_recovery_reset` | MTK Download | Restablecimiento de fábrica en modo recovery |
| `mtk_brom_info` | MTK BROM | Leer id del chip / handshake (necesario antes de cualquier flasheo BROM) |
| `mtk_brom_backup` | MTK BROM | Volcar particiones vía BROM DA |
| `edl_frp` | Qualcomm EDL | Sahara + Firehose erase (05c6:9008) |
| `qcom_detect_info` | Qualcomm EDL | Detectar + info (solo lectura) |
| `frp_qr_provision` | ADB genérico | Provisionamiento QR (ruta TestDPC) |

(Retirado: los antiguos nombres de clave con prefijo `flow_*` y
`python/core/flows/*.py` nunca se publicaron — las claves no tienen prefijo `flow_`.)

## Cómo entra aquí una nueva receta por modelo

1. **Ejecuta un volcado real del dispositivo** (ver `scripts/dump-connected.sh` para la
   ruta ADB, o `flashpilot-bridge spd-format` para la ruta BROM en Unisoc). El volcado
   va a `build/cache/dumps/<model>_<codename>/`.

2. **A partir del volcado, identifica** el motor + chip + el nombre de la partición
   FRP (casi siempre `frp`, `frp_a`, o `userdata` en Android 11+).

3. **Añade la entrada del dispositivo** a `python/gui/supported_devices.json` bajo la
   marca correcta, con `actions: ["frp", "info", "backup", "flash"]` y
   `status: "researched"`. (El flujo por motor existente lo recogerá
   automáticamente — no se necesita un flujo nuevo a menos que falte el motor en sí.)

4. **Suelta una nota corta de investigación** en `operations/frp/devices/<brand>/<model>.md`
   con el chip, el motor, la partición, la huella de build y un
   one-liner confirmando la receta (p. ej., "mmcblk0p4 = frp, borrado instantáneo
   por BROM DA, sin combo"). Ver
   `operations/frp/devices/nokia/nokia_g20.md` para el formato.

5. **Si el motor aún no tiene un flujo** para este chipset, registra el flujo en
   `src/flows.rs` (una fila `flow!(...)`) y añade el despacho CLI en
   `src/<engine>.rs` + `src/main.rs`.

## Por qué los archivos por chip han desaparecido

Anteriores refactorings dividieron el god `frp.py` en archivos por chip bajo
`operations/frp/chips/` y archivos por motor bajo
`operations/frp/{mtk,qualcomm,unisoc,samsung}_frp/`. Una revisión antigua de este
INDEX afirmó stubs de documentación muertos y un despacho `python/core/flows/brom.py`
— ese módulo nunca se publicó. El despacho real por chip es el registro de flujos Rust
(`src/flows.rs`: filas `mtk_*`/`qcom_*`/`spd_*`, `flow-list` para verificar); este
INDEX.md es el mapa para que un nuevo desarrollador sepa dónde vive realmente el código
específico del motor.

## Por qué los shims Python por motor han desaparecido

`operations/frp/mtk_frp/mtk_frp.py` (y sus 4 hermanos) importaban funciones de
`python.core.flows.brom` y las reexportaban bajo un **segundo** dict `FLOWS = {}` que
la GUI nunca lee. Colisionaban con el `FLOWS` canónico en
`python/core/flows/__init__.py` y habrían enmascarado los verdaderos si la GUI llegara a
leerlos. Se reemplazaron con un README en cada carpeta de motor que apunta a los
verdaderos módulos Python.