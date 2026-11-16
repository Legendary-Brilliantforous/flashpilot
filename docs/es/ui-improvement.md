# Plan intensivo de mejora de la UI de FlashPilot

Language switcher: [English](../../ui-improvement.md) · [Français](../fr/ui-improvement.md) · **Español** · [Deutsch](../de/ui-improvement.md) · [简体中文](../zh/ui-improvement.md) · [Русский](../ru/ui-improvement.md) · [Português](../pt/ui-improvement.md) · [日本語](../ja/ui-improvement.md) · [العربية](../ar/ui-improvement.md) · [हिन्दी](../hi/ui-improvement.md) · [Türkçe](../tr/ui-improvement.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## Objetivo
Transformar la GUI PyQt6 de un monolito funcional en un taller pulido, mantenible y de alto rendimiento, preservando todos los flujos respaldados por Rust y el comportamiento multi-dispositivo.

## Estado actual
- `python/gui/qt_app.py` (~15k LOC) es una ventana monolítica única.
- El sistema de temas (`theme.py`) está centralizado, pero el QSS es grande y está duplicado en algunos lugares.
- La barra de conexión, el rail de navegación, las páginas por chip, la consola y los ajustes están en un solo archivo.
- Ya existe una identidad visual fuerte (tarjetas glass, 10 acentos, escena de cable).

## Principios
1. Sin lógica de protocolo en Python; la UI solo renderiza y llama al puente.
2. Mantener Rust como fuente de verdad para flujos/jobs/modos.
3. Mejorar la capacidad de respuesta: mover el trabajo pesado fuera del hilo de UI, reducir el churn de widgets.
4. Accesibilidad: navegación por teclado, anillos de foco, etiquetas para lectores de pantalla.
5. Mantenibilidad: dividir `qt_app.py` en módulos por funcionalidad.

## Fase 0 — Shell de ventana, logo, splash (nuevo)
- Reemplazar el logo actual por una marca vectorial/SVG profesional (variantes monocromo + acento, 16/32/64/128/256px + .ico/.icns).
- Pantalla de splash: marca animada, etapas de progreso (init del puente Rust, escaneo de dispositivos, carga del tema), versión, sin parpadeo; fundido entrada/salida 200ms.
- Renderizado de ventana: ventana sin marco translúcida compatible con el alpha del compositor, esquinas redondeadas, sombra, escalado consciente de DPI, memoria de colocación multi-monitor.
- Flujo: activar `Qt AA_UseHighDpiPixmaps`, definir formato de superficie (OpenGL/RGBA), animaciones amigables con vsync, reducir el desbarajuste de layout; objetivo 60fps en interacciones.
- Marca: logo consistente en la barra de título, barra de tareas, diálogo "Acerca de", instalador.
- Columnas del shell redimensionables: el límite **panel de dispositivos | página** es un divisor horizontal arrastrable (por defecto 232px, arrastrable 228–420px, memorizado en `layout/device_panel_width`). La página mantiene su ancho natural y vive en un área de desplazamiento sin marco, para que al comprimirla se desplace lateralmente en lugar de reflow de sus pestañas/rejilla; el ancho del panel se conserva entre redimensionamientos de ventana hasta que el usuario lo arrastre. _Decisión (usuario): antes era un `setFixedWidth(232)` estricto._

## Fase 1 — División arquitectónica (sin cambio visual)
- Extraer los constructores de página en `python/gui/pages/`:
  - `samsung.py`, `mtk.py`, `qc.py`, `spd.py`, `battery.py`, `network.py`, `settings.py`, `quick.py`.
- Extraer widgets compartidos en `python/gui/widgets/`: `metric_card.py`, `collapsible.py`, `console.py`, `device_picker.py`.
- Mantener `qt_app.py` como shell: chrome de ventana, nav, enrutamiento, señales.
- Criterio de aceptación: la app arranca, todas las pestañas renderizan, las pruebas pasan.

## Fase 2 — Rendimiento
- Virtualizar la lista de dispositivos y el log de consola (`QAbstractListModel` + `QListView`) para evitar creación O(n) de widgets.
- Agrupar actualizaciones de log (flush cada 50ms o 100 líneas).
- Cachear el QSS renderizado por tema; regenerar solo al cambiar el acento.
- Carga perezosa de páginas pesadas (construcción en la primera visita).
- Criterio de aceptación: 10k líneas de log sin bloqueo de UI; desplazamiento a 60fps.

## Fase 3 — Pulido visual
- Tokens de diseño: escala de espaciado (4/8/12/16/24), escala de radio, elevación.
- Elevación/sombra de tarjeta consistente; estados hover/focus.
- Movimiento: fundido de página 120ms, escala de pulsación de botón, deslizamiento de toast.
- Sistema de iconos: reemplazar emoji con iconos SVG (glifos de marca).
- Estados vacíos y esqueletos para la detección de dispositivos.
- Modo de alto contraste + interruptor de movimiento reducido.

## Fase 4 — Flujos UX
- Diálogo unificado de selección de dispositivo con búsqueda/filtro y badges de transporte.
- Progreso de operación: lista de pasos con marcas de verificación, ETA, cancelación por dispositivo.
- Presentación de errores: tarjetas accionables con “reintentar / abrir docs / copiar log”.
- Ajustes: buscables, agrupados, con restablecer a valores por defecto.
- Consola: filtrar por nivel/dispositivo, exportar, buscar.

## Fase 5 — Accesibilidad & i18n
- Orden completo de Tab, foco visible, etiquetas tipo ARIA.
- Atajos de teclado documentados en la app.
- Extracción de cadenas para traducciones (sin cadenas de usuario codificadas en los widgets).

## Fase 6 — Pruebas
- Pruebas smoke de GUI con pytest-qt (headless).
- Capturas de regresión visual para cada página/tema.
- Benchmarks de rendimiento para el renderizado de log/dispositivo.

## Entregables
- `python/gui/pages/*`, `python/gui/widgets/*`
- Sistema de tokens de `theme.py` actualizado
- `tests/test_gui_smoke.py`
- Actualización de docs en README/INDEX.

## Riesgos
- Monolito de 15k LOC; se requiere extracción incremental.
- Reglas de threading de PyQt; mantener toda manipulación de widgets en el hilo principal.
- Preservar el alcance multi-dispositivo y la semántica de cancelación.

## Primera tarea sugerida
Extraer `_build_console` y `_build_conn_bar` en `widgets/console.py` y `widgets/connection_bar.py` con una API basada en señales; sin cambio de comportamiento.

## Fase 7 — Renderizado de flujos y jobs (nuevo)
### Problemas observados
- `_add_job_flows` aplana todos los modos en una lista de botones por job; el modo solo está en la infobulle, lo que confunde.
- Botones duplicados entre páginas (Quick, secciones de ops chip, pestañas Unlock) con gating inconsistente.
- Los botones experimentales/destructivos solo se distinguen por color/borde; sin leyenda.
- Sin búsqueda/filtro, ni usados recientemente, ni favoritos.
- Los libellés largos de flujo desbordan/se repliegan de forma impredecible en FlowLayout.
- Sin agrupación visual por riesgo (solo lectura vs flash vs experimental).

### Modelo de renderizado propuesto
- Navegación en tres niveles **Job → Mode → Método**:
  - Izquierda: lista de jobs (verbo primero, iconos).
  - Centro: pestañas de modo (ADB, MTP, …) con contadores.
  - Derecha: tarjetas de método (nombre, badge de riesgo, badge experimental, infobulle).
- Fuente única de verdad: `core.modes_for` / `core.methods_for`; sin listas duplicadas en las páginas.
- Desduplicar globalmente por (job, mode, key); las páginas chip filtran por modos soportados en lugar de relanzar `_add_job_flows`.
- Estados de tarjeta de método: activada/desactivada por puertas de capacidad, en curso (spinner), último resultado (ok/fail).

### Qué mover
- Mover la construcción de botones de `_add_job_flows` a `widgets/flow_button.py` + `widgets/method_card.py`.
- Mover la enumeración de mode/job a un modelo `FlowRegistryView` (fino, sin lógica) para el binding de UI.
- Mover la confirmación destructiva/experimental a un `ConfirmDialog` reutilizable.

### Qué fusionar
- Fusionar la página Quick y las páginas de ops chip para usar el mismo widget `FlowBrowser` con un filtro `modes`.
- Fusionar la gestión de avisos experimentales en el badge de la tarjeta + diálogo.

### Qué eliminar / desduplicar
- Eliminar las llamadas por página a `_add_job_flows` que duplican los mismos flujos de job; reemplazarlas con un `FlowBrowser` filtrado.
- Eliminar instancias duplicadas de `Flow` (misma key bajo varios modos) agrupando los modos en la tarjeta.
- Eliminar los encabezados brutos `QLabel(job.upper())` en favor de encabezados de sección con contadores.

### Nuevas funcionalidades
- La caja de búsqueda filtra por nombre y key de job/mode/método.
- Favoritos/recientes persistidos en ajustes.
- Leyenda de riesgo: solo lectura (verde), medio (ámbar), alto (rojo), experimental (ámbar punteado).
- Selección por lote: casillas para encolar varios métodos (ejecución secuencial con cancelación por paso).
- Arrastrar y soltar para reordenar favoritos.

### Criterios de aceptación
- Un navegador de flujos consistente en todas las páginas.
- Ningún botón de método duplicado para el mismo (job, mode, key).
- La búsqueda filtra en < 50 ms para 280 filas.
- Las puertas de capacidad desactivan visualmente los métodos con una infobulle de razón.

### Fase 7 — estado (implementado hasta ahora)
- **Forma elegida: actualización en página.** Introducir ahora el único camino de renderizado y mejorarlo en el lugar — `FlowBrowser` (vista) + `MethodCard` (botón) + `flow_meta` (enrutamiento/riesgo) — *sin* la navegación de tres paneles Job → Mode → Método por ahora. Las páginas mantienen su layout actual; `_add_job_flows` construye las filas y las renderiza mediante `FlowBrowser`, y los clics enrutan mediante `flow_meta.route_for`.
- **Modelo de riesgo derivado** (`flow_meta.risk_for`, la única fuente que un badge puede leer): `experimental` = key en `_EXPERIMENTAL_FLOW_MAP`; `high` = key en `_DESTRUCTIVE_CONFIRM` y por tanto **exactamente los flujos que la UI ya pide confirmar** (un badge nunca puede reclamar `high` sin diálogo, ni `read` sin ser solo lectura); `read` = solo para `READ_ONLY_JOBS` (`{"Read Device Info", "Detect Devices"}`); todo lo demás, incluidas keys/jobs desconocidos, cae por seguridad a `medium`.
- **Slice B1 — renderizado de flujos agrupado (este slice).** `FlowBrowser.set_rows` ahora agrupa lo que renderiza, corrigiendo los tres problemas nombrados:
  - El encabezado de job es ahora `{"REMOVE FRP"} · 6` — el crudo `QLabel(job.upper())` ganó un **contador** de métodos (atenuado con el token `border_hi`, el nombre mantiene el tratamiento existente 11px / 800 / 1px).
  - Dentro de cada job, las tarjetas se agrupan por **modo de transporte** tras un pequeño subtítulo de modo (`— ADB`), en lugar de una lista plana por job con el modo solo en la infobulle. Las filas llegan en orden mode-major desde `_flow_rows`, así que una racha de modos iguales es una sección; ningún modo se expande nunca en tarjetas extra.
  - Cada `MethodCard` pinta un **borde izquierdo** semántico (`ok` solo lectura, `warn` medio, `err` alto, `experimental` experimental) compuesto sobre `_btn_ghost()`, para que el riesgo sea visible de un vistazo junto a la leyenda existente. Las tarjetas experimentales mantienen su borde **discontinuo** ámbar — ahora propiedad de `MethodCard.set_risk(level)`; `set_state` permanece inerte.
  - Inalterado por construcción: el conjunto de filas renderizado, la regla de desduplicación (“el primer modo gana” por job), el texto del botón (`btn_sha`), todas las cadenas de infobulle, el enrutamiento de clics, las capas confirm/experimental y el registro de puertas (`job=`/`mode=`, nunca `command=`). Solo se añadieron widgets de agrupación/etiqueta.
- **Golden regenerado aquí deliberadamente.** `tests/ui_inventory_golden.json` se reconstruyó con `REGEN_INVENTORY=1` en este slice. La **única** diferencia es el **conteo de widgets** por página (las etiquetas de subtítulo de modo añadidas; +113 widgets repartidos en las cinco páginas ricas en flujos). `gated_count`, `gated_unique_triples`, `gated_triples_sha256`, `core_flows`, `action_meta` y los `buttons` / `acts` / `btn_sha` de cada página son byte-idénticos — el registro de puertas y la superficie de clic no se movieron.
- **Slice B2 — tablero de modelo (tarjetas de acción verticales) (este slice).** Las filas de acción por modelo de la página de modelo son ahora tarjetas `ActionRow` (`python/gui/widgets/action_row.py`) en lugar del `QFrame` artesanal de 50px con un `mousePressEvent` monkeypatcheado:
  - un **borde izquierdo semántico de 3px** (`err` para acciones de borrado/destructivas, en caso contrario `accent_hi`) — el mismo lenguaje de borde de riesgo que pinta `MethodCard.set_risk` en el navegador de flujos,
  - un **tile de icono 40x40**, un título **13px / 800** y una descripción **de una línea elidida**. Esto corrige el “libellés largos de flujo desbordan/se repliegan de forma impredecible” del plan: la descripción se elide en lugar de repliegarse, por lo que un libellé largo nunca puede forzar el tablero más ancho que su panel ni leerse como un bloque multilínea ragged,
  - un **chip** de motor/modo opcional y una **chevron** `›` atenuada; hover / pressed / focus son propiedad del widget (propiedad dinámica QSS + anillo de foco). El chip se pinta como una **píldora de un solo tono** a partir del color de acento que ya devuelve `common._mode_chip` (relleno teñido de acento, texto de acento, borde fino de acento), de modo que cada badge se lee como una misma familia,
  - **accesible por teclado** — `StrongFocus` + Enter / Return / Space emiten la señal `activated` (reemplazando el `mousePressEvent` monkeypatcheado). El tablero conserva sus tags `flow_act` / `flow_tip` y solo conecta `activated`, por lo que el enrutamiento no cambia,
  - los contenedores de grupo ahora llevan el **contador** de acciones del job (`FRP REMOVE · 4`) — el mismo lenguaje de nombre + contador que los encabezados de job del navegador de flujos.
- **Invariantes respetados.** `_ACTION_META` sigue teniendo **62** entradas; los `acts` y `btn_sha` de cada página `dev_*` son byte-idénticos (no se añadió/eliminó/renombró ninguna fila de acción, texto de botón ni botón); `gated_count` **418**, `gated_triples_sha256` `c89acce…7d75`, `gated_unique_triples` **61**, `core_flows` **116**, `stack_count` **25**. El ancho mínimo natural de la pila de páginas sigue siendo **699px**, lo que prueba que los libellés elididos no ensancharon nada.
- **Golden regenerado aquí deliberadamente.** `tests/ui_inventory_golden.json` se reconstruyó con `REGEN_INVENTORY=1` en este slice: la única diferencia es el **conteo de widgets** por página (`dev_apple` 59→63, `dev_motorola` 85→99 — las tarjetas/etiquetas añadidas de los dos tableros researched). El md5 transitorio del golden tras B2 fue `929f428638e91a42865ddde1ac96dd19`. El pulido posterior de este slice documental (la familia de chips de un solo tono y la división del panel de dispositivo en primera muestra) no cambió **ningún** conteo de widgets de página, por lo que el golden no necesitó **ninguna** regeneración adicional.
- **Slice B4 — el tablero de modelo llena la altura de la página (este slice).** En la página modelo de dispositivo → tablero (`devices.build_brand_page`), la fila de división en dos paneles no recibió la altura de la página, dejando una amplia banda vacía **debajo** de ambos paneles. En una ventana 1600x951 (viewport exterior de página `878x717`) los paneles midieron `left 250x313 / right 598x333` con una **banda muerta de 333px** debajo, y el tablero de acción recibió solo `333` de `717px`. Causa raíz: la fila de división fue añadida a `outer` **con stretch 1** *y* un `outer.addStretch(1)` final añadido justo después — los dos elementos estirados compartieron el espacio vertical restante ~50/50, y ningún panel era verticalmente `Expanding`, por lo que nada lo absorbía. Corrección (quirúrgica, solo en `build_brand_page`): eliminar el stretch final competidor (la fila de división ahora toma **toda** la altura restante) y dar al `list_col` izquierdo y al `right_stack` derecho una política vertical `Expanding` explícita, para que el `lscroll` interior y el `_scroll` interior de la página de modelo actual reciban la altura completa y posean sus propias barras de desplazamiento. Las filas de la izquierda permanecen alineadas arriba (`lv2.addStretch(1)` no se toca) y se desplazan cuando crece la lista. Después: `left 250x646 / right 598x665`, banda muerta **1px** (solo el margen inferior de 8px del layout), el tablero de la derecha muestra muchos más flujos y desplaza el resto internamente (`vscroll_max` 900 → 557), y el `_page_scroll` exterior del shell permanece oculto (`verticalScrollBar().maximum() == 0`). Para respaldar el futuro requisito del usuario, 40 modelos extra en memoria aumentan el rango de desplazamiento de la lista **izquierda** (`vscroll_max > 0`) **sin** cambio alguno en la altura de ningún panel.
  - Nuevas pruebas: `tests/test_device_board_layout.py` — `TestBrandPageFillsHeight::test_no_dead_band_below_split`, `::test_both_panes_get_the_real_height`, `::test_right_board_scrolls_its_own_content`, `::test_more_devices_scroll_left_without_growing_the_panes`. Ambas pruebas de geometría se confirmaron como **fallando** en el código sin corregir primero (banda muerta 295px a H=640; panel izquierdo 275px contra el mínimo de 412px) antes de la corrección.
  - **No se añadió ni eliminó ningún widget** (solo cambió una política de tamaño y se eliminó un espaciador stretch), por lo que ninguna página modificó su conteo de widgets y `tests/ui_inventory_golden.json` no necesitó **ninguna** regeneración — sigue siendo `929f428638e91a42865ddde1ac96dd19`.
- **Slice C — registro completo de flujos en el tablero de dispositivos (REVERTIDO).** Este slice añadió un grupo final `MORE FLOWS · N` renderizando el registro completo de flujos del motor del dispositivo como tarjetas `ActionRow`, además de una barra de filtro texto/modo. Se acotó por **motor + modo de transporte**, que no es lo mismo que las *funciones de este dispositivo*: cualquier teléfono que expusiera ADB tiraba por tanto todos los flujos registrados en ADB del registro, por lo que el tablero de Motorola ofrecía jobs exclusivos de Samsung (`knox_bypass`, `kg_remove`, `odin_flash_tar`), `imei_repair_spd`, `apple_icloud_*` y `huawei_frp_guide`. Peor aún, los modelos Motorola llevan **motores por modelo** (`Moto G13` = `spd`, `G24` = `mtk`, `G6` = `qcom`), así que los modelos `planned` mostraban un registro SPD/MTK entero para trabajo no realizado, y las marcas motorola/apple sortean por diseño la puerta `researched` en el tablero. Reversión completa: el grupo del registro, su barra de filtro, `_ENGINE_MODES`, la deferral a la primera muestra y `tests/test_device_flows.py` han desaparecido; el tablero vuelve a ser exactamente las acciones curadas por dispositivo. El golden de inventario permaneció byte-idéntico (`929f428638e91a42865ddde1ac96dd19`) porque el grupo se construía perezosamente, por lo que la reversión no necesita regeneración tampoco.
  - Lección para cualquier reintento: acotar por las **`actions` declaradas del propio modelo** (`supported_devices.json`), expandiendo solo los flujos a los que esas acciones realmente dispatchan — nunca por motor + modo.
  - Hecho verificado que sobrevive y es reutilizable: `win._route_flow_activation(job, mode, key, label)` es el único sumidero que aplica la confirmación destructiva y el acuse EXPERIMENTAL de propiedad; `_dispatch`/`start_model_action` no lo es (su comprobación experimental es el conjunto estrecho `devices._EXPERIMENTAL_ACTS`, así que p. ej. `emmc_raw` se ejecutaría sin acuse).
- **Aplazado (todavía):** caja de búsqueda / chips de filtro por modo sobre una lista de flujos por dispositivo, favoritos/recientes (persistidos en ajustes), la cola de selección por lote (casillas + ejecución secuencial), reordenamiento por arrastre, la navegación Job → Mode → Método de tres paneles, expandir las variantes de modo de un job en tarjetas extra (una tarjeta por `(job, mode, key)` es una decisión deliberada posterior — este slice NO expande modos) y un `ConfirmDialog` reutilizable (las capas confirm/experimental siguen siendo modales propiedad de la ventana).

## Fase 8 — Pulido profesional y diferenciación (nuevo)
### Identidad visual
- Tema oscuro firma “atelier” con textura sutil de grano/ruido y viñeta suave.
- Marca + monograma; iconografía consistente (estilo Lucide) en todas las acciones.
- Tarjetas hero de dispositivo: silueta de imagen del modelo, chip, badges de transporte, último visto.
- Escena de conexión animada mejorada: verdadero pulso de cable, puntos de estado por dispositivo.

### Densidad de información
- Panel inspector colapsable: detalles del dispositivo seleccionado, particiones, resumen PIT, logs.
- Vista de línea temporal de operaciones (inicio/fin, duración, resultado) por dispositivo.
- Vista diff para cambios PIT/partición antes del flash.

### Seguridad y confianza
- Tarjeta de checklist pre-vuelo antes de ops destructivas (dispositivo, firmware, coincidencia PIT).
- Escalera de riesgo clara con color + icono + texto; nunca solo color.
- Visualizador de log de auditoría (acciones experimentales) con exportación.

### Productividad
- Paleta de comandos (Ctrl+K) para buscar flujos, dispositivos, ajustes.
- Búsqueda global en logs y dispositivos.
- Navegación primero teclado; superposición de atajos (?).
- Restauración de sesión: reabrir el último dispositivo + página.

### Sensación Linux-nativa
- Diálogos de archivo nativos, conciencia del tema del sistema, manejo de Wayland/X11.
- Notificaciones de escritorio para ops largas; icono de bandeja con progreso.
- Arrastrar y soltar archivos de firmware sobre la página de flash.

### Onboarding
- Asistente de primer arranque: configuración udev, estado de build del puente, prueba de dispositivo.
- Estados vacíos con ilustraciones y siguientes pasos.
- Cajón de ayuda contextual con docs por flujo desde `operations/`.

### Recursos de marca
- Nuevo conjunto de logos, splash, gráficos de instalador, icono de app.
- Capturas de README actualizadas para coincidir con el nuevo UI.

## Fase 9 — Rediseño de consola / terminal (nuevo)
### Objetivo
Hacer que el log de consola se sienta como un terminal Linux de primera clase (estética UEFI-shell/TTY) en lugar de una caja de texto estrecha.

### Layout
- Dock **a la derecha** dedicado en un divisor horizontal (páginas a la izquierda, consola a la derecha); redimensionable, colapsable a una barra delgada. Ancho por defecto 420px, mínimo 360px (medido desde la propia fila de control del dock para que nada se recorte). _Decisión (usuario): la consola se queda a la derecha — un borrador anterior de esta fase decía “dock inferior / 35% de altura”; queda sustituido._
- Terminal ancho, monoespaciado, con padding cómodo (16px), altura de línea 1.45.
- Modo terminal a pantalla completa opcional (F11) con chrome mínimo.
- Pestañas por dispositivo o chips de filtro para que los logs no se entrelacen.

### Styling
- Paleta TTY oscura: fondo negro, texto verde/ámbar/cian, scanline opcional sutil.
- Soporte de colores ANSI para la salida del puente; encabezados en negrita, timestamps atenuados.
- Interruptor de números de línea / timestamps.
- Selección + copia; menú clic derecho (copiar, guardar, limpiar, filtrar).

### Comportamiento
- Streaming con backpressure; sin congelamiento de UI con 10k+ líneas.
- Búsqueda con regex, resaltado de coincidencias, saltar siguiente/anterior.
- Exportar a archivo; auto-guardado del log de sesión.
- Filtro por dispositivo y por nivel (info/warn/error/step).

### No apretado
- Restricciones de ancho/alto mínimos; ajuste responsivo; desplazamiento horizontal para líneas largas.
- Columnas redimensionables para timestamp/nivel/dispositivo.

## Fase 10 — Mensajes de consola y sistema de toasts (nuevo)
### Mensajes de consola
- Entradas de log estructuradas: timestamp, key de dispositivo, nivel, mensaje.
- Niveles coloreados: info (pizarra), éxito (verde), aviso (ámbar), error (rojo), paso (cian).
- Salida multilínea colapsable (trazas de pila, JSON) con “mostrar más”.
- Barras de progreso en línea para los pasos de flash; iconos de estado por paso.
- Keys de dispositivo clicables para enfocar el dispositivo; keys de flujo clicables para abrir la doc.

### Toasts
- Toasts no bloqueantes, apilados con icono, título, mensaje, botón de acción.
- Desaparición automática con barra de progreso; pausa al pasar el ratón.
- Estilos de severidad (info/éxito/aviso/error) con paleta consistente.
- Límite de cola (máx. 3 visibles) con contador de desbordamiento.
- Opciones de posición (arriba-derecha/abajo-derecha) y soporte de movimiento reducido.
- Sonido/háptico opcional para errores.

## Fase 12 — Investigación de paridad HiProTool (nuevo)
### Estado
- Búsqueda en línea no disponible en este entorno (HTTP 402). Se requiere investigación manual.

### Tareas de investigación
- Recopilar la lista de funcionalidades de HiProTool (FRP, MDM, bloqueo de pantalla, operador, IMEI, flash).
- Mapear cada método a un motor (ADB, modo download, BROM, EDL, fastboot, SPD).
- Identificar atajos y prerrequisitos específicos por dispositivo.
- Documentar en `operations/` con pasos de verificación y notas de seguridad.
- Priorizar primero los métodos de alto valor y bajo riesgo.

## Fase 14 — Próximas funcionalidades (nuevo)
### Funcionalidades objetivo
- Eliminación del IMEI de la lista negra (investigación + playbooks por dispositivo).
- Mejoras de desbloqueo de operador (bloqueo SIM, rutas NVDATA/QCN).
- Mejoras de desbloqueo MDM (device owner, provisioning QR, recovery).
- Mejoras de FRP (métodos por chip/versión de Android).
- Mejoras de eliminación de bloqueo de pantalla (ADB, recovery, download, EDL).
- Eliminación del Samsung Knox Guard (EXPERIMENTAL, audit-logged).
- Eliminación del enrollment MDM de Apple (profile/DEP).
- Herramientas de gestión Samsung Knox.
- Gestión del enrollment Android Enterprise.
- Gestión del enrollment zero-touch.
- Eliminación del bloqueo de activación de Apple (alcance checkm8/DFU, límites honestos).
- Recuperación del PUK de SIM para desbloquear el PIN SIM.
- Eliminación de bloqueo biométrico (investigación, límites de dispositivo).

### Notas
- Cada funcionalidad debe estar respaldada por Rust y marcada como EXPERIMENTAL donde sea arriesgada.
- Documentar en `operations/` con verificación y notas de seguridad.

## Fase 15 — Auditoría y limpieza de documentación (nuevo)
### Referencias obsoletas encontradas (históricas/retiradas)
- `operations/*/README.md` mencionan módulos Python retirados (`knox.py`, `qcn.py`, `health.py`, `apple.py`, `flows/*.py`) como contexto; aceptable pero debe marcarse claramente como histórico.
- `INDEX.md` referenciaba antes un `SPLIT_PLAN.md` faltante (corregido).
- `README.md` la disposición del repositorio listaba antes módulos inexistentes (corregido).
- `DESCRIPTION.md` tenía conteos incorrectos de transportes/jobs (corregido).

### Tareas de documentación restantes
- Normalizar todas las notas “retirado” en una sola sección “History” por archivo.
- Añadir una nota “Current architecture” al inicio de cada README de operations.
- Eliminar o archivar planes de migración obsoletos (DESIGN.md → nueva versión).
- Mantener `operations/` como solo investigación; los punteros de código deben decir `src/flows.rs`.