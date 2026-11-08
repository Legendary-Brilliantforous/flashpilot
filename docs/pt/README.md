# 🔧 FlashPilot

Language switcher: [English](../../README.md) · [Français](../fr/README.md) · [Español](../es/README.md) · [Deutsch](../de/README.md) · [简体中文](../zh/README.md) · [Русский](../ru/README.md) · **Português** · [日本語](../ja/README.md) · [العربية](../ar/README.md) · [हिन्दी](../hi/README.md) · [Türkçe](../tr/README.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

> **Um workbench de código aberto para flash e reparo de firmware Samsung no Linux — uma alternativa ao Odin / Heimdall para flashear telefones Galaxy (modo Download/Odin), dispositivos MediaTek (BROM/DA), Qualcomm (EDL) e Spreadtrum/UNISOC.**

**Palavras-chave de busca:** Samsung flashing tool · Odin alternative · Android firmware flashing Linux · Heimdall GUI · Galaxy phone repair · MTK BROM flash · Qualcomm EDL · FRP unlock · UNISOC flashing · device firmware tool · mobile repair · Android bootloader · USB flashing · Linux flashing suite · proprietary tool alternative

[![Rust](https://img.shields.io/badge/Rust-1.70+-orange?logo=rust&logoColor=white)](https://www.rust-lang.org)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-41cd52)](https://www.riverbankcomputing.com/software/pyqt/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](../../LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![CI](https://github.com/Legendary-Brilliantforous/flashpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/Legendary-Brilliantforous/flashpilot/actions)
[![Good First Issues](https://img.shields.io/github/issues/Legendary-Brilliantforous/flashpilot/good%20first%20issue)](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
[![Contributors](https://img.shields.io/github/contributors/Legendary-Brilliantforous/flashpilot)](https://github.com/Legendary-Brilliantforous/flashpilot/graphs/contributors)

**O que é isso?** O equivalente nativo para Linux das suites de flash para Windows pagas — uma única ferramenta unificada que fala diretamente com o bootloader de dispositivos **Samsung, MediaTek, Qualcomm e Spreadtrum/UNISOC**. Protocolos de engenharia reversa + desempenho nativo em Rust + uma bela GUI PyQt6 = a alternativa open source ao Odin, Heimdall e às caras ferramentas comerciais.

---

## ✨ Por que este projeto importa

O mundo do reparo Android funciona com ferramentas comerciais fechadas e só para Windows. Seus protocolos são de engenharia reversa por uma pequena comunidade de entusiastas — e a maior parte desse conhecimento está trancada dentro de suites pagas ou dispersa em fóruns de forma incompleta.

**Este projeto é a nossa resposta.** Transforma esses protocolos de engenharia reversa em uma base de código limpa, auditável, sob licença MIT, que qualquer um pode ler, executar, estender — e distribuir como sua própria suite de flash.

| Ferramenta comercial | Só Windows, código fechado | Este projeto |
|---|---|---|
| Odin / Smart Switch | Windows, só GUI | Protocolo Odin open source (Rust, nativo) + ferramentas PIT |
| Ferramentas de flash MTK | Windows, DA fechado | Flash e backup MTK BROM/DA (scatter + GPT) |
| Ferramentas EDL Qualcomm | Windows | Implementação do protocolo Sahara + Firehose |
| Ferramentas SPD/UNISOC | Windows | Implementação BSL em clean-room |
| Ferramentas FRP / bloqueio | Pagas, mercado cinza | Fluxos transparentes ADB + modo download, desbloqueio MDM |

---

## 🚀 Destaques — 1.2.1 Stable (0 avisos)

- **9 modos de transporte** — ADB, MTP, modo Download Samsung, BROM Samsung, MTK, MTK BROM, Fastboot, Qualcomm EDL, SPD.
- **13 categorias de job** — Flash Firmware, Remove FRP, Remove Screen Lock, Remove MDM, Unlock Carrier, Read Device Info, Detect Devices, Reboot, Repair Settings, mais por chip EXPERIMENTAL: Knox / Warranty (Samsung), QCN / Modem (Qualcomm), IMEI Repair / Change (MTK/SPD/Qualcomm), eMMC / UFS.
- **Multi-dispositivo** — conecte vários telefones: a barra de conexão lista cada um, toda operação pergunta a qual telefone se aplica (ou executa silenciosamente quando apenas um corresponde), e telefones diferentes podem rodar operações em paralelo (uma op por dispositivo, STOP transmite para todos).
- **Núcleo Rust (`flashpilot-bridge`, ~9.3k LOC) — 0 avisos de `cargo check`** — USB bruto com *libusb incluído* (sem dependências de sistema), implementações reais de protocolo (+ 18 caminhos mortos ligados, trim ltcg -80KB).
  - **Samsung**: protocolo de sessão Odin de engenharia reversa (baseado no Heimdall), payloads HID em modo download, leitura/escrita/flash de PIT — contexto `AT` retido, chunking `EndpointConfig`.
  - **MediaTek**: handshake BROM / preloader / DA, scatter & GPT, exploits BROM, chaves SLA — porcentagem real do `ProgressReporter`.
  - **Qualcomm**: `ProtocolError` Sahara + `QcomDeviceInfo` Firehose ligados via limites de tempo `Duration`.
  - **SPD/UNISOC**: BSL em clean-room — todos os `BSL_CMD/REP`, `iface`, `flush/read_flash/chip_uid/power_off` ligados.
  - Além de **MTP**, comandos **AT** e toda a tubulação **ADB**.
- **Uma GUI de nível estúdio** — janela frameless translucent com cards de raio, 10 temas de acento, cena animada de cabo/status, console ao vivo.
  - **Ícones de marca e fundos de botão distintos** — ícones de marca nítidos (Samsung Ⓢ, Apple 🍎 vermelho, Motorola Ⓜ, LG Ⓛ, etc.) e cores de fundo adaptadas em cada botão OEM da barra superior de chips.
  - **Visualizações horizontais para Motorola e Apple** — os painéis de ações de modelo usam por padrão disposições limpas em abas horizontais.
  - **Micro-interações e glassmorphism** — animações de fade-in de troca de página de 160 ms suaves, tipografia monoespaçada para badges de metadados (`Consolas`, `Monaco`) e bordas de cards glassmórficos aprimoradas.
  - **Grandes diálogos centralizados (620px, arrastáveis, ✕)** — gate beta + stable `UPDATE/AHEAD/PATCH` + confirmações de flash/FRP, cores de chip `MTK âmbar` `QCOM vermelho` `SPD violeta` `SAMSUNG azul`, texto de alto contraste.
  - **Colapsáveis EXPERIMENTAL por chip** — Knox (Samsung), QCN/IMEI (Qualcomm), IMEI (MTK/SPD): banner âmbar, checkbox de propriedade em toda execução, `I UNDERSTAND` de confirmação por digitação para mudança de IMEI, com log de auditoria.
  - **⏹ STOP** na barra de título para todas as operações em andamento; bloqueios por dispositivo permitem que outros telefones continuem funcionando.

---

## 📸 Capturas de tela

| Operações Samsung | Workbench MediaTek | Reparo de bateria | Download SPD |
|---|---|---|---|
| ![Samsung](../../docs/samsung.png) | ![MediaTek](../../docs/mtk.png) | ![Bateria](../../docs/battery.png) | ![SPD](../../docs/spd.png) |

---

## 🧩 Matriz de recursos

| Recurso | Samsung | MediaTek | Qualcomm | SPD/UNISOC | Qualquer ADB |
|---|---|---|---|---|---|
| Detectar / info | ✅ | ✅ (+ crash preloader→BROM) | ✅ (Sahara) | ✅ | ✅ |
| Flash de firmware | ✅ (Odin, Rust nativo) | ✅ (scatter + GPT) | ✅ (Firehose) | ✅ (FDL/regiões) | — |
| Backup de partições | ✅ (EFS) | ✅ | ✅ | ✅ | — |
| Bypass FRP | ✅ (ADB + download) | ✅ | ✅ (EDL) | ✅ | ✅ |
| Remoção de bloqueio de tela | ✅ | ✅ | ✅ (EDL) | — | ✅ |
| Desbloqueio MDM | ✅ (ADB, QR, recovery) | — | — | — | — |
| Knox garantia/bypass (EXPERIMENTAL) | ✅ | — | — | — | — |
| Backup/restauração QCN + reparo/mudança IMEI (EXPERIMENTAL) | — | ✅ (NVRAM) | ✅ (NV 550/682) | ✅ (BSL NV) | — |
| Ferramentas de partição | ✅ (PIT) | ✅ (GPT) | ✅ | ✅ (extract/pack PAC) | — |
| Exploits de baixo nível | ✅ (HID/BROM) | ✅ (exploit BROM, SLA) | ✅ (Sahara) | ✅ (BSL) | — |
| Reparo de bateria / rede | — | — | — | — | ✅ |

> 💡 As seções **Bateria** e **Rede** funcionam em *qualquer* dispositivo Android com depuração USB ativada — não é necessário hardware do fabricante.

---

## 🖥️ A GUI

Uma janela frameless, translucent, com cards de raio, com um **banner de conexão** ao vivo (cena computador → cabo → telefone com pulso de dados animado) acima de um **rail de navegação** à esquerda e um **painel de console/log** à direita.

- **Barra de conexão** — lista ao vivo de dispositivos (uma linha por telefone: modelo · série · transportes); clique em uma linha para inspecionar. Botões de operação perguntam qual telefone quando vários correspondem.
- **Samsung** — sub-abas do hub Samsung: `ODIN FLASH · UNLOCK · ADVANCED FLASH · INFO & TOOLS`, além de slots de firmware (AP/BL/CP/CSC/USERDATA), utilitários Odin e um colapsável `KNOX — EXPERIMENTAL`.
- **MediaTek / Qualcomm / SPD** — workbenches dedicados com ferramentas nativas de baixo nível (scatter/DA + crash-to-BROM, programmer/XML + QCN/IMEI, binários FDL + endereços base + IMEI), cada um com seu próprio colapsável `— EXPERIMENTAL`.
- **Bateria** — saúde do fuel-gauge em %, temp/voltagem/corrente, principais consumidores; reparo em um clique.
- **Rede** — estado SIM, flags de dados/Wi-Fi, modo DNS; reset de rádio e re-registro.
- **Configurações** — intervalo de auto-scan, caminhos padrão, limpeza automática do console, 10 temas de acento, animações (toggles shake/rubber/cable/bubble), brilho da janela, status do motor e `cargo build` integrado.

**Atalhos:** `F5` rescanear · `Ctrl+Enter` executar · `Ctrl+L` limpar console · `Ctrl+S` salvar log · `Ctrl+F` buscar.

---

## 📦 Início rápido

**Requisitos:** toolchain Rust, Python 3.10+, um desktop Linux. É só isso — libusb já está incluído.

```bash
# 1. Compila o bridge Rust (a primeira compilação compila libusb a partir da fonte)
cargo build --release

# 2. (Recomendado) instale as regras udev USB para que telefones não precisem de sudo
sudo bash root/setup-usb.sh

# 3. Ambiente Python
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. Iniciar
.venv/bin/python -m python.main        # ou: python3 main.py
```

O flash em modo download da Samsung é nativo (protocolo Rust Odin) — nenhum binário proprietário odin4 é obtido, distribuído ou necessário. O firmware combo da Samsung deve ser obtido nas páginas de suporte oficiais da Samsung ou em arquivos de firmware de confiança.

---

## 🖥️ Suporte de plataformas — queremos sua opinião

**Linux é a plataforma suportada.** FlashPilot é deliberadamente *a resposta nativa para Linux às suites de flash apenas para Windows* — desenvolvimento, testes e releases miram o Linux, e isso não vai mudar.

**Windows / macOS não são suportados hoje**, por razões práticas:

- USB no Windows é um inferno de drivers por modo de telefone (Zadig/WinUSB, QDLoader, drivers da Samsung brigando entre si); a maioria dos relatos "telefone não detectado" seria impossível de depurar remotamente.
- macOS adiciona sobrecarga de assinatura/notarização para uma demanda quase nula em lojas de reparo.
- A pilha *é* portátil (Rust + rusb, Python, Qt), então é uma decisão de manutenção, não uma impossibilidade técnica.

**Mas esta é uma pergunta aberta, não um veredito.** Se você quer suporte para Windows/macOS — ou quer defender Linux-only para sempre — nos diga:

- 💬 Abra uma **[Discussion](https://github.com/Legendary-Brilliantforous/flashpilot/discussions)** com seu caso de uso (loja de reparo? laboratório? qual SO? quais telefones?).
- 🔧 O código fala mais alto: o plano é uma abstração `python/core/platform.py` (`open_file_manager()`, `detach_kernel_drivers()`, `usb_device_path()`, `needs_udev_setup()`) com Linux como único backend, para que ports sejam PRs aditivos em vez de forks. PRs nessa direção são bem-vindos já.
- 🎨 Relacionado: contribuidores propuseram **PySide6** (LGPL, compatível com a licença MIT deste projeto) em vez de PyQt6 (GPLv3). Dê sua opinião na mesma Discussion — a migração é mecânica mas precisa primeiro de cobertura de smoke-test de GUI.

Nenhuma decisão será tomada sem as vozes dos contribuidores. Venha e seja um deles.

### CLI / bridge

```bash
./target/release/flashpilot-bridge detect          # all USB + Samsung filter (JSON)
./target/release/flashpilot-bridge fastboot-devices  # USB devices with a fastboot interface (JSON)
./target/release/flashpilot-bridge fastboot-cmd 22b8:2e80@2:16 20000 getvar securestate  # one raw fastboot command
./target/release/flashpilot-bridge mtk-detect      # MediaTek BROM (0e8d:0003) / preloader (0e8d:2000) / DA
./target/release/flashpilot-bridge mtk-crash-brom <bus:addr>  # crash preloader into held BROM
./target/release/flashpilot-bridge qcom-detect     # Qualcomm EDL
./target/release/flashpilot-bridge spd-detect      # Spreadtrum/UNISOC (VID 0x1782)
./target/release/flashpilot-bridge odin-pit 04e8:xxxx@bus:addr  # read PIT
./target/release/flashpilot-bridge at-send <t> ATI # AT over CDC ACM
./target/release/flashpilot-bridge adb-devices     # adb devices -l as JSON
```

---

## 📁 Estrutura do repositório

```
flashpilot/
├── src/                      # Rust bridge (~13k LOC) — ALL flows live here
│   ├── main.rs               #   command-line entry (80+ commands) + flow-run dispatch
│   ├── flows.rs              #   THE registry: FLOWS / JOBS / MODES (flow! macro, ~280 rows)
│   ├── usb/                  #   USB enumeration / interfaces / filtering (mod.rs + filtering.rs)
│   ├── devices.rs            #   merged USB+ADB device rows
│   ├── sam_download.rs       #   Samsung Download/Odin protocol (odin-* commands)
│   ├── mtk.rs mtk_da.rs      #   MediaTek BROM/DA flashing
│   ├── mtk_exploit.rs        #   BROM exploits (bypass/kamakiri2/crash-to-BROM)
│   ├── mtk_sla.rs            #   MediaTek SLA key handling
│   ├── qualcomm/             #   Sahara + Firehose + GPT (EDL)
│   ├── spd.rs                #   Spreadtrum/UNISOC BSL protocol (+ PAC)
│   ├── pac.rs                #   SPD PAC extract/pack
│   ├── pit.rs                #   Samsung PIT parser
│   ├── mtp.rs at.rs adb.rs   #   MTP, AT command, ADB plumbing
│   ├── fastboot.rs           #   native fastboot transport
│   ├── moto_flash.rs         #   Motorola staged fastboot FRP
│   ├── apple.rs              #   Apple usbmuxd/lockdown
│   ├── hid.rs bulk.rs        #   HID + bulk helpers
│   ├── fwtar.rs sparse.rs    #   firmware tar + sparse handling
│   ├── imgtools.rs           #   boot/vbmeta surgery
│   ├── hostinfo.rs           #   host eMMC/UFS health
│   ├── sam_*.rs              #   Samsung helpers (errors/setup)
│   └── config.rs error.rs util.rs
├── main.py                   # app entry (venv-safe launcher → python.gui.qt_app)
├── python/
│   ├── core/
│   │   ├── core.py           #   thin shim: mirrors Rust FLOWS/JOBS/MODES via bridge.flow_list()
│   │   ├── frp.py            #   FRP-only re-export surface (name == responsibility)
│   │   ├── devices.py        #   multi-device identity: stable keys, list, resolve, transport mapping
│   │   ├── bridge.py         #   talks to the Rust binary (+ per-key cancel)
│   │   ├── flow.py           #   Flow/Step primitives + cancellation
│   │   ├── jobs.py           #   FlashJob lifecycle (isolated job layer)
│   │   ├── cancel.py         #   cooperative cancellation registry
│   │   ├── mtk.py            #   MTK PIDs/stages/chips (0003=BROM, 2000=preloader)
│   │   ├── mtp.py            #   Samsung MTP/AT (multi-sequence ADB enable)
│   │   ├── pit.py pitstore.py  # Samsung PIT parser + cache
│   │   ├── adb.py            #   ADB helpers
│   │   ├── device_info.py    #   live device identity
│   │   ├── actions.py        #   action helpers
│   │   ├── experimental.py   #   per-run ack gates + audit log
│   │   ├── fus.py            #   Samsung FUS helpers
│   │   └── (no flows/ dir)   #   flows live in src/flows.rs; Python only delegates
│   └── gui/
│       ├── qt_app.py         #   the PyQt6 studio (~12k LOC)
│       ├── devices.py        #   brand→model→action drill-down pages
│       ├── nav.py            #   nav rail + OEM chip bar
│       ├── theme.py          #   tokens (accent vs focus_ring/sel_border) + QSS
│       ├── animations.py     #   Motion (shake/rubber serialized, no stuck state)
│       ├── toast.py          #   toast notifications
│       └── supported_devices.json  #   brand/model/chip research table
├── operations/               # per-operation docs + research (frp/mdm/flashing/…)
├── docs/                     # screenshots (fresh) + logo
├── root/                     # udev rules + setup-usb.sh
├── scripts/                  # dump-connected.sh, validate_mtp_at.py
├── INDEX.md CHANGELOG.md     # engineering index + release changelog
└── tests/                    # pytest suite (flow, MTK, PIT, odin safety, devices…)
```

---

## 🧑‍💻 Contribuir

**Este projeto só melhora com você.** Queremos mantenedores, hackers de protocolo, designers de GUI, redatores e testadores.

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — tudo o que você precisa para começar.
- **Comece com a etiqueta [`good first issue`](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)** — tarefas selecionadas e acessíveis a iniciantes.
- Use os templates de **[relatório de bug](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=bug&template=bug_report.yml)** / **[solicitação de recurso](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=enhancement&template=feature_request.yml)**.
- **Tarefas para iniciantes** — cada linha de fluxo em `src/flows.rs` é uma oportunidade: adicione uma linha `flow!(...)`, ajuste uma sequência de comandos, conecte um novo combo de dispositivo. Python auto-descobre via `bridge.flow_list()`.
- **O framework de fluxos (`src/flows.rs`) é muito simples** — um método novo cabe em uma linha:

```rust
flow!("my_method", "My method", "Read Device Info", "ADB"),
```

Aparece automaticamente na GUI. Esse é todo o ciclo de contribuição: **escreva uma linha de fluxo, entregue um recurso.**
- **Regra multi-dispositivo** — nunca pegue "o" dispositivo; aceite `key=None` (escopo ambiental) e filtre por ele. Ver `python/core/devices.py` e `CONTRIBUTING.md`.
- **Regras de nomes** — jobs são verbo primeiro (`Remove FRP`, não `FRP bypass`); chaves de fluxo são snake_case curtas (sem prefixo `flow_` em `FLOWS`); PIDs MTK são `0003`=BROM / `2000`=preloader (convenção mtkclient — não os troque).

**Ideias em que adoraríamos ajuda:**
- Novos modelos de dispositivo / combos de firmware nas tabelas de fluxo.
- Variantes de DA MediaTek, peculiaridades de scatter/GPT.
- Casos de borda de rawprogram & patch XML da Qualcomm.
- Métodos FRP / remoção de bloqueio adicionais por versão do Android.
- Empacotamento (Flatpak, AppImage, AUR, `cargo` + `pip`), CI, testes unitários.
- Mais protocolos ODIN, ferramentas eMMC/UFS, utilitários adjacentes ao iCloud e EDL.
- Traduções, temas e acessibilidade.

---

## 🛡️ Segurança e legalidade

Esta ferramenta fala diretamente com bootloaders e pode apagar dados ou brickar um dispositivo se usada mal.

- Use apenas em **dispositivos que você possui ou está autorizado a reparar** (lojas de reparo atendendo telefones de clientes com consentimento).
- Sempre leia os avisos na tela e **faça backup das partições** antes de flashear.
- Bypassear FRP/MDM em um dispositivo que não seja seu pode ser **ilegal em sua jurisdição** — você é responsável por como usa este software.
- FlashPilot inclui os payloads de protocolo que as operações precisam (payloads MTK DA/BROM, programadores firehose da Qualcomm, FDL1/FDL2 da Unisoc, bootloaders da Samsung), da mesma forma que as suites comerciais de flash. As imagens de firmware para um telefone específico vêm sempre do usuário ou do fabricante.

---

## 📄 Licença

MIT — ver [LICENSE](../../LICENSE). As constantes do protocolo Odin são derivadas do projeto Heimdall (MIT), e a referência BSL do SPD vem de documentação de protocolo em clean-room (spd_cmd.h / docs Opus-Spreadtrum).

---

**Dê uma estrela ⭐ a este repo, abra uma issue, envie um PR — e vamos construir juntos a melhor suite de flash open source no Linux.**