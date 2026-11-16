# ImproveCore — Mejoras del núcleo Rust

Language switcher: [English](../../improvecore.md) · [Français](../fr/improvecore.md) · **Español**

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

Fuente: elementos relacionados con Rust movidos desde `ui-improvement.md`.

## Flasheo ADB por dispositivo
- Sesiones ADB indexadas por dispositivo con reintentos/backoff y máquina de estados clara.
- Verificación tras escritura (hash) por defecto; progreso por partición.
- Gestión robusta de estados no autorizado/fuera de línea; indicador de reautenticación automática.
- Soporte de múltiples dispositivos ADB concurrentes sin interferencia.

## Innovación Odin (Samsung)
- Superar el último Odin: resiliencia de sesión única, recuperación por restablecimiento de puerto, streaming multi-partición.
- Mejor validación de PIT, manejo de vbmeta/AVB, guía de reparación drk.
- Reanudación/reintento ante errores USB transitorios; explicaciones detalladas de fallos.

## Comunicaciones BROM / bajo nivel
- Abstracción BROM unificada para MTK, Samsung, SPD, Qualcomm.
- Auxiliares crash-to-BROM, SLA/auth, fiabilidad de carga de DA.
- Clasificación de errores con correcciones accionables; tiempos límite por etapa.

## Soporte MTK reciente
- Análisis de preloader V5/V6 y selección de DA (`mtk_daloader.rs`).
- Seguimiento de las versiones recientes de DA/preloader MTK; autodetección y selección.
- Garantizar el funcionamiento de las rutas exploit/SLA en los chips más recientes; añadir fixtures de prueba.

## Detección de interfaz USB
- Detectar CDC ACM, ECM/NCM, almacenamiento masivo, HID, específico del fabricante, diagnóstico/módem.
- Detectar bootrom, preloader, ADB, modo download, EDL, MTK, SPD.
- Exponer la lista de interfaces en las filas de dispositivo; asignar a los flujos compatibles.

## Eliminación instantánea (FRP/MDM/bloqueos)
- Investigación de integración estilo HiProTool: rutas rápidas cuando sea seguro, documentadas.
- Playbooks por dispositivo en `operations/` con pasos verificados.
- Mantener el gating experimental + registro de auditoría para ops arriesgadas.