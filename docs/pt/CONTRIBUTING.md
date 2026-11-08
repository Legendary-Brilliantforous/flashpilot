Language switcher: [English](../../CONTRIBUTING.md) · [Français](../../fr/CONTRIBUTING.md) · [Español](../../es/CONTRIBUTING.md) · [Deutsch](../../de/CONTRIBUTING.md) · [简体中文](../../zh/CONTRIBUTING.md) · [Русский](../../ru/CONTRIBUTING.md) · **Português** · [日本語](../../ja/CONTRIBUTING.md) · [العربية](../../ar/CONTRIBUTING.md) · [हिन्दी](../../hi/CONTRIBUTING.md) · [Türkçe](../../tr/CONTRIBUTING.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

# 🧑‍💻 Contribuir para o FlashPilot

Obrigado por passar por aqui! Este projeto é construído sobre protocolos de
engenharia reversa e conhecimento aberto — cada contribuição o torna mais capaz,
mais confiável e mais próximo das suites Windows pagas. Você não precisa ser
expert em flasheo para ajudar.

## Índice

- [Código de conduta](#código-de-conduta)
- [Como o projeto é organizado](#como-o-projeto-é-organizado)
- [Formas de contribuir](#formas-de-contribuir)
- [Primeiros passos](#primeiros-passos)
- [Visão da arquitetura (10 minutos)](#visão-da-arquitetura-10-minutos)
- [Como adicionar um novo fluxo](#como-adicionar-um-novo-fluxo)
- [Adicionando um novo protocolo USB / comando Rust](#adicionando-um-novo-protocolo-usb--comando-rust)
- [Diretrizes de GUI](#diretrizes-de-gui)
- [Testes](#testes)
- [Checklist de pull request](#checklist-de-pull-request)
- [Roadmap e ideias](#roadmap-e-ideias)

---

## Código de conduta

Ver [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Seja respeitoso, assuma boa
intenção e mantenha as discussões técnicas e úteis. Este é um projeto que virou
sério a partir de algo de amador: damos boas-vindas a iniciantes e veteranos
igualmente. Assédio, gatekeeping ou commit de segredos/credenciais não serão
tolerados. Cargas (payloads) de protocolo são bem-vindas quando sua procedência
e licença estiverem documentadas.

---

## Como o projeto é organizado

Duas metades trabalham juntas:

| Camada | Local | Linguagem | Papel |
|---|---|---|---|
| **Núcleo / motor de protocolo** | `src/` | Rust | USB bruto, todos os protocolos de bootloader (`flashpilot-bridge` CLI) |
| **Registro de fluxos** | `src/flows.rs` | Rust | Linhas de macro `flow!` → `FLOWS` / `JOBS` / `MODES` (fonte da verdade) |
| **Shim de fluxo** | `python/core/core.py` | Python | Wrappers `_RustFlow` + fallback `JOBS`; delega a `bridge flow-run` |
| **Identidade do dispositivo** | `python/core/devices.py` | Python | Chaves estáveis, lista de dispositivos, re-resolução do alvo, escopo de thread |
| **Superfície FRP** | `python/core/frp.py` | Python | Reexportação apenas FRP (nome == responsabilidade) |
| **Estúdio GUI** | `python/gui/` | Python / PyQt6 | Workbench (`qt_app.py`), páginas (`devices.py`), tema, animações |

O Python nunca fala diretamente com USB. Ele invoca
`target/release/flashpilot-bridge` (o binário Rust), que retorna JSON/texto. A
GUI apenas escuta sinais das threads worker — nunca toque widgets a partir de
uma thread de segundo plano.

---

## Formas de contribuir

Sem código? Sem problemas:

- **Testes em hardware real** — reporte em quais dispositivos/firmwares um fluxo
  funciona.
- **Documentação** — melhore o README, este arquivo e descrições de fluxos.
- **Firmware / DA / arquivos combo** — apontadores para binários legítimos de
  livre disponibilidade.
- **Traduções e temas** — a GUI é tematizável; novos packs de acento são vitórias
  fáceis.
- **UI/UX** — mockups, passes de acessibilidade, design de atalhos de teclado.
- **Relatórios de bug** — use a [plantilha de reporte de bug](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=bug&template=bug_report.yml):
  passos, logs, saída de `flashpilot-bridge detect`, modelo + versão de firmware.
- **Código** — ver abaixo.

> 💡 **Novo por aqui?** Procure a etiqueta **`good first issue`** no tracker de
> issues — tarefas selecionadas, amigáveis a iniciantes, totalmente escopadas e
> seguras de pegar.

---

## Primeiros passos

```bash
# 1. Build the Rust bridge
cargo build --release

# 2. (Recommended) USB udev rules
sudo bash root/setup-usb.sh

# 3. Create the venv + run
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m python.main
```

O aplicativo abre uma janela nativa PyQt6. Use a página **Settings → Tools** para
ver se o bridge está compilado e o ADB detectado.

---

## Migrando de um checkout mais antigo (leia primeiro se estiver voltando)

Uma nota sobre a troca de nomes, claramente: entre a 1.2.0 e agora renomeamos o
módulo central, dividimos um god-file em módulos focados, renomeamos cada job e
adicionamos uma dúzia de arquivos. Isso quebra imports antigos, referências antigas
na documentação e quaisquer scripts fora da árvore escritos contra
`python.core.frp`. Desculpe por isso — foi a única forma de matar o god-file,
corrigir a confusão de PIDs MTK e tornar possível o suporte multi-dispositivo
sem empilhar hacks por cima. Esta seção é o guia completo de adaptação; nada aqui
é deprecado gradualmente, tudo mudou de uma vez, então percorra a tabela uma vez
e você estará atualizado.

### Caminhos renomeados

| Antes | Depois | O que mudar |
|---|---|---|
| `python/core/frp.py` (god file: registro + todo fluxo) | `python/core/core.py` | `from python.core import frp` → `from python.core import core`; `frp.FLOWS` → `core.FLOWS`, etc. |
| *(nada — FRP vivia dentro do god file)* | `python/core/frp.py` (novo, só FRP) | Se você só precisa de fluxos FRP, importe daqui em vez de `core`. |
| *(nada)* | `python/core/devices.py` (novo) | Identidade de dispositivo, `list_devices()`, `resolve_usb_target()`, `device_scope()`. |
| *(nada)* | `python/core/imei.py` (novo) | Fluxos de reparo/mudança de IMEI MTK/SPD. |
| *(nada)* | `python/core/experimental.py` (novo) | Portões EXPERIMENTAL + log de auditoria. |
| *(nada)* | `python/core/{knox,qcn,emmc,pac,apple,health,compat,device_info,fastboot,integrity,safety,spd_adb}.py` (novo) | Lógica por domínio, antes inline no god file ou inexistente. |
| *(nada)* | `tests/test_devices.py` (novo) | Testes multi-dispositivo + cancel-scope. |
| *(nada)* | `CHANGELOG.md` (novo) | Mudanças agrupadas por release; verifique-o primeiro. |

### A migração para Rust (arquitetura atual — a tabela acima é história)

Após a divisão acima, os motores migraram para Rust e o lado Python se
adelgaçou. Verdade atual:

- **Os fluxos vivem em `src/flows.rs`** (registro + `flow-run <key> [target]
  [--code/--partition/--file/--dpc ...]`). `flow-list` é a fonte da verdade —
  verifique uma chave de fluxo ali antes de citá-la na documentação.
- **`python/core/core.py` é um shim fino** (~450 linhas): `_RustFlow`
  delega a `bridge flow-run`, o registro vem do bridge com fallback `JOBS`. Os
  16 módulos de motor por domínio (`knox`, `qcn`, `emmc`, `imei`, `apple`,
  `ofp`, `pac`, `health`, `flashing`, `spd_adb`, `integrity`, `fastboot`,
  `usb_watch`, `compat`, `updater`, `safety`) foram removidos — não os
  referencie em docs nova.
- **A GUI permanece em Python** (`python/gui/qt_app.py` + `devices.py`); ela
  consome o registro Rust via `bridge.flow_list()`.
- Os antigos arquivos de teste para fluxos Python removidos foram deletados com
  eles; a cobertura são as suites por área + cargo `flows::tests`.

### Mudanças de API a que você deve se adaptar

- **Resolvers recebem `key=None`.** `find_samsung()`, `_download_mode_device()`,
  `_wait_for_adb()`, `_wait_mtk_brom_target()`, `_mtk_retry()`,
  `wait_clean_download_mode()`, `pit_contract()` todos aceitam uma chave de
  dispositivo estável opcional (escopo thread ambient por padrão — antigos call
  sites continuam funcionando, comportamento first-match preservado quando nenhuma
  chave é definida).
- **Cancelamento é por dispositivo.** `request_cancel()` / `clear_cancel()` /
  `cancel_requested()` em `flow.py` e `bridge.py` aceitam `key=None`. A chamada
  sem chave de `request_cancel()` ainda difunde (STOP global); as checagens sem
  chave consultam o escopo ambient, depois o bus de difusão.
- **Run-guard é por dispositivo.** `_flow_start(label, destructive, key=None)` /
  `_flow_end(key=None)` / `_flow_busy_msg(key=None)` em `qt_app.py`; as antigas
  globais `_FLOW_LOCK` / `_FLOW_LABEL` foram embora (substituídas por dicts por
  chave + `_flows_running()`).
- **Runners recebem `device_key=None`.** `_run_ops_flow()` / `_run_job_flow()`
  mostram o seletor de dispositivo quando vários telefones coincidem, depois
  definem `ctx["device_key"]` (+ `ctx["target"]` onde resolúvel) e executam
  dentro de `devices.device_scope()`.
- **Novo modo de transporte `"SPD"`** em `MODES` (VID `0x1782`); novos jobs
  `Knox / Warranty`, `QCN / Modem`, `IMEI Repair / Change`, `eMMC / UFS`.
- **Nomes de job são verb-first** (`Remove FRP`, não `FRP bypass`; ver README).
  Se sua branch ainda referencia nomes antigos, renomeie à tabela na
  “Visão da arquitetura”.
- **PIDs MTK são convenção mtkclient**: `0e8d:0003` = BROM,
  `0e8d:2000` = preloader. Vários comentários/logs antigos os tinham trocados;
  confie em `mtk.pid_stage()` / Rust `boot_stage_for()`, não em strings
  antigos.

### Se você tiver um PR aberto de antes da reestruturação

1. Rebase sobre a nova árvore; espere conflitos confinados a imports e aos
   blocos `JOBS`/`FLOWS`.
2. Rode a checklist abaixo — `pytest` capturará imediatamente referências a
   chaves/nomes obsoletos (testes de registro asseguram que cada método `JOBS`
   resolve).
3. Se seu PR tocou `flows/` (o experimento abandonado de pacote dividido): esse
   diretório se foi, porte sua mudança para `core.py` + o módulo de domínio.

---

## Visão da arquitetura (10 minutos)

1. **`src/main.rs`** — uma CLI com 80+ comandos. Cada braço `match` é um
   comando (`detect`, `mtk-flash`, `mtk-crash-brom`, `qcom-firehose`,
   `spd-format`, `odin-pit`, ...).
2. **`src/usb.rs`** — encontra dispositivos por VID/PID, fornece endpoints (mais
   `port_numbers` estáveis para endereçamento a prova de re-enumeração).
3. **`src/odin.rs`** — modo download Samsung (o protocolo Odin 3 de engenharia
   reversa, derivado do Heimdall). Lê/escreve/flasha PIT, flashea partições
   (incl. o multiplexador de sessão persistente `odin-agent`).
4. **`src/mtk*.rs`** — MediaTek BROM (`0e8d:0003`) → preloader (`0e8d:2000`) →
   handshake do Download Agent, parse de scatter, trabalho de partição GPT, chaves
   SLA, exploits BROM, crash-to-BROM. ⚠️ A convenção de PID é estilo
   mtkclient: `0003`=BROM, `2000`=preloader — não os inverta.
5. **`src/qualcomm/`** — handshake Sahara (EDL) e sessões Firehose.
6. **`src/spd.rs`** — Spreadtrum/UNISOC BSL: download de FDL, format, FRP,
   backup, extração/packing de PAC.
7. **`src/flows.rs`** — o **coração da app**. As linhas `flow!(key, label, job, mode)`
   constroem o registro `FLOWS` / `JOBS` / `MODES` (~280 linhas, 13 jobs, 9
   modos incl. `SPD`). `python/core/core.py` só o espelha para busca de GUI.
8. **`python/core/devices.py`** — identidade multi-dispositivo. Chaves estáveis
   (`adb:<serial>` → `usb:<port-path>` → fallback volátil), `list_devices()`,
   `resolve_usb_target()`, e o thread-local `device_scope()` que carrega o
   telefone escolhido dentro dos resolvers.
9. **`python/gui/qt_app.py`** — constrói todas as seções (Samsung / MTK / QC /
   SPD / Bateria / Rede / Ajustes) e workbenches de sub-abas, mais o seletor por
   operação por dispositivo e o run-guard por dispositivo.

### Fluxo de dados

```
click button
  → _choose_device(job, mode)          # silent if 0-1 phones match, else picker
  → _run_ops_flow(job, mode, method, name, device_key)
  → per-device _flow_start(key) + device_scope(key) + ctx["device_key"]
  → core.flow_for(...) -> Flow (list of Steps)
  → each Step runs in a worker thread, calling bridge._run([...])
  → bridge spawns target/release/flashpilot-bridge ...
  → Rust does USB I/O, prints JSON/text
  → Python parses + emits _ui.line() signals (tagged [device-key])
  → GUI updates console / status / progress safely
```

---

## Como adicionar um novo fluxo

A funcionalidade mais simples que você pode entregar. Abra `src/flows.rs` e adicione
uma linha:

```rust
flow!("my_method", "My method", "Remove FRP", "ADB"),
```

A chave é snake_case curta (sem prefixo `flow_`). O Python a auto-descobre via
`bridge.flow_list()` e o drill-down job/mode/método da GUI a pega
automaticamente; a execução roda por `flashpilot-bridge flow-run my_method`.

Depois (só se precisar de trabalho de protocolo de baixo nível novo), adicione o
comando do bridge em `src/<concern>.rs` + `src/main.rs`. O cabeamento job/mode
já está na linha do fluxo.

Esse é todo — o fluxo aparece no dropdown/sub-aba da GUI automaticamente e também
é alcançável pela CLI. **Esta é a área de maior valor / entrada mais fácil.**

> Use `log(...)` dentro dos passos para saída de console, `ctx` para o estado
> que você quer levar entre passos e `bridge._run(...)` para o que bate no
> binário Rust. Mantenha os passos cooperativos com `cancel_requested()` onde
> convier para Stop funcionar (o cancelamento é por dispositivo — ver abaixo).

### Regras que todo fluxo deve seguir

- **Nunca pegue "o" dispositivo.** Aceite `key=None` (escopo thread ambient) em
  qualquer resolver que você adicionar, e filtre por ele — ver
  `devices.device_key()`, `devices.match_key()`, `devices.device_scope()`. A GUI
  define o escopo por operação; chamadores sem interface também podem.
- **Nomes de job são verb-first** (`Remove FRP`, `Flash Firmware`,
  `Unlock Carrier`). **Chaves de fluxo são snake_case curtas** (`adb_frp`, não
  `flow_adb_frp`); o único alias histórico (`fastboot_read`) foi removido — não
  adicione alias.
- **A convenção de PIDs MTK é estilo mtkclient**: `0e8d:0003` = BROM
  (retido), `0e8d:2000` = preloader. Rust, Python, etiquetas da GUI e docs
  devem todos concordar.
- **Escritas EXPERIMENTAL** (Knox/IMEI/QCN/eMMC) passam por
  `experimental.check_gate_strict()` com um ack por execução — um ack armazenado
  nunca deve auto-aprovar. Gateie-as na GUI via `_EXPERIMENTAL_FLOW_MAP` + o
  padrão colapsável âmbar na página do chip proprietário (nunca uma página LAB
  global).
- **Alvos do bridge são voláteis** (`vid:pid@bus:addr` muda na
  re-enumeração). Re-resolva a partir da chave estável antes de abrir sessões
  (`devices.resolve_usb_target()`); pine odin4 com `-d /dev/bus/usb/BBB/AAA`.

---

## Adicionando um novo protocolo USB / comando Rust

1. Adicione seu módulo sob `src/` (p. ex. `src/myproto.rs`).
2. Adicione `mod myproto;` em `src/main.rs` e um novo braço `match` + linha de
   uso.
3. Retorne `Result<T>` via `crate::error` e use `serde_json` para saída
   estruturada.
4. Exponha a partir do Python em `python/core/bridge.py` como wrapper em torno
   de `_run([...])`.
5. Construa um `Flow` em `core.py` que o chame (respeite as regras de fluxo
   acima).
6. Adicione um teste se puder — os testes unitários vivem em `src/*.rs`
   (`#[test]`) e `tests/`.

**Higiene de protocolo:** cite sua fonte (fóruns, write-ups clean-room, outros
projetos OSS) na docstring do módulo. Não incluímos blobs proprietários — apenas
a implementação do protocolo.

---

## Diretrizes de GUI

- **PyQt6 apenas.** Sem outros bindings Qt nem deps de UI extras (ver
  `requirements.txt`).
- Corresponda ao linguagem visual existente: `_btn_ghost()`, `_btn_primary()`,
  `_card_qss()`, `SectionTitle`, cores de tema `C[...]`, `FlowLayout` para
  grades de botões.
- **Tokens de tema, não acento cru:** preenchimentos podem usar
  `C['accent'/'grad_a'/'grad_b']`, mas anéis de foco, bordas de abas
  selecionadas e checkboxes DEVEM usar os tokens neutros `C['focus_ring']` /
  `C['sel_border']` — caso contrário temas de acento vermelho (Crimson, Sunset)
  vazam vermelho nos estados de foco. Nunca faça hardcode de hex para chrome.
- **Regra de threads:** trabalho de segundo plano vai em `threading.Thread`;
  atualizações de GUI ocorrem apenas via sinais `self._ui.*` (`.line`, `.status`,
  `.toast`, `.ui`, `.progress`).
- **Animações:** `Motion.shake()` / `Motion.rubber()` são mutuamente exclusivas
  por widget (guardadas por `_anim_lock`) — nunca rode as duas concorrentemente;
  call sites devem serializar via `QTimer.singleShot`. Nenhuma deve deixar
  `setFixedSize`, bordas restilizadas ou layouts desabilitados por trás;
  `cleanup()` restaura tudo.
- Mantenha linhas de UI longevas roláveis — as páginas de chip envolvem o
  conteúdo em um `QScrollArea` para que nunca esmaguem em janelas pequenas.
- Novas sub-abas reutilizam `SamsungSubTabs` + um `QStackedWidget` (ver
  `_build_chip_ops_section`).
- Botões de ação são `NoFocus` (sem anel de foco persistente); pilulas de
  abas checkable mantêm o estilo `checked` para o estado ativo.

---

## Testes

```bash
cargo test                      # Rust unit tests (incl. MTK stage mapping, SLA, PIT)
.venv/bin/python -m pytest tests/   # Python suite (currently 173 passed, 4 skipped)
```

Estrutura da suite de testes:

- `tests/test_frp_flow.py` — execução de `Flow`/`Step` + cancelamento
  cooperativo + run-guard por dispositivo.
- `tests/test_mtk.py` — lógica MediaTek (scatter, DA, helpers de boot-stage,
  espera/crash-retry de BROM).
- `tests/test_devices.py` — chaves estáveis de dispositivo, filtragem de
  telefones, re-resolução de alvo, cancelamento com escopo.
- `tests/test_carrier_lock.py` — veredito de bloqueio SIM + gating de patch MTK +
  discovery de DA.
- `tests/test_odin_safety.py` — verificação tar.md5, portões BL, negociação de
  flags do odin4.
- `tests/test_pit.py` — parse de PIT Samsung.
- `tests/test_bridge_io.py`, `tests/test_fus.py` — bridge I/O + downloader de
  firmware Samsung.

Se você adicionar lógica Rust, adicione módulos `#[test]` no mesmo arquivo. Se
adicionar fluxos, adicione um pytest que execute o fluxo com contexto
fake/offline quando possível. Novos resolvers devem aceitar `key=None`; novos
testes devem cobrir filtragem multi-dispositivo (ver `test_devices.py`) em vez
de assumir um único telefone.

---

## Checklist de pull request

- [ ] `cargo build --release` passa.
- [ ] `cargo test` passa (ou anote por que não executável).
- [ ] `.venv/bin/python -m pytest tests/` passa.
- [ ] Novo fluxo: cabeado em `JOBS` (job + mode) para ser alcançável na GUI.
- [ ] Novo resolver: aceita `key=None` (escopo ambient) e é coberto por teste
  multi-dispositivo.
- [ ] Novo comando Rust: adicionado ao texto de uso de `main.rs` + wrapper em
  `bridge.py`.
- [ ] Mudanças GUI: cores tematizadas (tokens neutros de foco!), atualizações
  baseadas em sinal, layouts seguros ante scroll.
- [ ] Nenhum segredo/binário/dado identificador de dispositivo adicionado ao
  repositório.
- [ ] README matriz de features atualizado se você adicionou uma capacidade.

Mantenha PRs focados. O ideal é uma feature ou fix por PR; referencie o número
do issue.

---

## Política de suporte de plataformas (leia antes de fazer um port)

**Linux é a única plataforma suportada.** Desenvolvimento, testes de hardware e
releases visam Linux. Issues de Windows/macOS serão fechados como não suportados
— a menos que cheguem como código, como segue.

**Por quê:** `odin4` é só Linux; USB no Windows precisa de drivers por modo
(Zadig / QDLoader / Samsung) que não podem ser depurados remotamente; macOS
precisa de assinatura/notarização por demanda insignificante. Ver a seção
“Platform support” do README para o raciocínio completo e o convite aberto para
discuti-lo.

**Como contribuir um port mesmo assim (a forma aceita):**

1. NÃO salpique checagens `sys.platform` nos fluxos ou na GUI.
2. Adicione `python/core/platform.py` com funções de backend —
   `open_file_manager()`, `detach_kernel_drivers(target)`,
   `usb_device_path(bus, addr)`, `needs_udev_setup()`,
   `kernel_module_loaded(name)` — Linux implementado, os demais lançando
   `NotImplementedError` com uma mensagem útil.
3. Migre os call sites só-Linux (`xdg-open`, `rmmod cdc_acm`,
   `/dev/bus/usb`, `lsmod`, docs de udev) para ele, um PR por grupo de call
   site.
4. Um PR de backend Windows/macOS deve incluir: a implementação de backend,
   atualizações de docs e evidência de CI ou teste manual verificado por
   mantenedor. A equipe central não possui hardware de teste não-Linux — PRs de
   port vivem ou morrem pela capacidade de seu autor de prová-los.

**PySide6 vs PyQt6:** a migração para PySide6 (LGPL, compatível com MIT — PyQt6
é GPLv3) é desejada mas está bloqueada na cobertura de smoke-test de GUI. Se
você a tomar: converta `pyqtSignal→Signal`, `pyqtProperty→Property`,
`PyQt6.sip→shiboken6` mecanicamente, estenda os smoke tests de janela/seletor/
guardia off-screen em `tests/`, e mantenha o comportamento pixel-idêntico.
Discuta primeiro nas Discussions.

## Roadmap e ideias

Adoraríamos que contribuidores liderassem qualquer um destes:

- **Ports e empacotamento:** Flatpak / AppImage / AUR, matriz CI (distros
  Linux), fluxo de release `pip`/`cargo`.
- **MediaTek:** mais variantes de DA, casos de borda de scatter, dumps de
  backup eMMC/UFS, novas entradas em `CHIP_NAMES` (com fonte citada — nunca
  adivinze códigos hex).
- **Qualcomm:** casos de borda rawprogram/patch XML, combos fh-loader, mais PIDs
  de chips.
- **Samsung:** payloads HID adicionais de modo download por SoC, polimento de UX
  multi-partição Odin.
- **Multi-dispositivo:** abas de console por dispositivo/progresso, granularidade
  de STOP por dispositivo (STOP atualmente difunde), correlação `port_numbers`
  para hubs exóticos.
- **Novas seções:** FRP TEE/teclado, perfis carrier (de-bloating), utilitários
  só-EDL.
- **Comunidade:** traduções, uma wiki de compatibilidade de dispositivos, um
  catálogo reproduzível de arquivos de firmware.
- **Segurança:** modo dry-run, backup pré-flash automático, docs de recuperação
  de brick.

---

## Contribuidores

Todos que ajudam — código, docs, relatórios de dispositivo ou um combo testado
— são listados aqui e celebrados. Abra um PR se adicionando (alfabético por
username, uma linha de link):

```md
- [@your-github](https://github.com/your-github) — what you did
```

Os primeiros contribuidores deste projeto o tornaram real. Seja o próximo.

---

**Dúvidas?** Abra uma discussion/issue. Obrigado por ajudar a avançar o
software livre e aberto de flasheo no Linux. 🚀