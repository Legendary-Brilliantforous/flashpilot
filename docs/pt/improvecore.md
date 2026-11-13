# ImproveCore — Melhorias do núcleo Rust

Language switcher: [English](../../improvecore.md) · [Français](../fr/improvecore.md) · [Español](../es/improvecore.md) · [Deutsch](../de/improvecore.md) · [简体中文](../zh/improvecore.md) · [Русский](../ru/improvecore.md) · **Português** · [日本語](../ja/improvecore.md) · [العربية](../ar/improvecore.md) · [हिन्दी](../hi/improvecore.md) · [Türkçe](../tr/improvecore.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

Fonte: itens relacionados ao Rust movidos de `ui-improvement.md`.

## Flasheo ADB por dispositivo
- Sessões ADB indexadas por dispositivo com retry/backoff e máquina de estados clara.
- Verificação após escrita (hash) por padrão; progresso por partição.
- Tratamento robusto de estados não autorizado/offline; prompt de reautorização automática.
- Suporte a múltiplos dispositivos ADB concorrentes sem cross-talk.

## Inovação Odin (Samsung)
- Superar o Odin mais recente: resiliência de sessão única, recuperação por reset de porta, streaming multi-partição.
- Melhor validação de PIT, tratamento de vbmeta/AVB, guia de reparo drk.
- Retomada/retry em erros USB transitórios; explicações detalhadas de falhas.

## Comunicações BROM / baixo nível
- Abstração BROM unificada para MTK, Samsung, SPD, Qualcomm.
- Auxiliares crash-to-BROM, SLA/auth, confiabilidade de upload de DA.
- Classificação de erros com correções acionáveis; timeouts por etapa.

## Suporte MTK recente
- Parsing de preloader V5/V6 e seleção de DA (`mtk_daloader.rs`).
- Acompanhar as versões recentes de DA/preloader MTK; autodetecção e seleção.
- Garantir que os caminhos exploit/SLA funcionem nos chips mais novos; adicionar fixtures de teste.

## Detecção de interface USB
- Detectar CDC ACM, ECM/NCM, mass storage, HID, vendor-specific, diagnostic/modem.
- Detectar bootrom, preloader, ADB, download mode, EDL, MTK, SPD.
- Expor lista de interfaces nas linhas de dispositivo; mapear para fluxos suportados.

## Remoção instantânea (FRP/MDM/bloqueios)
- Pesquisa de integração estilo HiProTool: caminhos rápidos onde for seguro, documentados.
- Playbooks por dispositivo em `operations/` com passos verificados.
- Manter experimental gating + audit logging para operações de risco.