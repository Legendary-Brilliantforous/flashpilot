# 🔧 FlashPilot

Language switcher: [English](../README.md) · [Français](../fr/README.md) · **Español** · [Deutsch](../de/README.md) · [简体中文](../zh/README.md) · [Русский](../ru/README.md) · [Português](../pt/README.md) · [日本語](../ja/README.md) · [العربية](../ar/README.md) · [हिन्दी](../hi/README.md) · [Türkçe](../tr/README.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

> **Un banco de trabajo de código abierto para el flasheo y reparación de firmware Samsung en Linux — una alternativa a Odin / Heimdall para flashear teléfonos Galaxy (modo Download/Odin), dispositivos MediaTek (BROM/DA), Qualcomm (EDL) y Spreadtrum/UNISOC.**

**Palabras clave de búsqueda:** Samsung flashing tool · Odin alternative · Android firmware flashing Linux · Heimdall GUI · Galaxy phone repair · MTK BROM flash · Qualcomm EDL · FRP unlock · UNISOC flashing · device firmware tool · mobile repair · Android bootloader · USB flashing · Linux flashing suite · proprietary tool alternative

[![Rust](https://img.shields.io/badge/Rust-1.70+-orange?logo=rust&logoColor=white)](https://www.rust-lang.org)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-41cd52)](https://www.riverbankcomputing.com/software/pyqt/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![CI](https://github.com/Legendary-Brilliantforous/flashpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/Legendary-Brilliantforous/flashpilot/actions)
[![Good First Issues](https://img.shields.io/github/issues/Legendary-Brilliantforous/flashpilot/good%20first%20issue)](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
[![Contributors](https://img.shields.io/github/contributors/Legendary-Brilliantforous/flashpilot)](https://github.com/Legendary-Brilliantforous/flashpilot/graphs/contributors)

**¿Qué es esto?** El equivalente nativo para Linux de las suites de flasheo de Windows de pago — una sola herramienta unificada que habla directamente con el bootloader de los dispositivos **Samsung, MediaTek, Qualcomm y Spreadtrum/UNISOC**. Protocolos de ingeniería inversa + rendimiento nativo en Rust + una hermosa GUI PyQt6 = la alternativa open source a Odin, Heimdall y las costosas herramientas comerciales.

---

## ✨ Por qué importa este proyecto

El mundo de la reparación Android funciona con herramientas comerciales cerradas y solo para Windows. Sus protocolos son de ingeniería inversa por una pequeña comunidad de aficionados — y la mayor parte de ese conocimiento está bloqueado dentro de suites de pago o disperso por los foros en forma incompleta.

**Este proyecto es nuestra respuesta.** Convierte esos protocolos de ingeniería inversa en una base de código limpia, auditable, con licencia MIT, que cualquiera puede leer, ejecutar, ampliar — y distribuir como su propia suite de flasheo.

| Herramienta comercial | Solo Windows, código cerrado | Este proyecto |
|---|---|---|
| Odin / Smart Switch | Windows, solo GUI | Protocolo Odin open source (Rust, nativo) + herramientas PIT |
| Herramientas de flasheo MTK | Windows, DA cerrado | Flasheo y copia de seguridad MTK BROM/DA (scatter + GPT) |
| Herramientas EDL Qualcomm | Windows | Implementación del protocolo Sahara + Firehose |
| Herramientas SPD/UNISOC | Windows | Implementación BSL en clean-room |
| Herramientas FRP / bloqueo | De pago, mercado gris | Flujos transparentes ADB + modo download, desbloqueo MDM |

---

## 🚀 Características destacadas — 1.2.1 Stable (0 advertencias)

- **9 modos de transporte** — ADB, MTP, modo Download Samsung, BROM Samsung, MTK, MTK BROM, Fastboot, Qualcomm EDL, SPD.
- **13 categorías de jobs** — Flash Firmware, Remove FRP, Remove Screen Lock, Remove MDM, Unlock Carrier, Read Device Info, Detect Devices, Reboot, Repair Settings, más por chip en EXPERIMENTAL: Knox / Warranty (Samsung), QCN / Modem (Qualcomm), IMEI Repair / Change (MTK/SPD/Qualcomm), eMMC / UFS.
- **Multi-dispositivo** — conecta varios teléfonos: la barra de conexión lista cada uno, cada operación pregunta a qué teléfono se aplica (o se ejecuta silenciosamente cuando solo uno coincide), y diferentes teléfonos pueden ejecutar operaciones en paralelo (una op por dispositivo, STOP se difunde a todos).
- **Núcleo Rust (`flashpilot-bridge`, ~9.3k LOC) — 0 advertencias de `cargo check`** — USB crudo con *libusb incluido* (sin dependencias del sistema), implementaciones reales de protocolo (+ 18 rutas muertas cableadas, trim ltcg -80KB).
  - **Samsung**: protocolo de sesión Odin de ingeniería inversa (basado en Heimdall), payloads HID en modo download, lectura/escritura/flasheo de PIT — contexto `AT` conservado, troceado `EndpointConfig`.
  - **MediaTek**: handshake BROM / preloader / DA, scatter & GPT, exploits BROM, claves SLA — porcentaje real del `ProgressReporter`.
  - **Qualcomm**: `ProtocolError` Sahara + `QcomDeviceInfo` Firehose cableados mediante tiempos límite `Duration`.
  - **SPD/UNISOC**: BSL en clean-room — todos los `BSL_CMD/REP`, `iface`, `flush/read_flash/chip_uid/power_off` cableados.
  - Además **MTP**, comandos **AT** y toda la plomería **ADB**.
- **Una GUI de nivel estudio** — ventana frameless translucent con tarjetas de radio, 10 temas de acento, escena animada de cable/estado, consola en vivo.
  - **Iconos de marca y fondos de botón distintos** — iconos de marca nítidos (Samsung Ⓢ, Apple 🍎 rojo, Motorola Ⓜ, LG Ⓛ, etc.) y colores de fondo adaptados en cada botón OEM de la barra superior de chips.
  - **Vistas horizontales para Motorola y Apple** — los paneles de acciones de modelos usan por defecto disposiciones limpias en pestañas horizontales.
  - **Micro-interacciones y glassmorphism** — animaciones de fundido de entrada de página de 160 ms fluidas, tipografía monoespaciada para insignias de metadatos (`Consolas`, `Monaco`) y bordes de tarjetas glassmórficas mejorados.
  - **Grandes diálogos centrados (620px, arrastrables, ✕)** — puerta beta + stable `UPDATE/AHEAD/PATCH` + confirmaciones de flasheo/FRP, colores de chip `MTK ámbar` `QCOM rojo` `SPD violeta` `SAMSUNG azul`, texto de alto contraste.
  - **Colapsables EXPERIMENTAL por chip** — Knox (Samsung), QCN/IMEI (Qualcomm), IMEI (MTK/SPD): banner ámbar, casilla de propiedad en cada ejecución, `I UNDERSTAND` de confirmación por tipeo para cambio de IMEI, con registro de auditoría.
  - **⏹ STOP** en la barra de título detiene todas las operaciones en curso; los bloqueos por dispositivo permiten que otros teléfonos sigan trabajando.

---

## 📸 Capturas de pantalla

| Operaciones Samsung | Banco de trabajo MediaTek | Reparación de batería | Descarga SPD |
|---|---|---|---|
| ![Samsung](docs/samsung.png) | ![MediaTek](docs/mtk.png) | ![Batería](docs/battery.png) | ![SPD](docs/spd.png) |

---

## 🧩 Matriz de características

| Capacidad | Samsung | MediaTek | Qualcomm | SPD/UNISOC | Cualquier ADB |
|---|---|---|---|---|---|
| Detectar / info | ✅ | ✅ (+ crash preloader→BROM) | ✅ (Sahara) | ✅ | ✅ |
| Flashear firmware | ✅ (Odin, Rust nativo) | ✅ (scatter + GPT) | ✅ (Firehose) | ✅ (FDL/regiones) | — |
| Copia de seguridad de particiones | ✅ (EFS) | ✅ | ✅ | ✅ | — |
| Bypass FRP | ✅ (ADB + download) | ✅ | ✅ (EDL) | ✅ | ✅ |
| Eliminar bloqueo de pantalla | ✅ | ✅ | ✅ (EDL) | — | ✅ |
| Desbloquear MDM | ✅ (ADB, QR, recovery) | — | — | — | — |
| Knox garantía/bypass (EXPERIMENTAL) | ✅ | — | — | — | — |
| Copia/restauración QCN + reparación/cambio IMEI (EXPERIMENTAL) | — | ✅ (NVRAM) | ✅ (NV 550/682) | ✅ (BSL NV) | — |
| Herramientas de partición | ✅ (PIT) | ✅ (GPT) | ✅ | ✅ (extract/pack PAC) | — |
| Exploits de bajo nivel | ✅ (HID/BROM) | ✅ (exploit BROM, SLA) | ✅ (Sahara) | ✅ (BSL) | — |
| Reparación de batería / red | — | — | — | — | ✅ |

> 💡 Las secciones **Batería** y **Red** funcionan en *cualquier* dispositivo Android con depuración USB activada — no se necesita hardware del vendedor.

---

## 🖥️ La GUI

Una ventana frameless, translucent, con tarjetas de radio, con un **banner de conexión** en vivo (escena ordenador → cable → teléfono con un pulso de datos animado) sobre un **rail de navegación** a la izquierda y un **panel de consola/log** a la derecha.

- **Barra de conexión** — lista en vivo de dispositivos (una fila por teléfono: modelo · serie · transportes); haz clic en una fila para inspeccionarla. Los botones de operación preguntan qué teléfono cuando varios coinciden.
- **Samsung** — sub-pestañas del hub Samsung: `ODIN FLASH · UNLOCK · ADVANCED FLASH · INFO & TOOLS`, además de slots de firmware (AP/BL/CP/CSC/USERDATA), utilidades Odin y un colapsable `KNOX — EXPERIMENTAL`.
- **MediaTek / Qualcomm / SPD** — bancos de trabajo dedicados con herramientas nativas de bajo nivel (scatter/DA + crash-to-BROM, programmer/XML + QCN/IMEI, binarios FDL + direcciones base + IMEI), cada uno con su propio colapsable `— EXPERIMENTAL`.
- **Batería** — salud del fuel-gauge en %, temp/voltaje/corriente, principales consumidores; reparación en un clic.
- **Red** — estado SIM, flags de datos/Wi-Fi, modo DNS; reinicio de radio y re-registro.
- **Ajustes** — intervalo de auto-escaneo, rutas por defecto, borrado automático de la consola, 10 temas de acento, animaciones (toggles shake/rubber/cable/bubble), resplandor de ventana, estado del motor y `cargo build` integrado.

**Atajos:** `F5` reescanear · `Ctrl+Enter` ejecutar · `Ctrl+L` limpiar consola · `Ctrl+S` guardar log · `Ctrl+F` buscar.

---

## 📦 Inicio rápido

**Requisitos:** toolchain de Rust, Python 3.10+, un escritorio Linux. Eso es todo — libusb viene incluido.

```bash
# 1. Compila el puente Rust (la primera compilación compila libusb desde la fuente)
cargo build --release

# 2. (Recomendado) instala las reglas udev USB para que los teléfonos no necesiten sudo
sudo bash root/setup-usb.sh

# 3. Entorno Python
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. Lanzar
.venv/bin/python -m python.main        # o: python3 main.py
```

El flasheo en modo download de Samsung es nativo (protocolo Rust Odin) — no se obtiene, distribuye ni requiere ningún binario propietario odin4. El firmware combo de Samsung debe obtenerse de las páginas de soporte oficiales de Samsung o de archivos de firmware de confianza.

---

## 🖥️ Soporte de plataformas — queremos tu opinión

**Linux es la plataforma soportada.** FlashPilot es deliberadamente *la respuesta nativa para Linux a las suites de flasheo solo para Windows* — el desarrollo, las pruebas y las releases se dirigen a Linux, y eso no cambiará.

**Windows / macOS no están soportados hoy**, por razones prácticas:

- Windows USB es un infierno de drivers por modo de teléfono (Zadig/WinUSB, QDLoader, drivers de Samsung peleándose entre sí); la mayoría de los reportes "teléfono no detectado" serían indebuggeables en remoto.
- macOS añade sobrecarga de firma/notarización para una demanda casi nula en tiendas de reparación.
- La pila *es* portable (Rust + rusb, Python, Qt), así que es una decisión de mantenimiento, no una imposibilidad técnica.

**Pero esta es una pregunta abierta, no un veredicto.** Si quieres soporte para Windows/macOS — o quieres defender Linux-only para siempre — dínoslo:

- 💬 Abre una **[Discussion](https://github.com/Legendary-Brilliantforous/flashpilot/discussions)** con tu caso de uso (¿tienda de reparación? ¿laboratorio? ¿qué SO? ¿qué teléfonos?).
- 🔧 El código habla más fuerte: el plan es una abstracción `python/core/platform.py` (`open_file_manager()`, `detach_kernel_drivers()`, `usb_device_path()`, `needs_udev_setup()`) con Linux como único backend, para que los ports sean PRs aditivos en lugar de forks. Los PRs en esa dirección son bienvenidos ya.
- 🎨 Relacionado: los contribuidores han propuesto **PySide6** (LGPL, compatible con la licencia de este proyecto MIT) frente a PyQt6 (GPLv3). Da tu opinión en la misma Discussion — la migración es mecánica pero necesita primero cobertura de smoke-test de GUI.

Ninguna decisión se tomará sin las voces de los contribuidores. Ven y sé uno de ellos.

### CLI / puente

```bash
./target/release/flashpilot-bridge detect          # all USB + Samsung filter (JSON)
./target/release/flashpilot-bridge fastboot-devices  # USB devices with a fastboot interface (JSON)
./target/release/flashpilot-bridge fastboot-cmd 22b8:2e80@2:16 20000 getvar securestate  # one raw fastboot command
./target/release/flashpilot-bridge mtk-detect      # MediaTek BROM (0e8d:0003) / preloader (0e8d:2000) / DA
./target/release/flashpilot-bridge mtk-crash-brom <bus:addr>  # crash preloader into held BROM
./target/release/flashpilot-bridge qcom-detect     # Qualcomm EDL
./target/release/flashpilot-bridge spd-detect      # Spreadtrum/UNISOC (VID 0x1782)
./target/release/flashpilot-bridge odin-pit 04e8:xxxx@bus:addr  # read PIT
./target/release/flashpilot-bridge at-send <t> ATI # AT over CDC ACM
./target/release/flashpilot-bridge adb-devices     # adb devices -l as JSON
```

---

## 📁 Estructura del repositorio

```
flashpilot/
├── src/                      # Rust bridge (~13k LOC) — ALL flows live here
│   ├── main.rs               #   command-line entry (80+ commands) + flow-run dispatch
│   ├── flows.rs              #   THE registry: FLOWS / JOBS / MODES (flow! macro, ~280 rows)
│   ├── usb/                  #   USB enumeration / interfaces / filtering (mod.rs + filtering.rs)
│   ├── devices.rs            #   merged USB+ADB device rows
│   ├── sam_download.rs       #   Samsung Download/Odin protocol (odin-* commands)
│   ├── mtk.rs mtk_da.rs      #   MediaTek BROM/DA flashing
│   ├── mtk_exploit.rs        #   BROM exploits (bypass/kamakiri2/crash-to-BROM)
│   ├── mtk_sla.rs            #   MediaTek SLA key handling
│   ├── qualcomm/             #   Sahara + Firehose + GPT (EDL)
│   ├── spd.rs                #   Spreadtrum/UNISOC BSL protocol (+ PAC)
│   ├── pac.rs                #   SPD PAC extract/pack
│   ├── pit.rs                #   Samsung PIT parser
│   ├── mtp.rs at.rs adb.rs   #   MTP, AT command, ADB plumbing
│   ├── fastboot.rs           #   native fastboot transport
│   ├── moto_flash.rs         #   Motorola staged fastboot FRP
│   ├── apple.rs              #   Apple usbmuxd/lockdown
│   ├── hid.rs bulk.rs        #   HID + bulk helpers
│   ├── fwtar.rs sparse.rs    #   firmware tar + sparse handling
│   ├── imgtools.rs           #   boot/vbmeta surgery
│   ├── hostinfo.rs           #   host eMMC/UFS health
│   ├── sam_*.rs              #   Samsung helpers (errors/setup)
│   └── config.rs error.rs util.rs
├── main.py                   # app entry (venv-safe launcher → python.gui.qt_app)
├── python/
│   ├── core/
│   │   ├── core.py           #   thin shim: mirrors Rust FLOWS/JOBS/MODES via bridge.flow_list()
│   │   ├── frp.py            #   FRP-only re-export surface (name == responsibility)
│   │   ├── devices.py        #   multi-device identity: stable keys, list, resolve, transport mapping
│   │   ├── bridge.py         #   talks to the Rust binary (+ per-key cancel)
│   │   ├── flow.py           #   Flow/Step primitives + cancellation
│   │   ├── jobs.py           #   FlashJob lifecycle (isolated job layer)
│   │   ├── cancel.py         #   cooperative cancellation registry
│   │   ├── mtk.py            #   MTK PIDs/stages/chips (0003=BROM, 2000=preloader)
│   │   ├── mtp.py            #   Samsung MTP/AT (multi-sequence ADB enable)
│   │   ├── pit.py pitstore.py  # Samsung PIT parser + cache
│   │   ├── adb.py            #   ADB helpers
│   │   ├── device_info.py    #   live device identity
│   │   ├── actions.py        #   action helpers
│   │   ├── experimental.py   #   per-run ack gates + audit log
│   │   ├── fus.py            #   Samsung FUS helpers
│   │   └── (no flows/ dir)   #   flows live in src/flows.rs; Python only delegates
│   └── gui/
│       ├── qt_app.py         #   the PyQt6 studio (~12k LOC)
│       ├── devices.py        #   brand→model→action drill-down pages
│       ├── nav.py            #   nav rail + OEM chip bar
│       ├── theme.py          #   tokens (accent vs focus_ring/sel_border) + QSS
│       ├── animations.py     #   Motion (shake/rubber serialized, no stuck state)
│       ├── toast.py          #   toast notifications
│       └── supported_devices.json  #   brand/model/chip research table
├── operations/               # per-operation docs + research (frp/mdm/flashing/…)
├── docs/                     # screenshots (fresh) + logo
├── root/                     # udev rules + setup-usb.sh
├── scripts/                  # dump-connected.sh, validate_mtp_at.py
├── INDEX.md CHANGELOG.md     # engineering index + release changelog
└── tests/                    # pytest suite (flow, MTK, PIT, odin safety, devices…)
```

---

## 🧑‍💻 Contribuir

**Este proyecto solo mejora contigo.** Buscamos mantenedores, hackers de protocolo, diseñadores de GUI, redactores y testers.

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — todo lo que necesitas para empezar.
- **Empieza con la etiqueta [`good first issue`](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)** — tareas seleccionadas y accesibles a principiantes.
- Usa las plantillas de **[informe de bug](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=bug&template=bug_report.yml)** / **[solicitud de funcionalidad](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=enhancement&template=feature_request.yml)**.
- **Tareas para principiantes** — cada fila de flujo en `src/flows.rs` es una oportunidad: añade una línea `flow!(...)`, ajusta una secuencia de comandos, conecta un nuevo combo de dispositivo. Python lo auto-descubre mediante `bridge.flow_list()`.
- **El framework de flujos (`src/flows.rs`) es muy simple** — un método nuevo cabe en una línea:

```rust
flow!("my_method", "My method", "Read Device Info", "ADB"),
```

Aparece automáticamente en la GUI. Ese es todo el ciclo de contribución: **escribe una fila de flujo, entrega una funcionalidad.**
- **Regla multi-dispositivo** — nunca tomes "el" dispositivo; acepta `key=None` (alcance ambiental) y filtra por él. Ver `python/core/devices.py` y `CONTRIBUTING.md`.
- **Reglas de nombres** — los jobs son verbo primero (`Remove FRP`, no `FRP bypass`); las claves de flujo son snake_case corto (sin prefijo `flow_` en `FLOWS`); los PIDs MTK son `0003`=BROM / `2000`=preloader (convención mtkclient — no los intercambies).

**Ideas en las que nos encantaría ayuda:**
- Nuevos modelos de dispositivos / combos de firmware en las tablas de flujos.
- Variantes de DA MediaTek, rarezas de scatter/GPT.
- Casos límite de rawprogram & patch XML de Qualcomm.
- Métodos FRP / eliminación de bloqueo adicionales por versión de Android.
- Empaquetado (Flatpak, AppImage, AUR, `cargo` + `pip`), CI, tests unitarios.
- Más protocolos ODIN, herramientas eMMC/UFS, utilidades adyacentes a iCloud y EDL.
- Traducciones, temas y accesibilidad.

---

## 🛡️ Seguridad y legalidad

Esta herramienta habla directamente con los bootloaders y puede borrar datos o brickear un dispositivo si se usa mal.

- Úsala solo en **dispositivos que posees o estás autorizado a reparar** (tiendas de reparación que atienden teléfonos de clientes con consentimiento).
- Lee siempre las advertencias en pantalla y **haz copia de seguridad de las particiones** antes de flashear.
- Bypasear FRP/MDM en un dispositivo que no te pertenece puede ser **ilegal en tu jurisdicción** — eres responsable de cómo uses este software.
- FlashPilot incluye los payloads de protocolo que necesitan las operaciones (payloads MTK DA/BROM, programadores firehose de Qualcomm, FDL1/FDL2 de Unisoc, bootloaders de Samsung), igual que las suites comerciales de flasheo. Las imágenes de firmware para un teléfono concreto siempre provienen del usuario o del vendedor.

---

## 📄 Licencia

MIT — ver [LICENSE](LICENSE). Las constantes del protocolo Odin provienen del proyecto Heimdall (MIT), y la referencia BSL de SPD viene de documentación de protocolo en clean-room (spd_cmd.h / docs Opus-Spreadtrum).

---

**Dale una estrella ⭐ a este repo, abre una issue, envía un PR — y construyamos juntos la mejor suite de flasheo open source en Linux.**