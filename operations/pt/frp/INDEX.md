Language switcher: [English](../../frp/INDEX.md) · [Français](../../fr/frp/INDEX.md) · [Español](../../es/frp/INDEX.md) · [Deutsch](../../de/frp/INDEX.md) · [简体中文](../../zh/frp/INDEX.md) · [Русский](../../ru/frp/INDEX.md) · **Português** · [日本語](../../ja/frp/INDEX.md) · [العربية](../../ar/frp/INDEX.md) · [हिन्दी](../../hi/frp/INDEX.md) · [Türkçe](../../tr/frp/INDEX.md)

> English is the canonical source. This page is a translation; help wanted — see [`../../../docs/TRANSLATION.md`](../../../docs/TRANSLATION.md).

# operations/frp/ — Proteção de redefinição de fábrica (Factory Reset Protection, apenas Android)

> Os dispositivos Apple não têm FRP (a Apple usa Activation Lock / iCloud em seu
> lugar) — ver `operations/apple/`.

Este diretório contém **árvores de documentação por motor** para bypass de FRP.
O código real reside em `src/flows.rs` (Rust). Quando você tiver uma receita real
para um dispositivo (chip, par de FDL, offsets de partição, etc.), coloca uma
nota curta de pesquisa em `devices/<brand>/<model>.md`. O README na raiz deste
arquivo mapeia todo fluxo FRP do codebase a onde reside e do que precisa.

## Mapa de motores

| Motor | Quando usar | Código | CLI do bridge |
|---|---|---|---|
| **Genérico (ADB)** | Primeira tentativa em qualquer telefone com depuração USB ligada | Fluxos Rust (`adb_frp`, `frp_*` linhas em `src/flows.rs`) | `flow-run adb_frp` / `adb shell ...` via `bridge.adb_shell` |
| **MTK BROM** | MediaTek (Helio / Dimensity / MT6765) — desligar → segurar Vol-/+ → plugar USB | Fluxos Rust (`mtk_*` linhas em `src/flows.rs`) | `flow-run mtk_brom_info` (CLI: `mtk-detect`, `mtk-da-upload`, `mtk-frp`, `mtk-bypass`) |
| **MTK DA** | MTK BROM que sobreviveu ao upload de DA (chips com estado bloqueado) | Fluxos Rust (`mtk_brom_backup`, `mtk_auth_flash`) | `flow-run mtk_brom_backup` |
| **Qualcomm EDL** | Download de emergência 9008 (Snapdragon) | Fluxos Rust (`edl_*`, `qcom_*` linhas) | `flow-run edl_frp` (CLI: `qcom-*`) |
| **Samsung Exynos** | A14 (Exynos 850/1330), A15/A16 — modo Download Odin é só flasheo, NÃO para FRP | Linhas Rust `frp_*` (bypass de conta Samsung) | (principalmente no dispositivo, sem bridge) |
| **Samsung MTK (A05/A06)** | A05/A06 com Helio G85 — usa MTK BROM (acima) | Fluxos Rust (`mtk_brom_info`, `mtk_brom_backup`) | `flow-run mtk_brom_backup` |
| **UNISOC/SPD** | 1782:4d00 FDL1+FDL2 (SC9863A, T606/UMS9230) | Fluxos Rust (`spd_*` linhas) + `src/spd.rs` | `flow-run spd_detect_info` (CLI: `spd-detect`, `spd-frp`, `spd-format`, `spd-magic-pack`) |
| **HiSilicon Kirin** | 12d1 — ainda sem fluxo aberto (não submetido a engenharia reversa) | (nenhum ainda) | (nenhum) |

(Antigos módulos de motor `python/core/flows/*.py` nunca foram publicados;
`mtk-brom-backup` é a linha de fluxo `mtk_brom_backup`. Verifique qualquer chave
com `flow-list`.)

## Mapa de fluxo (key → função)

Todo fluxo que as ações FRP da GUI podem chamar. As chaves são linhas do
registro Rust (`src/flows.rs`, `flow-list` para verificar); a GUI as roteia por
(job, mode) e o bridge as executa via `flow-run <key> [target]`.

| Chave de fluxo | Motor | O que faz |
|---|---|---|
| `adb_frp` | ADB genérico | `settings put secure frp 0` + desativar assistentes de setup + limpar dados do GMS |
| `frp_browser` | ADB genérico | Abrir `chrome://settings/` no dispositivo via intent |
| `frp_emergency` | ADB genérico | Abrir configurações via dialer de chamada de emergência (no dispositivo) |
| `frp_settings` | ADB genérico | Abrir configurações via caminho do painel de notificações (no dispositivo) |
| `frp_fake_login` (+`_testdpc`, `+_adp`) | ADB genérico | Provisionamento por QR com DPC de proprietário do dispositivo, depois limpeza de FRP |
| `at_info` | Samsung MTP/AT | Ler modo + devconinfo via canal AT (Samsung pré-Android 8) |
| `at_method` | Samsung MTP/AT | AT+DEBUGLVC para habilitar ADB pela porta diag |
| `download_frp` | Modo Download Samsung | Remoção de FRP com firmware CSC/Combination (contrato de segurança PIT) |
| `odin_enable_adb` | Modo Download Samsung | Habilitar ADB a partir do modo download via tarball Odin |
| `mtk_combo_flash` | MTK Download | Flasheo de firmware Combination (PIT + DA) |
| `mtk_recovery_reset` | MTK Download | Redefinição de fábrica em modo recovery |
| `mtk_brom_info` | MTK BROM | Ler id do chip / handshake (necessário antes de qualquer flash BROM) |
| `mtk_brom_backup` | MTK BROM | Despejar partições via BROM DA |
| `edl_frp` | Qualcomm EDL | Sahara + Firehose erase (05c6:9008) |
| `qcom_detect_info` | Qualcomm EDL | Detectar + info (somente leitura) |
| `frp_qr_provision` | ADB genérico | Provisionamento por QR (caminho TestDPC) |

(Retirado: os antigos nomes de chave com prefixo `flow_*` e
`python/core/flows/*.py` nunca foram publicados — as chaves não têm prefixo
`flow_`.)

## Como uma nova receita por modelo chega aqui

1. **Execute um dump real do dispositivo** (ver `scripts/dump-connected.sh` para o
   caminho via ADB, ou `flashpilot-bridge spd-format` para o caminho BROM em
   Unisoc). O dump vai para `build/cache/dumps/<model>_<codename>/`.

2. **A partir do dump, identifique** o motor + chip + o nome da partição FRP
   (quase sempre `frp`, `frp_a` ou `userdata` no Android 11+).

3. **Adicione a entrada do dispositivo** em `python/gui/supported_devices.json`
   sob a marca correta, com `actions: ["frp", "info", "backup", "flash"]` e
   `status: "researched"`. (O fluxo por motor existente o recolherá
   automaticamente — não é preciso um novo fluxo, a menos que o próprio motor
   esteja faltando.)

4. **Soltar uma nota curta de pesquisa** em `operations/frp/devices/<brand>/<model>.md`
   com o chip, o motor, a partição, a impressão de build e uma
   linha confirmando a receita (ex., "mmcblk0p4 = frp, apagamento instantâneo
   por BROM DA, sem combo"). Ver
   `operations/frp/devices/nokia/nokia_g20.md` para o formato.

5. **Se o motor ainda não tiver um fluxo** para esse chipset, registre o fluxo
   em `src/flows.rs` (uma linha `flow!(...)`) e adicione o despacho CLI em
   `src/<engine>.rs` + `src/main.rs`.

## Por que os arquivos por chip desapareceram

Antigos refatoramentos dividiram o god `frp.py` em arquivos por chip sob
`operations/frp/chips/` e arquivos por motor sob
`operations/frp/{mtk,qualcomm,unisoc,samsung}_frp/`. Uma revisão antiga deste
INDEX afirmou stubs de doc mortos e um despacho `python/core/flows/brom.py`
— esse módulo nunca foi publicado. O despacho real por chip é o registro de
fluxos Rust (`src/flows.rs`: linhas `mtk_*`/`qcom_*`/`spd_*`, `flow-list` para
verificar); este INDEX.md é o mapa para que um novo dev saiba onde o código
específico do motor realmente vive.

## Por que os shims Python por motor desapareceram

`operations/frp/mtk_frp/mtk_frp.py` (e seus 4 irmãos) importavam funções de
`python.core.flows.brom` e as reexportavam sob um **segundo** dict
`FLOWS = {}` que a GUI nunca lê. Colidiam com o `FLOWS` canônico em
`python/core/flows/__init__.py` e poderiam ter mascarado os reais se a GUI os
lêsse. Foram substituídos por um README em cada pasta de motor que aponta para
os módulos Python reais.