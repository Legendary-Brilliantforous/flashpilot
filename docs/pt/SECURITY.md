Language switcher: [English](../../SECURITY.md) · [Français](../fr/SECURITY.md) · [Español](../es/SECURITY.md) · [Deutsch](../de/SECURITY.md) · [简体中文](../zh/SECURITY.md) · [Русский](../ru/SECURITY.md) · **Português** · [日本語](../ja/SECURITY.md) · [العربية](../ar/SECURITY.md) · [हिन्दी](../hi/SECURITY.md) · [Türkçe](../tr/SECURITY.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

# Política de segurança

## Versões compatíveis

O projeto está em fase pré-1.0. Correções de segurança entram na branch `main` e,
quando existir, na última release tagueada.

## Reportando uma vulnerabilidade

Por favor, **não** abra um issue público para problemas de segurança. Reporte de
forma privada:

- E-mail: **flashpilot@proton.me** (crie este endereço em proton.me → conta
  gratuita), ou
- Formulário privado de reporte de vulnerabilidade do GitHub neste repositório.

Por favor, inclua:

- Comando / fluxo afetado e versão,
- Passos para reproduzir,
- Impacto (p. ex., execução de código arbitrário, risco de brick, perda de
  dados, exposição de credenciais).

Empenhamo-nos em acusar o recebimento de reportes em 72 horas e coordenaremos a
divulgação.

## Escopo e expectativas

Esta ferramenta executa deliberadamente operações USB / bootloader de baixo nível.
Por natureza ela pode apagar ou brickar um dispositivo. Esse é um comportamento
documentado, não uma vulnerabilidade. Nos preocupamos com:

- Exploits que executam código não confiável além da operação prevista,
- Desviar das confirmações de segurança / checagens de dispositivo de uma forma
  que prejudique usuários,
- Incluir blobs proprietários ou segredos no repositório,
- Qualquer coisa que vaze dados do dispositivo ou credenciais do usuário.

Opere apenas em dispositivos de que você seja proprietário ou autorizado a atender.