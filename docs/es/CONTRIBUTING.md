Language switcher: [English](../../CONTRIBUTING.md) · [Français](../fr/CONTRIBUTING.md) · **Español** · [Deutsch](../de/CONTRIBUTING.md) · [简体中文](../zh/CONTRIBUTING.md) · [Русский](../ru/CONTRIBUTING.md) · [Português](../pt/CONTRIBUTING.md) · [日本語](../ja/CONTRIBUTING.md) · [العربية](../ar/CONTRIBUTING.md) · [हिन्दी](../hi/CONTRIBUTING.md) · [Türkçe](../tr/CONTRIBUTING.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

# 🧑‍💻 Contribuir a FlashPilot

¡Gracias por pasar por aquí! Este proyecto se basa en protocolos de ingeniería
inversa y en conocimiento abierto — cada contribución lo hace más capaz, más
confiable y más cercano a las suites de Windows de pago. No necesitas ser experto
en flasheo para ayudar.

## Tabla de contenidos

- [Código de conducta](#código-de-conducta)
- [Cómo está organizado el proyecto](#cómo-está-organizado-el-proyecto)
- [Formas de contribuir](#formas-de-contribuir)
- [Primeros pasos](#primeros-pasos)
- [Recorrido por la arquitectura (10 minutos)](#recorrido-por-la-arquitectura-10-minutos)
- [Cómo añadir un nuevo flujo](#cómo-añadir-un-nuevo-flujo)
- [Añadir un nuevo protocolo USB / comando Rust](#añadir-un-nuevo-protocolo-usb--comando-rust)
- [Guías de GUI](#guías-de-gui)
- [Pruebas](#pruebas)
- [Lista de verificación de pull request](#lista-de-verificación-de-pull-request)
- [Roadmap e ideas](#roadmap-e-ideas)

---

## Código de conducta

Ver [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Sé respetuoso, asume buena intención
y mantén las discusiones técnicas y útiles. Este es un proyecto que pasó de
hobby a serio: damos la bienvenida a principiantes y veteranos por igual. No se
tolerará el acoso, el gatekeeping ni el commit de secretos/credenciales. Las
cargas útiles (payloads) de protocolo son bienvenidas cuando se documenta su
procedencia y licencia.

---

## Cómo está organizado el proyecto

Dos mitades trabajan juntas:

| Capa | Ubicación | Lenguaje | Rol |
|---|---|---|---|
| **Motor principal / de protocolo** | `src/` | Rust | USB crudo, todos los protocolos de bootloader (`flashpilot-bridge` CLI) |
| **Registro de flujos** | `src/flows.rs` | Rust | Filas con macro `flow!` → `FLOWS` / `JOBS` / `MODES` (fuente de verdad) |
| **Shim de flujo** | `python/core/core.py` | Python | Wrappers `_RustFlow` + fallback `JOBS`; delega a `bridge flow-run` |
| **Identidad del dispositivo** | `python/core/devices.py` | Python | Claves estables, lista de dispositivos, re-resolución del objetivo, alcance de hilo |
| **Superficie FRP** | `python/core/frp.py` | Python | Reexportación solo FRP (el nombre es la responsabilidad) |
| **Estudio GUI** | `python/gui/` | Python / PyQt6 | Workbench (`qt_app.py`), páginas (`devices.py`), tema, animaciones |

Python nunca habla con USB directamente. Llama al binario
`target/release/flashpilot-bridge` (el binario Rust), que devuelve JSON/texto. La
GUI solo escucha señales de los hilos worker — nunca toques widgets desde un hilo
en segundo plano.

---

## Formas de contribuir

¿Sin código? No hay problema:

- **Pruebas en hardware real** — informa sobre qué dispositivos/firmwares funciona un flujo.
- **Documentación** — mejora el README, este archivo y las descripciones de flujos.
- **Firmware / DA / archivos combo** — indicaciones hacia binarios legítimos y de libre disponibilidad.
- **Traducciones y temas** — la GUI es tematizable; nuevos packs de acento son victorias fáciles.
- **UI/UX** — mockups, pasadas de accesibilidad, diseño de atajos de teclado.
- **Reportes de bug** — usa la [plantilla de reporte de bug](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=bug&template=bug_report.yml): pasos, logs, salida de `flashpilot-bridge detect`, modelo del dispositivo + versión de firmware.
- **Código** — ver abajo.

> 💡 **¿Nuevo aquí?** Busca la etiqueta **`good first issue`** en el tracker de
> issues — tareas seleccionadas, amigables para principiantes, completamente
> acotadas y seguras de tomar.

---

## Primeros pasos

```bash
# 1. Compila el puente Rust
cargo build --release

# 2. (Recomendado) reglas udev USB
sudo bash root/setup-usb.sh

# 3. Crea el venv + ejecuta
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m python.main
```

La app abre una ventana PyQt6 nativa. Usa la página **Settings → Tools** para ver
si el puente está compilado y ADB detectado.

---

## Migrando desde un checkout anterior (léelo primero si vuelves)

Una nota sobre el churn, directamente: entre 1.2.0 y ahora renombramos el módulo
central, dividimos un god-file en módulos enfocados, renombramos cada job y
añadimos una docena de archivos. Eso rompe imports antiguos, referencias en
documentación antigua y cualquier script fuera del árbol que escribieras contra
`python.core.frp`. Perdón por eso — fue la única forma de matar el god-file,
corregir el lío de PIDs MTK y hacer posible el soporte multi-dispositivo sin
apilar hacks encima. Esta sección es la guía completa de adaptación; nada aquí
está deprecado gradualmente, todo cambió a la vez, así que recorre la tabla una
vez y estarás al día.

### Rutas renombradas

| Antes | Después | Qué cambiar |
|---|---|---|
| `python/core/frp.py` (god file: registro + todo flujo) | `python/core/core.py` | `from python.core import frp` → `from python.core import core`; `frp.FLOWS` → `core.FLOWS`, etc. |
| *(nada — FRP vivía dentro del god file)* | `python/core/frp.py` (nuevo, solo FRP) | Si solo necesitas flujos FRP, importa de aquí en lugar de `core`. |
| *(nada)* | `python/core/devices.py` (nuevo) | Identidad de dispositivo, `list_devices()`, `resolve_usb_target()`, `device_scope()`. |
| *(nada)* | `python/core/imei.py` (nuevo) | Flujos de reparación/cambio de IMEI MTK/SPD. |
| *(nada)* | `python/core/experimental.py` (nuevo) | Puertas EXPERIMENTAL + registro de auditoría. |
| *(nada)* | `python/core/{knox,qcn,emmc,pac,apple,health,compat,device_info,fastboot,integrity,safety,spd_adb}.py` (nuevo) | Lógica por dominio, antes inline en el god file o inexistente. |
| *(nada)* | `tests/test_devices.py` (nuevo) | Tests multi-dispositivo + cancel-scope. |
| *(nada)* | `CHANGELOG.md` (nuevo) | Cambios agrupados por release; revísalo primero. |

### El movimiento a Rust (arquitectura actual — la tabla de arriba es historia)

Tras la división anterior, los motores se movieron a Rust y el lado Python se
adelgazó. Verdad actual:

- **Los flujos viven en `src/flows.rs`** (registro + `flow-run <key> [target]
  [--code/--partition/--file/--dpc ...]`). `flow-list` es la fuente de verdad —
  verifica una clave de flujo ahí antes de citarla en documentación.
- **`python/core/core.py` es un shim fino** (~450 líneas): `_RustFlow` delega a
  `bridge flow-run`, el registro viene del puente con un fallback `JOBS`. Los 16
  módulos de motor por dominio (`knox`, `qcn`, `emmc`, `imei`, `apple`, `ofp`,
  `pac`, `health`, `flashing`, `spd_adb`, `integrity`, `fastboot`, `usb_watch`,
  `compat`, `updater`, `safety`) se eliminaron — no los menciones en docs nueva.
- **La GUI se queda en Python** (`python/gui/qt_app.py` + `devices.py`); consume
  el registro Rust vía `bridge.flow_list()`.
- Los antiguos archivos de test para flujos Python eliminados se borraron con ellos;
  la cobertura son las suites por área + cargo `flows::tests`.

### Cambios de API a los que debes adaptarte

- **Los resolutores toman `key=None`.** `find_samsung()`, `_download_mode_device()`,
  `_wait_for_adb()`, `_wait_mtk_brom_target()`, `_mtk_retry()`,
  `wait_clean_download_mode()`, `pit_contract()` todos aceptan una clave de
  dispositivo estable opcional (alcance ambiental de hilo por defecto — los
  call sites antiguos siguen funcionando, comportamiento first-match preservado
  cuando no se establece clave).
- **La cancelación es por dispositivo.** `request_cancel()` / `clear_cancel()` /
  `cancel_requested()` en `flow.py` y `bridge.py` aceptan `key=None`. El
  `request_cancel()` sin clave sigue difundiendo (STOP global); las comprobaciones
  sin clave consultan primero el alcance ambiental, luego el bus de difusión.
- **El run-guard es por dispositivo.** `_flow_start(label, destructive, key=None)` /
  `_flow_end(key=None)` / `_flow_busy_msg(key=None)` en `qt_app.py`; los antiguos
  globals `_FLOW_LOCK` / `_FLOW_LABEL` desaparecieron (reemplazados por dicts
  por clave + `_flows_running()`).
- **Los runners toman `device_key=None`.** `_run_ops_flow()` / `_run_job_flow()`
  muestran el selector de dispositivo cuando varios teléfonos coinciden, luego
  establecen `ctx["device_key"]` (+ `ctx["target"]` donde sea resoluble) y
  ejecutan dentro de `devices.device_scope()`.
- **Nuevo modo de transporte `"SPD"`** en `MODES` (VID `0x1782`); nuevos jobs
  `Knox / Warranty`, `QCN / Modem`, `IMEI Repair / Change`, `eMMC / UFS`.
- **Los nombres de job son verbo primero** (`Remove FRP`, no `FRP bypass`; ver
  README). Si tu rama aún referencia nombres antiguos, renómbralos a la tabla en
  “Recorrido por la arquitectura”.
- **Los PIDs MTK son convención mtkclient**: `0e8d:0003` = BROM,
  `0e8d:2000` = preloader. Varios comentarios/logs antiguos los tenían
  intercambiados; confía en `mtk.pid_stage()` / `boot_stage_for()` de Rust, no en
  strings antiguos.

### Si tienes un PR abierto anterior a la reestructura

1. Rebasea sobre el nuevo árbol; espera conflictos confinados a imports y a los
   bloques `JOBS`/`FLOWS`.
2. Ejecuta la checklist de abajo — `pytest` detectará enseguida las
   referencias a claves/nombres obsoletos (los tests del registro validan que cada
   método de `JOBS` resuelve).
3. Si tu PR tocó `flows/` (el experimento de paquete dividido que se eliminó):
   ese directorio ya no existe, trae tu cambio a `core.py` + el módulo de
   dominio.

---

## Recorrido por la arquitectura (10 minutos)

1. **`src/main.rs`** — una CLI con 80+ comandos. Cada rama `match` es un
   comando (`detect`, `mtk-flash`, `mtk-crash-brom`, `qcom-firehose`,
   `spd-format`, `odin-pit`, ...).
2. **`src/usb.rs`** — encuentra dispositivos por VID/PID y te da endpoints (más
   `port_numbers` estables para direccionamiento a prueba de re-enumeración).
3. **`src/odin.rs`** — modo download Samsung (el protocolo Odin 3 ingeniería
   inversa, derivado de Heimdall). Lee/escribe/flash PIT, flash de particiones
   (incl. el multiplexor de sesión persistente `odin-agent`).
4. **`src/mtk*.rs`** — MediaTek BROM (`0e8d:0003`) → preloader (`0e8d:2000`) →
   handshake del Download Agent, parseo de scatter, trabajo de partición GPT, claves
   SLA, exploits BROM, crash-to-BROM. ⚠️ La convención de PID es estilo
   mtkclient: `0003`=BROM, `2000`=preloader — no los intercambies.
5. **`src/qualcomm/`** — handshake Sahara (EDL) y sesiones Firehose.
6. **`src/spd.rs`** — Spreadtrum/UNISOC BSL: descarga de FDL, formateo, FRP,
   copia de seguridad, extract/pack de PAC.
7. **`src/flows.rs`** — el **corazón de la app**. Las filas `flow!(key, label, job, mode)`
   construyen el registro `FLOWS` / `JOBS` / `MODES` (~280 filas, 13 jobs, 9 modos
   incl. `SPD`). `python/core/core.py` solo lo refleja para búsqueda de GUI.
8. **`python/core/devices.py`** — identidad multi-dispositivo. Claves estables
   (`adb:<serial>` → `usb:<port-path>` → fallback volátil), `list_devices()`,
   `resolve_usb_target()` y el thread-local `device_scope()` que lleva el teléfono
   elegido dentro de los resolutores.
9. **`python/gui/qt_app.py`** — construye todas las secciones (Samsung / MTK / QC /
   SPD / Batería / Red / Ajustes) y los workbenches de sub-pestañas, más el
   selector por operación por dispositivo y el run-guard por dispositivo.

### Flujo de datos

```
clic en botón
  → _choose_device(job, mode)          # silencioso si 0-1 teléfonos coinciden, si no selector
  → _run_ops_flow(job, mode, method, name, device_key)
  → _flow_start(key) por dispositivo + device_scope(key) + ctx["device_key"]
  → core.flow_for(...) -> Flow (lista de Steps)
  → cada Step corre en un hilo worker, llamando bridge._run([...])
  → bridge lanza target/release/flashpilot-bridge ...
  → Rust hace I/O USB, imprime JSON/texto
  → Python parsea + emite señales _ui.line() (etiquetadas [device-key])
  → la GUI actualiza consola / estado / progreso de forma segura
```

---

## Cómo añadir un nuevo flujo

La funcionalidad más simple que puedes entregar. Abre `src/flows.rs` y añade una
fila:

```rust
flow!("my_method", "My method", "Remove FRP", "ADB"),
```

La clave es snake_case corta (sin prefijo `flow_`). Python la auto-descubre vía
`bridge.flow_list()` y el drill-down job/mode/método de la GUI la recoge
automáticamente; la ejecución corre a través de `flashpilot-bridge flow-run
my_method`.

Luego (solo si se necesita trabajo de protocolo de bajo nivel nuevo) añade el
comando del puente en `src/<concern>.rs` + `src/main.rs`. El cableado job/mode
ya está en la fila del flujo.

Eso es todo — el flujo aparece en el desplegable/sub-pestaña de la GUI
automáticamente y también es alcanzable desde la CLI. **Esta es el área de
mayor valor y más fácil de entrar.**

> Usa `log(...)` dentro de los pasos para salida de consola, `ctx` para el
> estado que quieres llevar entre pasos y `bridge._run(...)` para cualquier cosa
> que golpee al binario Rust. Mantén los pasos cooperativos con
> `cancel_requested()` donde convenga para que STOP funcione (la cancelación es
> por dispositivo — ver abajo).

### Reglas que todo flujo debe seguir

- **Nunca tomes "el" dispositivo.** Acepta `key=None` (alcance ambiental de
  hilo) en cualquier resolutor que añadas, y filtra por él — ver
  `devices.device_key()`, `devices.match_key()`, `devices.device_scope()`. La GUI
  establece el alcance por operación; los llamadores sin interfaz también pueden.
- **Los nombres de job son verbo primero** (`Remove FRP`, `Flash Firmware`,
  `Unlock Carrier`). **Las claves de flujo son snake_case corto** (`adb_frp`, no
  `flow_adb_frp`); el único alias histórico (`fastboot_read`) se eliminó — no
  añadas alias.
- **La convención de PIDs MTK es estilo mtkclient**: `0e8d:0003` = BROM
  (retenido), `0e8d:2000` = preloader. Rust, Python, etiquetas GUI y docs deben
  estar de acuerdo.
- **Las escrituras EXPERIMENTAL** (Knox/IMEI/QCN/eMMC) pasan por
  `experimental.check_gate_strict()` con un ack por ejecución — un ack
  almacenado nunca debe auto-aprobarse. Controlalas en la GUI vía
  `_EXPERIMENTAL_FLOW_MAP` + el patrón colapsable ámbar en la página del chip
  propietario (nunca en una página LAB global).
- **Los objetivos del puente son volátiles** (`vid:pid@bus:addr` cambia en
  re-enumeración). Re-resuelve desde la clave estable antes de abrir sesiones
  (`devices.resolve_usb_target()`); ancla odin4 con `-d /dev/bus/usb/BBB/AAA`.

---

## Añadir un nuevo protocolo USB / comando Rust

1. Añade tu módulo bajo `src/` (p. ej. `src/myproto.rs`).
2. Añade `mod myproto;` a `src/main.rs` y una nueva rama `match` + línea de uso.
3. Devuelve `Result<T>` vía `crate::error` y usa `serde_json` para salida
   estructurada.
4. Expónlo desde Python en `python/core/bridge.py` como wrapper alrededor de
   `_run([...])`.
5. Construye un `Flow` en `core.py` que lo llame (respeta las reglas de flujo
   anteriores).
6. Añade un test si puedes — las pruebas unitarias viven en `src/*.rs`
   (`#[test]`) y `tests/`.

**Higiene de protocolo:** cita tu fuente (foros, write-ups en clean-room, otros
proyectos OSS) en el docstring del módulo. No incluimos blobs propietarios — solo
la implementación del protocolo.

---

## Guías de GUI

- **Solo PyQt6.** Sin otros bindings Qt ni deps de UI extra (ver
  `requirements.txt`).
- Coincide con el lenguaje visual existente: `_btn_ghost()`, `_btn_primary()`,
  `_card_qss()`, `SectionTitle`, colores de tema `C[...]`, `FlowLayout` para
  rejillas de botones.
- **Tokens de tema, no acento crudo:** los rellenos pueden usar
  `C['accent'/'grad_a'/'grad_b']`, pero los anillos de foco, los bordes de
  pestañas seleccionadas y los checkboxes DEBEN usar los tokens neutros
  `C['focus_ring']` / `C['sel_border']` — de lo contrario los temas de acento
  rojo (Crimson, Sunset) filtran rojo en los estados de foco. Nunca hardcodes
  hex para chrome.
- **Regla de hilos:** el trabajo en segundo plano va en `threading.Thread`; las
  actualizaciones de GUI ocurren solo a través de las señales
  `self._ui.*` (`.line`, `.status`, `.toast`, `.ui`, `.progress`).
- **Animaciones:** `Motion.shake()` / `Motion.rubber()` son mutuamente excluyentes
  por widget (guardadas por `_anim_lock`) — nunca ejecutes ambas concurrentemente
  o los call sites deben serializar mediante `QTimer.singleShot`. Ninguna debe
  dejar `setFixedSize`, bordes restilizados o layouts deshabilitados detrás;
  `cleanup()` restaura todo.
- Mantén las filas de UI de larga vida desplazables — las páginas de chip
  envuelven el contenido en un `QScrollArea` para que nunca se aplasten en
  ventanas pequeñas.
- Las nuevas sub-pestañas reutilizan `SamsungSubTabs` + un `QStackedWidget` (ver
  `_build_chip_ops_section`).
- Los botones de acción son `NoFocus` (sin anillo de foco pegajoso); los pills de
  pestañas checkable conservan el estilo `checked` para el estado activo.

---

## Pruebas

```bash
cargo test                      # pruebas unitarias Rust (incl. mapping de etapas MTK, SLA, PIT)
.venv/bin/python -m pytest tests/   # suite Python (actualmente 173 passed, 4 skipped)
```

Diseño de la suite de tests:

- `tests/test_frp_flow.py` — ejecución de `Flow`/`Step` + cancelación cooperativa + run-guard por dispositivo.
- `tests/test_mtk.py` — lógica MediaTek (scatter, DA, helpers de boot-stage, espera/crash-retry de BROM).
- `tests/test_devices.py` — claves estables de dispositivo, filtrado de teléfonos, re-resolución de objetivo, cancelación con alcance.
- `tests/test_carrier_lock.py` — veredicto de bloqueo SIM + gating de parche MTK + discovery de DA.
- `tests/test_odin_safety.py` — verificación de tar.md5, puertas BL, negociación de flags de odin4.
- `tests/test_pit.py` — parseo de PIT de Samsung.
- `tests/test_bridge_io.py`, `tests/test_fus.py` — I/O del puente + descargador de firmware Samsung.

Si añades lógica Rust, añade módulos `#[test]` en el mismo archivo. Si añades
flujos, añade un pytest que ejecute el flujo con un contexto falso/offline cuando
sea posible. Los nuevos resolutores deben aceptar `key=None`; los nuevos tests
deberían cubrir el filtrado multi-dispositivo (ver `test_devices.py`) en lugar de
asumir un solo teléfono.

---

## Lista de verificación de pull request

- [ ] `cargo build --release` pasa.
- [ ] `cargo test` pasa (o nota por qué no es ejecutable).
- [ ] `.venv/bin/python -m pytest tests/` pasa.
- [ ] Nuevo flujo: cableado en `JOBS` (job + mode) para que sea alcanzable en la GUI.
- [ ] Nuevo resolutor: acepta `key=None` (alcance ambiental) y está cubierto por un test multi-dispositivo.
- [ ] Nuevo comando Rust: añadido al texto de uso de `main.rs` + wrapper en `bridge.py`.
- [ ] Cambios GUI: colores tematizados (¡tokens de foco neutros!), actualizaciones basadas en señales, layouts seguros ante scroll.
- [ ] No se añadieron secretos/binarios/datos identificativos de dispositivos al repositorio.
- [ ] README matriz de características actualizada si añadiste una capacidad.

Mantén los PRs enfocados. Lo ideal es una funcionalidad o fix por PR; referencia
el número de issue.

---

## Política de soporte de plataformas (léelo antes de hacer un port)

**Linux es la única plataforma soportada.** El desarrollo, las pruebas de
hardware y los releases se dirigen a Linux. Los issues de Windows/macOS se
cerrarán como no soportados — salvo que lleguen como código, como sigue.

**Por qué:** `odin4` es solo Linux; Windows USB necesita drivers por modo (Zadig
/ QDLoader / Samsung) que no pueden depurarse en remoto; macOS necesita firma/
notarización para una demanda insignificante. Ver la sección
“Platform support” del README para el razonamiento completo y la invitación
abierta a discutirlo.

**Cómo contribuir un port de todos modos (la forma aceptada):**

1. NO salpique verificaciones `sys.platform` por los flujos o la GUI.
2. Añade `python/core/platform.py` con funciones de backend —
   `open_file_manager()`, `detach_kernel_drivers(target)`,
   `usb_device_path(bus, addr)`, `needs_udev_setup()`,
   `kernel_module_loaded(name)` — Linux implementado, los demás lanzando
   `NotImplementedError` con un mensaje útil.
3. Migra los call sites solo-Linux (`xdg-open`, `rmmod cdc_acm`,
   `/dev/bus/usb`, `lsmod`, docs de udev) hacia él, un PR por grupo de call
   site.
4. Un PR de backend Windows/macOS debe incluir: la implementación del backend,
   actualizaciones de docs y evidencia de CI o prueba manual verificada por un
   mantenedor. El equipo central no posee hardware de test no-Linux — los PRs de
   port viven o mueren por la habilidad de su autor para demostrarlos.

**PySide6 vs PyQt6:** la migración a PySide6 (LGPL, compatible con MIT — PyQt6
es GPLv3) se desea pero está bloqueada por la cobertura de smoke-test de GUI. Si
la tomas: convierte `pyqtSignal→Signal`, `pyqtProperty→Property`,
`PyQt6.sip→shiboken6` mecánicamente, extiende los smoke tests sin pantalla de
ventana/selector/guardia en `tests/`, y mantén el comportamiento pixel-idéntico.
Discútelo primero en Discussions.

## Roadmap e ideas

Nos encantaría que los contribuidores lideraran cualquiera de estos:

- **Ports y empaquetado:** Flatpak / AppImage / AUR, matriz CI (distros Linux),
  flujo de release `pip`/`cargo`.
- **MediaTek:** más variantes de DA, casos límite de scatter, dumps de copia de
  seguridad eMMC/UFS, nuevas entradas en `CHIP_NAMES` (con fuente citada — nunca
  adivines códigos hex).
- **Qualcomm:** casos límite de rawprogram/patch XML, combos de fh-loader, más
  PIDs de chip.
- **Samsung:** payloads HID adicionales de modo download por SoC, pulido de UX de
  Odin multi-partición.
- **Multi-dispositivo:** pestañas de consola por dispositivo/progreso, granularidad
  de STOP por dispositivo (STOP actualmente se difunde), correlación de
  `port_numbers` para hubs exóticos.
- **Nuevas secciones:** FRP TEE/teclado, perfiles de carrier (de-bloating),
  utilidades solo-EDL.
- **Comunidad:** traducciones, una wiki de compatibilidad de dispositivos, un
  catálogo reproducible de archivos de firmware.
- **Seguridad:** modo dry-run, copia de seguridad pre-flasheo automática, docs
  de recuperación de brick.

---

## Contribuidores

Todos los que ayudan — código, docs, reportes de dispositivo o un combo probado
— se listan aquí y se celebran. Abre un PR añadiéndote a ti mismo (alfabético
por username, una línea de enlace):

```md
- [@your-github](https://github.com/your-github) — what you did
```

Los primeros contribuidores de este proyecto lo hicieron real. Sé el siguiente.

---

**¿Preguntas?** Abre una discussion/issue. Gracias por ayudar a avanzar el
software de flasheo libre y abierto en Linux. 🚀