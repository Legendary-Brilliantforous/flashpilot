# FlashPilot — índice

Language switcher: [English](../INDEX.md) · [Français](../fr/INDEX.md) · [Español](../es/INDEX.md) · [Deutsch](../de/INDEX.md) · [简体中文](../zh/INDEX.md) · [Русский](../ru/INDEX.md) · **Português** · [日本語](../ja/INDEX.md) · [العربية](../ar/INDEX.md) · [हिन्दी](../hi/INDEX.md) · [Türkçe](../tr/INDEX.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

O README tem o marketing. Este arquivo é o índice de engenharia — cada pasta, o que faz e onde começar.

## Executar

```bash
# GUI
python main.py

# CLI (bridge) — mesmo protocolo, sem GUI
./target/release/flashpilot-bridge detect-all
./target/release/flashpilot-bridge spd-detect
```

## Estrutura raiz (17 entradas)

| Entrada | O que | Quando abrir |
|---|---|---|
| `main.py` | Ponto de entrada da aplicação. Adiciona o repositório a `sys.path` e chama `python.gui.qt_app.main()`. | Para mudar como a app inicia. |
| `pyproject.toml` | Metadados do pacote Python (name=flashpilot, deps, backend de build). | Para adicionar uma dependência Python ou subir a versão. |
| `Cargo.toml` / `Cargo.lock` | Núcleo Rust (o binário `flashpilot-bridge`). | Para mudar a CLI do bridge ou adicionar um protocolo. |
| `python/` | Camada Python fina sobre o motor Rust: `python/core/` (shim + helpers de GUI) e `python/gui/` (PyQt6). Todos os fluxos vivem em `src/flows.rs`. | Encanamento GUI e dispositivos. |
| `src/` | Fontes Rust. Estrutura espelho de `python/core/`. | Quando você adiciona um comando de bridge ou muda um protocolo USB. |
| `tests/` | Suite pytest. ~149 testes, ~1s de execução. | Execute com `.venv/bin/python -m pytest tests/ -q`. |
| `scripts/` | Ferramentas shell autônomas. Hoje: `dump-connected.sh`, `validate_mtp_at.py`. | Para uma operação em lote sem GUI. |
| `docs/` | Recursos do README (capturas, logo). | Para o README. |
| `packaging/` | Script de build `.deb` + arquivos de controle. | Para enviar uma release. |
| `root/` | Regras udev (para telefones funcionarem sem sudo). | Configuração única. |
| `operations/` | **Árvores de documentação por job** — ver seção "operations/" abaixo. | Para entender um job específico (FRP, MDM, bloqueio de tela, etc.). |
| `build/` | **Todos os artefatos de build/runtime ignorados pelo git** — ver seção "build/" abaixo. | Você quase nunca abre. |
| `.github/` | Workflows de CI, templates de issues. | Para mudar a CI. |
| `LICENSE` `CODE_OF_CONDUCT.md` `CONTRIBUTING.md` `SECURITY.md` `DESCRIPTION.md` | Metadados padrão do projeto. | Ao fazer release. |

## Estrutura `python/`

```
python/
├── main.py                 <- app entry (adds repo to sys.path, calls python.gui.qt_app.main)
├── gui/                    <- PyQt6 app
│   ├── qt_app.py           <- The main window + every device-mode UI (~12k LOC)
│   ├── devices.py          <- Data-driven "supported devices" drill-down (brand -> model -> action)
│   ├── theme.py            <- Design tokens (colors, button styles, version helpers)
│   ├── animations.py       <- Painted glyphs: connection scene, status orb, etc.
│   ├── nav.py              <- Top-level navigation rail + OEM chip bar
│   ├── toast.py            <- Toast notifications
│   └── supported_devices.json  <- The database of which model gets which action
└── core/                   <- Thin Python layer (no Qt deps; delegates to Rust bridge)
    ├── core.py             <- FLOWS/JOBS/MODES mirror (hardcoded cache + Rust flow_list())
    ├── bridge.py           <- Talks to the Rust `flashpilot-bridge` binary
    ├── flow.py             <- Flow/Step primitives + cancellation
    ├── jobs.py             <- FlashJob lifecycle (isolated job layer)
    ├── cancel.py           <- Cooperative cancellation registry
    ├── devices.py          <- Multi-device identity (stable keys, list, resolve, transport mapping)
    ├── frp.py              <- FRP-only re-export surface (name == responsibility)
    ├── mtk.py              <- MTK PIDs/stages/chips (0003=BROM, 2000=preloader)
    ├── mtp.py              <- Samsung MTP/AT (multi-sequence ADB enable)
    ├── pit.py pitstore.py  <- Samsung PIT parser + cache
    ├── adb.py device_info.py actions.py experimental.py fus.py
    └── (no flows/ dir)     <- flows live in src/flows.rs; Python only delegates via bridge.flow_run()
```

**Os fluxos vivem em Rust.** `python/core/core.py` é um shim fino: `_RustFlow` delega a execução a `bridge flow-run <key>`. O registro canônico é `src/flows.rs` (macro `flow!`, ~280 linhas); Python o reflete para a busca da GUI.

## Estrutura `src/` (Rust)

```
src/
├── main.rs                 <- All CLI dispatch (eprintln! is the "log" channel) + flow-run
├── flows.rs                <- THE flow registry (flow! macro; FLOWS/JOBS/MODES)
├── usb/                    <- libusb context, descriptor parsing, filtering (mod.rs + filtering.rs)
├── devices.rs              <- merged USB+ADB device rows
├── sam_download.rs         <- Samsung Download/Odin session (odin-* commands)
├── sam_errors.rs sam_setup.rs sam_*.rs  <- Samsung helpers
├── mtk.rs mtk_da.rs        <- MediaTek BROM/DA flashing
├── mtk_exploit.rs          <- BROM exploits (bypass/kamakiri2/crash-to-BROM)
├── mtk_sla.rs mtk_sla_keys.rs <- Secure Lock Authentication
├── mtk_daloader.rs         <- DA container parsing
├── qualcomm/               <- EDL: Sahara + Firehose + GPT
├── spd.rs                  <- UNISOC BSL (BSL_CMD_*, BSL_REP_*, FDL1/FDL2)
├── pac.rs                  <- SPD PAC extract/pack
├── pit.rs                  <- Samsung PIT parser
├── mtp.rs at.rs adb.rs     <- MTP, AT command, ADB plumbing
├── fastboot.rs             <- native fastboot transport
├── moto_flash.rs           <- Motorola staged fastboot FRP
├── apple.rs                <- Apple usbmuxd/lockdown
├── bulk.rs hid.rs          <- bulk + HID helpers
├── fwtar.rs sparse.rs imgtools.rs <- firmware tar/sparse/boot-vbmeta
├── hostinfo.rs             <- host eMMC/UFS health
├── config.rs error.rs util.rs device.rs
└── (no odin.rs)            <- Odin logic lives in sam_download.rs
```

## `operations/` — árvores de documentação por job

Essas pastas contêm **README por operação** que explicam como cada job funciona, quais chaves de fluxo usa, quais dispositivos suporta e as advertências conhecidas. Não é código — a árvore é markdown puro (uma limpeza anterior removeu os shims `.py` obsoletos que costumavam viver aqui; nada importa `operations/`). O código vive em `src/flows.rs` (o registro `flow!`; `python/core/core.py` é um shim fino) e nos módulos por domínio (`knox.py`, `qcn.py`, `imei.py`, `emmc.py`, …). Os READMEs de `operations/` são escritos para usuários finais / pesquisadores de ferramentas comerciais; o código é a fonte da verdade.

| Pasta | O que | Código real em |
|---|---|---|
| `operations/apple/` | iCloud, bloqueio de ativação, MDM, remoção de código/modo perdido | Fluxos Rust (`src/flows.rs`: linhas `apple_*`, CLI `flow-run`) |
| `operations/frp/` | Bypass FRP por motor + notas de pesquisa por dispositivo. **Comece por `operations/frp/INDEX.md`**. | Fluxos Rust (registro `src/flows.rs`, CLI `flow-run`); shim fino `python/core/core.py` |
| `operations/mdm/` | Desbloqueio MDM / device-owner + notas por marca | Fluxos Rust (registro `src/flows.rs`, CLI `flow-run`) |
| `operations/screen_unlock/` | Remoção de bloqueio de tela (ADB / recovery / download / completo) | Fluxos Rust (registro `src/flows.rs`, CLI `flow-run`) |
| `operations/battery/` | Relatório / reparo / teste de carga da bateria (via ADB) | Fluxos Rust (registro `src/flows.rs`, CLI `flow-run`) |
| `operations/network/` | Estado SIM, DNS, reset de rádio | Fluxos Rust (registro `src/flows.rs`, CLI `flow-run`) |
| `operations/carrier_unlock/` | Bloqueio de operadora (Apple, MTK) | Fluxos Rust (registro `src/flows.rs`, CLI `flow-run`) |
| `operations/flashing/` | Guias de flash por fabricante (Samsung Odin, MTK DA, Qualcomm EDL, UNISOC SPD, PIT) | Fluxos Rust (registro `src/flows.rs`, CLI `flow-run`) |
| `operations/usb/` | Notas de enumeração e detecção USB | `src/usb/`, `src/devices.rs`, `python/core/devices.py` |

## `build/` — artefatos de build/runtime ignorados pelo git

| Subpasta | Conteúdo | Criado por |
|---|---|---|
| `build/target/` | Saída `cargo build` do Rust | `cargo build` |
| `build/dist/` | Pacotes `.deb` | `packaging/build-deb.sh` |
| `build/cache/` | Caches TAR por dispositivo e dumps de engenharia reversa | GUI / `scripts/dump-connected.sh` |
| `build/mdm_qr/` | Códigos QR de provisionamento MDM gerados | Fluxo GUI MDM |
| `build/pit/` | Arquivos `.pit` de tabela de partições em cache | Fluxo GUI PIT |

**Regra:** nunca faça `git add` de nada em `build/`. Se precisar apagar o estado, delete o subdiretório — será reconstruído.

## Como adicionar uma funcionalidade (a folha "qual arquivo eu toco?")

| Você quer... | Toque em |
|---|---|
| Adicionar um novo dispositivo à lista suportada | `python/gui/supported_devices.json` |
| Adicionar uma ação por fabricante a um dispositivo suportado | `src/flows.rs` (adicione uma linha `flow!(...)`); Python auto-descobre via `bridge.flow_list()` |
| Adicionar um fluxo ADB para um tema existente | Igual acima (Rust `src/flows.rs`) |
| Adicionar um novo comando CLI de bridge | `src/<tema>.rs` + `src/main.rs` (ramo `<cmd>` no match) |
| Adicionar uma nova página de navegação principal | `python/gui/qt_app.py` (`_build_*_page` + `_section_index`) |
| Adicionar uma cor / estilo de botão | `python/gui/theme.py` (dict `C` / `_btn_*()`) |
| Documentar as notas por job de um novo dispositivo | `operations/<job>/<marca>/<modelo>.md` |
| Adicionar um teste | `tests/test_<área>.py`, siga o padrão `test_mtk.py` |

## Como o executor de operações funciona (leia uma vez)

A GUI nunca chama um fluxo diretamente. O seletor de dispositivo por operação (`FlashPilotWindow._choose_device`) resolve primeiro uma chave de dispositivo estável; então `_run_ops_flow` / `_run_job_flow` chamam `python.core.core.flow_for(job, mode, method)`, que retorna um objeto `Flow()` (uma lista de `Step()`s), e então `flow.run(ctx, log)` é chamado em uma thread worker dentro de `devices.device_scope(key)` (para que cada resolvedor mire o telefone escolhido). Cada fluxo escreve em um callable `log(line)` que a GUI conecta ao seu console. O cancelamento tem escopo por dispositivo (`flow.request_cancel(key)`; a difusão sem chave para tudo), verificado no topo de cada `_run`.

Para adicionar um fluxo: adicione uma linha `flow!("my_op", "My op", "Job Name", "MODE")` em `src/flows.rs`. Python auto-descobre via `bridge.flow_list()` e o drill-down job/mode/método da GUI o pega automaticamente. A CLI Rust `flow-run` o executa; os resolvedores devem aceitar um serial alvo / `vid:pid@bus:addr` (ver `src/device.rs`).