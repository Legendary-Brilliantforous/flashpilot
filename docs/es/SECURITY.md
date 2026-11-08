Language switcher: [English](../../SECURITY.md) · [Français](../../fr/SECURITY.md) · **Español** · [Deutsch](../../de/SECURITY.md) · [简体中文](../../zh/SECURITY.md) · [Русский](../../ru/SECURITY.md) · [Português](../../pt/SECURITY.md) · [日本語](../../ja/SECURITY.md) · [العربية](../../ar/SECURITY.md) · [हिन्दी](../../hi/SECURITY.md) · [Türkçe](../../tr/SECURITY.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

# Política de seguridad

## Versiones compatibles

El proyecto está en fase pre-1.0. Las correcciones de seguridad se aplican en la
rama `main` y, cuando existe, en la última release etiquetada.

## Reportar una vulnerabilidad

Por favor, **no** abras un issue público para problemas de seguridad. Repórtalo
de forma privada:

- Correo: **flashpilot@proton.me** (crea esta dirección en proton.me → cuenta
  gratuita), o
- Formulario privado de reporte de vulnerabilidades de GitHub en este
  repositorio.

Por favor incluye:

- Comando / flujo afectado y versión,
- Pasos para reproducir,
- Impacto (p. ej., ejecución de código arbitrario, riesgo de brick, pérdida de
  datos, exposición de credenciales).

Nos comprometemos a acusar recibo de los reportes en 72 horas y a coordinar la
divulgación.

## Alcance y expectativas

Esta herramienta realiza deliberadamente operaciones USB / bootloader de bajo
nivel. Por su naturaleza puede borrar o brickear un dispositivo. Ese es un
comportamiento documentado, no una vulnerabilidad. Nos preocupa:

- Exploits que ejecutan código no confiable más allá de la operación prevista,
- Evitar las confirmaciones de seguridad / comprobaciones de dispositivo de una
  forma que perjudique a los usuarios,
- Incluir blobs propietarios o secretos en el repositorio,
- Cualquier cosa que filtre datos del dispositivo o credenciales del usuario.

Por favor, opera únicamente en dispositivos que poseas o estés autorizado a
reparar.