# Registro de cambios

Language switcher: [English](../../CHANGELOG.md) · [Français](../fr/CHANGELOG.md) · **Español**

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## 1.2.2 (auto-actualizaciones, 10 idiomas, Rockchip + multi-dispositivo seguro para módem)

*Consolida las notas del ciclo de desarrollo 1.2.2 → 1.3.2 — todo lo enviado desde 1.2.1.*

### Auto-actualizaciones y Novedades (nuevo)

- Las actualizaciones se instalan solas: el `.deb` descargado se instala vía sudo en segundo plano, la app se reinicia y una ventana de una sola vez "qué se agregó o cambió" muestra el changelog de la nueva versión en el primer arranque (el aviso manual "Install Now" permanece cuando la auto-instalación está desactivada en Ajustes → Actualizaciones).

### UI en 10 idiomas + cambio de idioma en vivo (nuevo)

- Toda la UI llega en 10 idiomas adicionales (Français, Español, Deutsch, 简体中文, Русский, Português, 日本語, العربية, हिन्दी, Türkçe): ajustes, losetas de dispositivos, páginas y cadenas de consola.
- Cambiar el idioma de la UI es inmediato — sin reinicio; los diseños se ajustan a métricas reales de fuente para que las traducciones largas hagan wrap en vez de recortar controles.
- Catálogos de traducción JSON basados en claves con verificación de cobertura; la CI hace smoke-tests de los catálogos instalados.

### Rockchip + detección más inteligente (nuevo)

- Nueva página de marca Rockchip: familia RK28xx–RK35xx vía modo fastboot.
- La detección identifica modelo, marca y factor de forma — no solo el chip.
- Cada etapa de flasheo es capturada (paridad TFT): MediaTek BROM/preloader/DA en todo el conjunto de PID de etapa y VIDs OEM (incluyendo el preloader VCOM 0x2000/0x2001), la familia extendida de PIDs de descarga Qualcomm EDL, la unión de PIDs de descarga SPD, y los diagnósticos Qualcomm HS-USB nombrados como un modo propio.
- El badge de modo sigue al dispositivo SELECCIONADO y nombra el protocolo USB real (ADB/MTP/PTP/DIAG/storage/RNDIS) en lugar de OTHER: solo los PID de flasheo revindican la etiqueta de bajo nivel MediaTek, Qualcomm EDL conserva su chip de badge, y las caídas por subcadena 'MEDIATEK'/'download' están corregidas.

### FRP Motorola (nuevo)

- Cadena FRP fastboot CVE-2016-10277, aprovisionamiento QR de fake-login con DPC propio (TestDPC / Device Policy / Adobe), FRP fastboot escalonado con ciclos de flash + reinicio, y un ciclo ADB en bootmode de fábrica.

### Rutas de motor reales (nuevo)

- Rutas reales de flasheo, FRP y bloqueo MTK/QCOM/Unisoc/Samsung en el núcleo Rust.
- odin4 se fue: el motor Odin Rust nativo maneja todo el pipeline de tar, PIT y cada clase de problema conocida de odin4; usbmuxd/lockdown de Apple se movió a Rust; el núcleo es solo Rust (todos los repliegues de dispositivo/protocolo Python eliminados).

### ADB seguro para módem (corregido)

- Las rutas poll/monitor/display son zero-touch (`adb-devices --no-probe`): sin open/claim/handshake desde los bucles — los módems USB dejan de re-enumerarse cada ciclo (verificado en vivo: 114 ciclos de poll silenciosos en un módem MSM8916).
- Las peleas de claim delegan en escalera: nativo → transporte de servidor Rust (serie explícita) → binario host → kill de rescue (último recurso), de modo que las ops ADB tienen éxito mientras el servidor del sistema retiene la interfaz.
- Corrección de fusión USB-ADB (las cadenas de fila se analizan, así que las filas sí llevan estado ADB), rescate del retenedor ocupado + reintento transitorio + estado ocupado honesto, guarda babble/overflow, comando de aislamiento del test de claim, valores CNXN de adb modernos, y los rincones QCOM/MTK muestran la superposición ADB como las ramas hermanas.

### Fiabilidad multi-dispositivo (corregido)

- Pick con settle-retry: cada ejecutor de herramienta reintenta una vez tras 2,5 s cuando un escaneo pierde transitoriamente un dispositivo en re-enumeración, en lugar de rechazar con "no device" mientras la GUI lo muestra conectado.
- El AUTH de ADB mantiene SHA-256 en juego a través de las rondas de token (rondas impares SHA-256, pares SHA-1), de modo que una firma perdida en la ronda 1 ya no se mura en un falso "not authorized"; `_wait_for_adb` tolera fallos de escaneo transitorios.
- Vinculación de identidad objetivo: un dispositivo reemplazado que ocupa un bus:addr reutilizado se rechaza (verificación serie zero-touch) — el transporte nunca sigue a otro teléfono.
- Cambio de lista de dispositivos: la reconstrucción de la barra de conexión reintenta cuando el segundo escaneo pierde un dispositivo, cambiar de dispositivo ya no cae al primer teléfono, y las herramientas ADB se repliegan a la fila daemon ADB cuando el pick USB falla ("muestra conectado pero las acciones dicen no hay adb").
- Clasificación + selector de dispositivos: los dispositivos no coincidentes reportan USB en lugar de una etiqueta MTP incorrecta, y un pick USB perdido ofrece el selector de fila daemon ("Run on this device" / "Cancel") en lugar de rechazar.

### Resultados honestos y pulido de GUI (corregido)

- Los flujos FRP requieren flags verificados y un estado de salida de shell real; una salida de puente no cero levanta un fallo con la cola del log — no más toasts falsos de "completed".
- GUI: chips de job por fila, memoria de ventana, tope de toasts, navegación por teclado, STOP consciente del dispositivo (un job cancela ese dispositivo), kg_unlock movido a un hilo worker (las cadenas de 30 segundos ya no congelan la ventana), splash sigue el build real, las páginas diferidas siguen siendo reintentables, los toasts despejan la barra superior.

### Seguridad y robustez

- Salidas privadas por defecto, nombres temporales a prueba de symlinks, comprobaciones de symlink.
- Verificación del firmware tras escritura por defecto + puerta de modelo + correcciones numéricas.
- FRP: el certificado de firma DPC se lee de forma nativa y el checksum de aprovisionamiento está corregido.
- Arnés de pruebas de hardware HIL: regresiones multi-dispositivo / reemplazo de dispositivo / tormenta USB en hardware real; tests de backoff del monitor ADB hechos deterministas.
- Página de aterrizaje pública (`website/`) con la matriz de capacidades y la consola de protocolos.

## 1.2.1 (versión estable)

### Soporte multi-dispositivo (nuevo)

- Conecta varios teléfonos: la barra de conexión lista cada uno (modelo · serie · transportes); haz clic en una fila para inspeccionarlo.
- Cada operación pregunta a qué teléfono se aplica cuando varios coinciden (silencioso con 0–1 coincidencia). Las líneas de consola llevan una etiqueta `[device-key]`.
- Una operación por dispositivo: teléfonos distintos pueden flashear en paralelo; el mismo teléfono sigue serializándose. STOP global se emite a todos los corredores.
- Identidad estable (`python/core/devices.py`): `adb:<serial>` → `usb:<port-path>` → repliegue volátil. Los objetivos se re-resuelven antes de abrir sesiones, por lo que la re-enumeración USB ya no huérfana un flasheo (`usb device Fail`).
- Lista de dispositivos solo teléfonos: hubs, HID, webcams y lectores de tarjetas se filtran.
- Nuevo modo de transporte `SPD` + flujos de detección Qualcomm/SPD de solo lectura.

### EXPERIMENTAL por chip (nuevo)

- Samsung `Knox / Warranty`, Qualcomm `QCN / Modem`, por chip `IMEI Repair / Change`, `eMMC / UFS` — colapsables ámbar en la página del chip propietario (sin página LAB global). Casilla de propiedad en cada ejecución; el cambio de IMEI requiere además escribir `I UNDERSTAND`. Auditado; los acks persistidos nunca pasan automáticamente (`check_gate_strict`).

### MTK BROM (corregido + mejorado)

- **Corrección del mapeo PID/etapa** a la convención mtkclient (`0e8d:0003`=BROM, `0e8d:2000`=preloader) en Rust, Python, etiquetas GUI, logs y docs.
- Nuevo comando de puente `mtk_crash_brom` + flujo `MTK crash preloader into BROM` (registrado bajo MTK BROM).
- `_wait_mtk_brom_target()` prefiere el BROM estable sostenido sobre la ventana de preloader; el descubrimiento de DA rechaza binarios truncados (<1 KB).

### Odin / flasheo (endurecido)

- `_prepare_download_session()`: desacople del controlador del kernel + reintento de handshake 3× a través de la re-enumeración; todos los PID Odin aceptados; caché PIT calentada pre-flasheo.
- odin4 fijado con `-d /dev/bus/usb/BBB/AAA` + un reintento automático único en pérdida USB; trailer `.tar.md5` anclado al fin de archivo (streaming, sin lectura completa en RAM).
- Logs de flasheo nativo inteligente por partición MB/s + ETA.

### Endurecimiento de robustez (guiado por revisión)

- Sahara: comando HELLO/version/mode/tamaño-de-paquete validado al analizar (antes: cualquier blob ≥32 bytes era de confianza); la autocomprobación de formato de transferencia ahora hace round-trip de structs en lugar de descartar bytes; fallos de cierre registrados; el desacople se ejecuta antes del claim; el handshake reporta resultados de transfer/close/reset en JSON en lugar de descartarlos (reset explícito y visible).
- Auth ADB: backoff exponencial acotado entre rondas de token; pausa de keygen única anunciada en lugar de parecer colgado.
- MTK: el tamaño de paquete configurado realmente llega a la sesión DA (antes se calculaba y descartaba; sesiones codificadas en 64 K), acotado a 512 B–1 MB.
- Copias de seguridad de seguridad: los fallos imprimen una pancarta ineludible con tiempo transcurrido y una pista STOP (contrato sin cambios: nunca bloquea la operación).
- Puertas experimentales: flujos iCloud + Pixel migrados a acks estrictos por ejecución; los tokens de ack GUI ahora se cuentan por funcionalidad con expiración (sin sangrado entre funcionalidades, sin acks perdidos, sin autorizaciones caducadas).

### Correcciones de GUI

- Bordes rojos de la barra superior + encogimiento de botones trazados a animaciones shake/rubber concurrentes y anillos de foco teñidos de acento: animaciones serializadas con `_anim_lock` + limpieza completa; nuevos tokens de tema neutros `focus_ring`/`sel_border` (los acentos rojos ya no pueden filtrarse al foco).
- `os.system()` → `subprocess` para reconstrucción del puente / apertura de directorio de logs.
- Stub SPD duplicado "Enable ADB", gating experimental erróneo de `fastboot_unlock`, ruta muerta FUS→slot AP y emisión `finished` faltante corregidos. Se retiró la superficie experimental muerta LAB/Knox/QCN/PAC.

### Reestructuración

- `python/core/frp.py` (archivo dios) → `python/core/core.py` (registro + flujos); `frp.py` ahora solo FRP. Se eliminó la división muerta `python/core/flows/`.
- Nombres de job verbo primero (`Remove FRP`, `Flash Firmware`, …); una clave canónica snake_case por flujo; casing del nombre de visualización normalizado.

### Docs

- Capturas nuevas (`docs/samsung.png`, `mtk.png`, `spd.png`), README reescrito (destacados/matriz/layout), arquitectura CONTRIBUTING + reglas de flujos, este changelog.

### boot.img + AVB (un solo motor nativo)

- Nuevo motor de cirugía de imagen en el puente Rust (`src/imgtools.rs`): análisis del encabezado boot Android, escaneo cpio newc, parcheado de propiedades (pad-in-place o crecimiento estilo magiskboot con reescritura de encabezado), gzip determinista (mtime=0, nivel 9), flags AVB vbmeta. CLI `boot-info` / `boot-patch-adb` / `vbmeta-patch`.
- El repack Python `spd_adb` + `core._patch_vbmeta_flags` delegan con repliegue local (firmas y contratos de retorno sin cambios).
- El trabajo de equivalencia corrigió dos bugs reales: el splice de crecimiento discordaba con la alineación del lector en 2 bytes (corrompiendo cada entrada posterior — ambas implementaciones), y el re-parcheado crecía `\n` en cada ejecución (ambos lados ahora idempotentes). Los bytes gzip se excluyen a propósito de la paridad (las implementaciones zlib difieren); el contenido descomprimido, tamaños y campos coinciden.
- 6 pruebas unitarias Rust + 9 pruebas entre implementaciones.

### PAC (un solo motor nativo + acciones GUI cableadas)

- Nuevo motor SPD PAC en el puente Rust (`src/pac.rs`): parse/extract/pack con la disposición YGDP, constructores de encabezado/slot compartidos ahora también usados por el escritor `spd-readback` (salida byte-identical; sus nombres históricos duplicados de slot quedan en cuarentena, no propagados). CLI `pac-parse` / `pac-extract` / `pac-pack`.
- Python `pac.*` delega con repliegue local; nuevos `flow_pac_extract` / `flow_pac_pack` (solo archivo, entradas env estilo ofp) registrados en FLOWS y mapeados en el despachador GUI — los botones PAC antes muertos ahora funcionan.
- Las pruebas de equivalencia detectaron y corrigieron un bug real: el packer local descartaba silenciosamente la cadena producto (escritura slice-copy); además guardas de desbordamiento u32 con mensajes idénticos en ambos motores.
- 5 pruebas unitarias Rust + 7 pruebas entre implementaciones (roundtrips ambas direcciones, paridad sanitize incl. colisión de dir, mapeo de errores).

### PIT (un solo motor nativo)

- Nuevo motor Samsung PIT en el puente Rust (`src/pit.rs`): parse (disposición 28/132), cadenas de encabezado/modelo, normalización de nombres, find, escaneo de solapamiento, validación forense + veredictos de salud — mensajes, resúmenes y veredictos byte-identical a la implementación Python en dumps reales y casos límite (incluyendo paridad Python-`repr` para nombres basura).
- CLI `pit-parse` / `pit-health` / `pit-find` / `pit-overlaps` / `pit-model`; las rutas Python `pit.*` de bytes crudos delegan con repliegue local cuando el binario falta (contratos preservados: ValueError/None/never-raise). Las rutas de objeto en memoria y los auxiliares de visualización siguen locales y rápidos; las reglas compartidas fijadas por 11 pruebas de equivalencia entre implementaciones.
- 8 pruebas unitarias Rust (vectores de disposición, tabla de normalización, clasificación de solapamiento meta, formas de resumen/human-size).

### ADB (transporte nativo, sin platform-tools)

- Nuevo cliente ADB nativo en el puente Rust (`src/adb.rs`): transporte USB (255/66/1) con desacople del controlador del kernel, handshake CNXN, AUTH RSA-SHA256/SHA-1 (reutiliza `~/.android/adbkey`, generado si falta), servicios `shell:` y `sync:` (STAT/RECV/SEND).
- `adb-devices` mantiene su contrato de línea `adb devices -l` desde un escaneo nativo (`device` / `unauthorized` / `no permissions`); `adb-shell` toma un serial (`-` = primer autorizado), más los nuevos `adb-pull` / `adb-push` fijados por serial.
- Python: `bridge.adb_shell()` resuelve explícito > alcance ambiental > primer serial autorizado (ADB multi-dispositivo ahora fijado al objetivo); `adb.py` delega al puente; pull/push de copia/restauración EFS pasan por el puente en lugar de llamadas system `adb` sin fijar. `has_adb()` ahora significa "puente construido".
- 6 pruebas Rust (framing, banner, sign/verify PKCS#1, roundtrip DER, blob de clave pública bit-identical vs clave de adb del sistema) + 9 pruebas Python.

### Fastboot (transporte nativo + Motorola universal)

- Nuevo transporte USB fastboot nativo en el puente Rust (`src/fastboot.rs`): `fastboot-devices` (JSON) + `fastboot-cmd <vid:pid@bus:addr> <ms> <cmd…>` para la fase de comando (getvar/oem/erase/reboot) con desacople del controlador del kernel. El fallo del lado del dispositivo se renderiza como `FAILED (remote: …)` con código de salida 0, coincidiendo con la forma de transcript del binario del sistema (incluyendo valores `getvar` solitarios que viajan en el paquete OKAY en bootloaders Moto MBM).
- Los auxiliares compartidos de Python (`_fastboot_run`, `_wait_fastboot`, `_fastboot_getvar`) son nativo-primero con repliegue al binario del sistema; los comandos de fase DATA (flash/boot/…) usan siempre el binario del sistema, y el listado lado-host `devices` se sirve desde la detección nativa. Todo el tráfico fastboot ahora está fijado al objetivo (`vid:pid@bus:addr`), cerrando el peligro de teléfono-incorrecto sin `-s`.
- Nuevos flujos Motorola a escala de marca (`moto_frp_adb`, `moto_frp_fastboot`, `moto_oem_unlock_token`): reset de aprovisionamiento ADB, flujo oficial de token de desbloqueo con lectura de estado de bloqueo + resets de sesión, lector de token solo lectura. Mostrados bajo Motorola → All Motorola / Lenovo (universal) y cada modelo Moto; URL del portal de desbloqueo corregida (el antiguo `motorola.com/unlockbootloader` está muerto).
- `python/core/fastboot.py` (Pixel) y `usb_watch.py` (scraping lsusb) movidos al puente; 7 nuevas pruebas `tests/test_fastboot_native.py`.