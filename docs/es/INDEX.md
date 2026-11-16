# FlashPilot — índice

Language switcher: [English](../../INDEX.md) · [Français](../fr/INDEX.md) · **Español** · [Deutsch](../de/INDEX.md) · [简体中文](../zh/INDEX.md) · [Русский](../ru/INDEX.md) · [Português](../pt/INDEX.md) · [日本語](../ja/INDEX.md) · [العربية](../ar/INDEX.md) · [हिन्दी](../hi/INDEX.md) · [Türkçe](../tr/INDEX.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

El README tiene el marketing. Este archivo es el índice de ingeniería — cada carpeta, qué hace y dónde empezar.

## Ejecutarlo

```bash
# GUI
python main.py

# CLI (puente) — mismo protocolo, sin GUI
./target/release/flashpilot-bridge detect-all
./target/release/flashpilot-bridge spd-detect
```

## Estructura raíz (17 entradas)

| Entrada | Qué | Cuándo abrirla |
|---|---|---|
| `main.py` | Punto de entrada de la aplicación. Añade el repositorio a `sys.path` y llama a `python.gui.qt_app.main()`. | Para cambiar cómo arranca la app. |
| `pyproject.toml` | Metadatos del paquete Python (name=flashpilot, deps, backend de build). | Para añadir una dependencia Python o subir la versión. |
| `Cargo.toml` / `Cargo.lock` | Núcleo Rust (el binario `flashpilot-bridge`). | Para cambiar la CLI del puente o añadir un protocolo. |
| `python/` | Capa Python fina sobre el motor Rust: `python/core/` (shim + helpers de GUI) y `python/gui/` (PyQt6). Todos los flujos viven en `src/flows.rs`. | Plomería GUI y dispositivos. |
| `src/` | Fuentes Rust. Estructura espejo de `python/core/`. | Cuando añades un comando de puente o cambias un protocolo USB. |
| `tests/` | Suite pytest. ~149 tests, ~1s de ejecución. | Ejecuta con `.venv/bin/python -m pytest tests/ -q`. |
| `scripts/` | Herramientas shell autónomas. Hoy: `dump-connected.sh`, `validate_mtp_at.py`. | Para una operación por lotes sin GUI. |
| `docs/` | Recursos del README (capturas, logo). | Para el README. |
| `packaging/` | Script de build `.deb` + archivos de control. | Para enviar una release. |
| `root/` | Reglas udev (para que los teléfonos funcionen sin sudo). | Configuración puntual. |
| `operations/` | **Árboles de documentación por job** — ver sección "operations/" más abajo. | Para entender un job específico (FRP, MDM, bloqueo de pantalla, etc.). |
| `build/` | **Todos los artefactos de build/runtime ignorados por git** — ver sección "build/" más abajo. | Casi nunca los abres. |
| `.github/` | Workflows de CI, plantillas de issues. | Para cambiar la CI. |
| `LICENSE` `CODE_OF_CONDUCT.md` `CONTRIBUTING.md` `SECURITY.md` `DESCRIPTION.md` | Metadatos estándar del proyecto. | Al hacer una release. |

## Estructura `python/`

```
python/
├── main.py                 <- app entry (adds repo to sys.path, calls python.gui.qt_app.main)
├── gui/                    <- PyQt6 app
│   ├── qt_app.py           <- The main window + every device-mode UI (~12k LOC)
│   ├── devices.py          <- Data-driven "supported devices" drill-down (brand -> model -> action)
│   ├── theme.py            <- Design tokens (colors, button styles, version helpers)
│   ├── animations.py       <- Painted glyphs: connection scene, status orb, etc.
│   ├── nav.py              <- Top-level navigation rail + OEM chip bar
│   ├── toast.py            <- Toast notifications
│   └── supported_devices.json  <- The database of which model gets which action
└── core/                   <- Thin Python layer (no Qt deps; delegates to Rust bridge)
    ├── core.py             <- FLOWS/JOBS/MODES mirror (hardcoded cache + Rust flow_list())
    ├── bridge.py           <- Talks to the Rust `flashpilot-bridge` binary
    ├── flow.py             <- Flow/Step primitives + cancellation
    ├── jobs.py             <- FlashJob lifecycle (isolated job layer)
    ├── cancel.py           <- Cooperative cancellation registry
    ├── devices.py          <- Multi-device identity (stable keys, list, resolve, transport mapping)
    ├── frp.py              <- FRP-only re-export surface (name == responsibility)
    ├── mtk.py              <- MTK PIDs/stages/chips (0003=BROM, 2000=preloader)
    ├── mtp.py              <- Samsung MTP/AT (multi-sequence ADB enable)
    ├── pit.py pitstore.py  <- Samsung PIT parser + cache
    ├── adb.py device_info.py actions.py experimental.py fus.py
    └── (no flows/ dir)     <- flows live in src/flows.rs; Python only delegates via bridge.flow_run()
```

**Los flujos viven en Rust.** `python/core/core.py` es un shim fino: `_RustFlow` delega la ejecución a `bridge flow-run <key>`. El registro canónico es `src/flows.rs` (macro `flow!`, ~280 filas); Python lo refleja para la búsqueda de la GUI.

## Estructura `src/` (Rust)

```
src/
├── main.rs                 <- All CLI dispatch (eprintln! is the "log" channel) + flow-run
├── flows.rs                <- THE flow registry (flow! macro; FLOWS/JOBS/MODES)
├── usb/                    <- libusb context, descriptor parsing, filtering (mod.rs + filtering.rs)
├── devices.rs              <- merged USB+ADB device rows
├── sam_download.rs         <- Samsung Download/Odin session (odin-* commands)
├── sam_errors.rs sam_setup.rs sam_*.rs  <- Samsung helpers
├── mtk.rs mtk_da.rs        <- MediaTek BROM/DA flashing
├── mtk_exploit.rs          <- BROM exploits (bypass/kamakiri2/crash-to-BROM)
├── mtk_sla.rs mtk_sla_keys.rs <- Secure Lock Authentication
├── mtk_daloader.rs         <- DA container parsing
├── qualcomm/               <- EDL: Sahara + Firehose + GPT
├── spd.rs                  <- UNISOC BSL (BSL_CMD_*, BSL_REP_*, FDL1/FDL2)
├── pac.rs                  <- SPD PAC extract/pack
├── pit.rs                  <- Samsung PIT parser
├── mtp.rs at.rs adb.rs     <- MTP, AT command, ADB plumbing
├── fastboot.rs             <- native fastboot transport
├── moto_flash.rs           <- Motorola staged fastboot FRP
├── apple.rs                <- Apple usbmuxd/lockdown
├── bulk.rs hid.rs          <- bulk + HID helpers
├── fwtar.rs sparse.rs imgtools.rs <- firmware tar/sparse/boot-vbmeta
├── hostinfo.rs             <- host eMMC/UFS health
├── config.rs error.rs util.rs device.rs
└── (no odin.rs)            <- Odin logic lives in sam_download.rs
```

## `operations/` — árboles de documentación por job

Estas carpetas contienen **README por operación** que explican cómo funciona cada job, qué claves de flujo usa, qué dispositivos soporta y las advertencias conocidas. No es código — el árbol es markdown puro (una limpieza pasada eliminó los shims `.py` obsoletos que solían vivir aquí; nada importa `operations/`). El código vive en `src/flows.rs` (el registro `flow!`; `python/core/core.py` es un shim fino) y en los módulos por dominio (`knox.py`, `qcn.py`, `imei.py`, `emmc.py`, …). Los README de `operations/` están escritos para usuarios finales / investigadores de herramientas comerciales; el código es la fuente de verdad.

| Carpeta | Qué | Código real en |
|---|---|---|
| `operations/apple/` | iCloud, bloqueo de activación, MDM, eliminación de código/perdido | Flujos Rust (`src/flows.rs`: filas `apple_*`, CLI `flow-run`) |
| `operations/frp/` | Bypass FRP por motor + notas de investigación por dispositivo. **Empieza por `operations/frp/INDEX.md`**. | Flujos Rust (registro `src/flows.rs`, CLI `flow-run`); shim fino `python/core/core.py` |
| `operations/mdm/` | Desbloqueo MDM / device-owner + notas por marca | Flujos Rust (registro `src/flows.rs`, CLI `flow-run`) |
| `operations/screen_unlock/` | Eliminación de bloqueo de pantalla (ADB / recovery / download / completo) | Flujos Rust (registro `src/flows.rs`, CLI `flow-run`) |
| `operations/battery/` | Informe / reparación / prueba de carga de batería (por ADB) | Flujos Rust (registro `src/flows.rs`, CLI `flow-run`) |
| `operations/network/` | Estado SIM, DNS, reinicio de radio | Flujos Rust (registro `src/flows.rs`, CLI `flow-run`) |
| `operations/carrier_unlock/` | Bloqueo de operador (Apple, MTK) | Flujos Rust (registro `src/flows.rs`, CLI `flow-run`) |
| `operations/flashing/` | Guías de flasheo por vendedor (Samsung Odin, MTK DA, Qualcomm EDL, UNISOC SPD, PIT) | Flujos Rust (registro `src/flows.rs`, CLI `flow-run`) |
| `operations/usb/` | Notas de enumeración y detección USB | `src/usb/`, `src/devices.rs`, `python/core/devices.py` |

## `build/` — artefactos de build/runtime ignorados por git

| Subcarpeta | Contenido | Creado por |
|---|---|---|
| `build/target/` | Salida `cargo build` de Rust | `cargo build` |
| `build/dist/` | Paquetes `.deb` | `packaging/build-deb.sh` |
| `build/cache/` | Cachés TAR por dispositivo y dumps de ingeniería inversa | GUI / `scripts/dump-connected.sh` |
| `build/mdm_qr/` | Códigos QR de provisionamiento MDM generados | Flujo GUI MDM |
| `build/pit/` | Archivos `.pit` de tabla de particiones en caché | Flujo GUI PIT |

**Regla:** nunca hagas `git add` de nada de `build/`. Si necesitas borrar el estado, elimina el subdirectorio — se reconstruirá.

## Cómo añadir una funcionalidad (la hoja "¿qué archivo toco?")

| Quieres... | Toca |
|---|---|
| Añadir un nuevo dispositivo a la lista soportada | `python/gui/supported_devices.json` |
| Añadir una acción por vendedor a un dispositivo soportado | `src/flows.rs` (añade una línea `flow!(...)`); Python la auto-descubre vía `bridge.flow_list()` |
| Añadir un flujo ADB para un tema existente | Igual que arriba (Rust `src/flows.rs`) |
| Añadir un nuevo comando CLI de puente | `src/<tema>.rs` + `src/main.rs` (rama `<cmd>` en el match) |
| Añadir una nueva página de navegación principal | `python/gui/qt_app.py` (`_build_*_page` + `_section_index`) |
| Añadir un color / estilo de botón | `python/gui/theme.py` (`C` dict / `_btn_*()`) |
| Documentar las notas por job de un dispositivo nuevo | `operations/<job>/<marca>/<modelo>.md` |
| Añadir un test | `tests/test_<área>.py`, sigue el patrón `test_mtk.py` |

## Cómo funciona el lanzador de operaciones (léelo una vez)

La GUI nunca llama a un flujo directamente. El selector de dispositivo por operación (`FlashPilotWindow._choose_device`) resuelve primero una clave de dispositivo estable; luego `_run_ops_flow` / `_run_job_flow` llaman a `python.core.core.flow_for(job, mode, method)`, que devuelve un objeto `Flow()` (una lista de `Step()`), y luego se llama a `flow.run(ctx, log)` en un hilo worker dentro de `devices.device_scope(key)` (para que cada resolutor apunte al teléfono elegido). Cada flujo escribe en un callable `log(line)` que la GUI conecta a su consola. La cancelación tiene alcance por dispositivo (`flow.request_cancel(key)`; la difusión sin clave detiene todo), verificada al inicio de cada `_run`.

Para añadir un flujo: añade una línea `flow!("my_op", "My op", "Job Name", "MODE")` a `src/flows.rs`. Python la auto-descubre vía `bridge.flow_list()` y el drill-down job/mode/método de la GUI la recoge automáticamente. La CLI Rust `flow-run` la ejecuta; los resolutores deben aceptar un serial objetivo / `vid:pid@bus:addr` (ver `src/device.rs`).