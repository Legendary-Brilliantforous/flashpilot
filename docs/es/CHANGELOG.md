# Registro de cambios

Language switcher: [English](../../CHANGELOG.md) · [Français](../fr/CHANGELOG.md) · **Español**

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## 1.3.2 (el badge nombra el protocolo USB)

- El badge de modo ya no muestra OTHER para un dispositivo conectado: 'MEDIATEK' no contiene la subcadena 'MTK', por lo que una etiqueta genérica de modo MTK ('MEDIATEK MODE (VID 0x0E8D PID 0x2008)') caía hasta OTHER.
- Un teléfono MediaTek/Tecno en arranque normal con un PID no coincidente (0e8d:2008, interfaz still-image/MTP, sin fila ADB) ya no se revindica como MediaTek de bajo nivel: solo los PID de flasheo (BROM/preloader/DA) revindican la etiqueta de bajo nivel; todo lo demás cae a nombres de protocolo basados en interfaz (ADB/MTP/PTP/DIAG/storage/RNDIS) en TODAS las listas de dispositivos — antes solo los dispositivos Samsung eran escaneados por protocolo.
- Transportes Rust: un PID no coincidente que aun expone una interfaz still-image (clase 6) reporta MTP en lugar de USB; el hardware sin interfaz MTP conserva la etiqueta USB honesta.
- La etiqueta de conexión muestra 'MediaTek device (normal boot)' en lugar de 'MediaTek low-level' para PID no de flasheo.
- Qualcomm EDL conserva su propio chip de badge: 'EDL MODE (Qualcomm Emergency Download)' contiene la subcadena 'download' y antes caía al chip DOWNLOAD.
- Los diagnósticos HS-USB de Qualcomm (05c6:9006, p. ej. Moto en Diag) se nombran 'QUALCOMM DIAG MODE (HS-USB Diagnostics 9006)' en lugar de fusionarse en la etiqueta genérica 'QUALCOMM DEVICE'.

## 1.3.1 (corrección de ModeBadge)

- El badge de modo del dispositivo (barra superior, junto a Stop) sigue al dispositivo SELECCIONADO y ya no lee MTP para configuraciones Qualcomm-normal (la subcadena 'normal' caía en el chip MTP).

## 1.3.0 (clasificación de dispositivo + selector)

- Los dispositivos no coincidentes (compuestos vendor-specific/diag) reportan 'USB' en lugar de la etiqueta incorrecta 'MTP'.
- Cuando el pick USB falla en un flap, las herramientas ADB muestran el selector de fila daemon en lugar de rechazar: elige qué dispositivo apunta la op.

## 1.2.9 (identidad del dispositivo mostrado)

- Cambiar de dispositivo ya no cae al primer teléfono: el refresco de 3 s, el resolvedor de identidad en vivo y todos los repliegues se basan en el dispositivo mostrado; la ruta de ausencia mantiene las losetas estáticas de la fila.

## 1.2.8 (corrección de cambio de lista de dispositivos)

- La reconstrucción de la barra de conexión reintenta cuando su segundo escaneo pierde un dispositivo que el monitor acababa de ver (ventana de re-enumeración): ambos dispositivos se muestran y el cambio funciona en enlaces inestables.

## 1.2.7 (vinculación de identidad objetivo)

- Un dispositivo reemplazado que ocupa un bus:addr reutilizado se rechaza (verificación serie zero-touch en el objetivo; la apertura coincide con vid/pid/bus/addr, no con el número de serie). Cierra el escenario de reemplazo de dispositivo: el transporte nunca se sigue hacia otro dispositivo.

## 1.2.6 (repliegue de fila daemon)

- Las herramientas ADB se repliegan a la fila daemon ADB cuando el pick por escaneo USB falla en un bus inestable (el daemon es basado en TCP y sigue siendo autoritativo para la presencia). Corrige "muestra conectado pero las acciones dicen no hay adb".

## 1.2.5 (superposición ADB en rincón MTK)

- La rama de rincón mtk_devs ahora muestra la superposición ADB como las ramas hermanas: un dispositivo Tecno/MTK con ADB autorizado nombra el transporte en la esquina superior derecha (antes mostraba solo 'MediaTek low-level' mientras ADB Status mostraba conectado).

## 1.2.4 (corrección de AUTH ADB)

- Alternancia de hash AUTH corregida: SHA-256 permanece en juego a través de las rondas de token (rondas impares SHA-256, pares SHA-1). Antes una firma perdida en la ronda 1 en un enlace ruidoso re-tokenizaba en un muro de SHA-1 -> falso 'no autorizado' mientras el dispositivo estaba autorizado.
- `_wait_for_adb` tolera fallos de escaneo transitorios durante la espera.

## 1.2.3 (resiliencia del pick)

- Pick de dispositivo con settle-retry: cada ejecutor de herramienta reintenta una vez tras 2,5 s cuando un escaneo pierde transitoriamente un dispositivo en re-enumeración, en lugar de rechazar con "no device" mientras la GUI lo muestra conectado. Los selectores cancelados por el usuario nunca se reintentan.

## 1.2.2 (ADB seguro para modem + correcciones de visualización)

### Transporte ADB (corregido)

- Las rutas poll/monitor/display son zero-touch (`adb-devices --no-probe`, `adb_presence`): sin open/claim/handshake desde los bucles. Corrige módems USB que se re-enumeran cada ciclo (verificado en vivo: 114 ciclos de poll silenciosos en un módem MSM8916 tras tormentas ~1 Hz).
- Escalera de delegación en peleas de claim: nativo -> transporte de servidor Rust (`adb-shell-server`, serie explícita solo) -> binario host -> kill de rescue (último recurso). Las ops ADB ahora tienen éxito con el servidor del sistema reteniendo la interfaz en lugar de desalojarla.
- Corrección de fusión USB-ADB: las cadenas de fila se analizan (la deserialización de struct había dado silenciosamente cero entradas ADB, por lo que las filas nunca llevaban estado ADB).
- El rincón QCOM ahora muestra la superposición ADB como las ramas hermanas.

### Robustez (corregido)

- Reintento settle único en rechazos transitorios de puerta (ventanas de re-enumeración) con mensajes precisos; `rescue=False` + pin de serie en todos los shells de diagnóstico/herramientas; detección de fallo Firehose; panics de entrada CLI; clamps de asignación; guardas de recorrido tar; numéricos XML estrictos.

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