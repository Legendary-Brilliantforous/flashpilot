# Plano intensivo de melhoria da UI do FlashPilot

Language switcher: [English](../../ui-improvement.md) · [Français](../fr/ui-improvement.md) · [Español](../es/ui-improvement.md) · [Deutsch](../de/ui-improvement.md) · [简体中文](../zh/ui-improvement.md) · [Русский](../ru/ui-improvement.md) · **Português** · [日本語](../ja/ui-improvement.md) · [العربية](../ar/ui-improvement.md) · [हिन्दी](../hi/ui-improvement.md) · [Türkçe](../tr/ui-improvement.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## Objetivo
Transformar a GUI PyQt6 de um monolito funcional em uma bancada polida, mantível e de alto desempenho, preservando todos os fluxos respaldados pelo Rust e o comportamento multi-dispositivo.

## Estado atual
- `python/gui/qt_app.py` (~15k LOC) é uma janela monolítica única.
- O sistema de tema (`theme.py`) é centralizado, mas o QSS é grande e duplicado em alguns pontos.
- Barra de conexão, rail de navegação, páginas por chip, console e configurações estão no mesmo arquivo.
- Já existe uma forte identidade visual (cards de vidro, 10 acentos, cena de cabo).

## Princípios
1. Nenhuma lógica de protocolo em Python; a UI apenas renderiza e chama o bridge.
2. Manter o Rust como fonte de verdade para fluxos/jobs/modos.
3. Melhorar a responsividade: mover trabalho pesado para fora da thread de UI, reduzir a criação de widgets.
4. Acessibilidade: navegação por teclado, anéis de foco, rótulos para leitor de tela.
5. Manutenibilidade: dividir `qt_app.py` em módulos por recurso.


## Fase 0 — Shell da janela, logotipo, splash (novo)
- Substituir o logotipo atual por uma marca vetorial/SVG profissional (variantes monocromática + acento, 16/32/64/128/256px + .ico/.icns).
- Tela de splash: marca animada, estágios de progresso (inicializar bridge Rust, escanear dispositivos, carregar tema), versão, sem flicker; fade-in/out 200ms.
- Renderização da janela: janela frameless translúcida com alfa amigável ao compositor, cantos arredondados, sombra de queda, escala ciente de DPI, memória de posicionamento em múltiplos monitores.
- Suavidade: habilitar Qt AA_UseHighDpiPixmaps, definir formato de superfície (OpenGL/RGBA), animações amigáveis a vsync, reduzir thrash de layout; meta de interações a 60fps.
- Marca: logotipo consistente na barra de título, barra de tarefas, diálogo sobre, instalador.
- Colunas do shell redimensionáveis: o limite **painel de dispositivos | página** é um divisor horizontal arrastável (padrão 232px, arrastável 228–420px, lembrado em `layout/device_panel_width`). A página mantém sua largura natural e vive em uma área de scroll sem moldura, para que comprimi-la role lateralmente em vez de reflow dos tabs/grid; a largura do painel é mantida entre redimensionamentos da janela até o usuário arrastá-lo. _Decisão (usuário): antes era um `setFixedWidth(232)` fixo._

## Fase 1 — Divisão de arquitetura (sem mudança visual)
- Extrair os construtores de página para `python/gui/pages/`: `samsung.py`, `mtk.py`, `qc.py`, `spd.py`, `battery.py`, `network.py`, `settings.py`, `quick.py`.
- Extrair widgets compartilhados para `python/gui/widgets/`: `metric_card.py`, `collapsible.py`, `console.py`, `device_picker.py`.
- Manter `qt_app.py` como shell: chrome da janela, nav, roteamento, sinais.
- Aceitação: o app inicia, todos os tabs renderizam, testes passam.

## Fase 2 — Desempenho
- Virtualizar lista de dispositivos e log do console (QAbstractListModel + QListView) para evitar criação de widgets O(n).
- Agrupar atualizações de log (flush a cada 50ms ou 100 linhas).
- Cachear QSS renderizado por tema; regenerar apenas na mudança de acento.
- Carregamento preguiçoso de páginas pesadas (construir na primeira visita).
- Aceitação: 10k linhas de log sem travamento da UI; scroll permanece 60fps.

## Fase 3 — Polimento visual
- Tokens de design: escala de espaçamento (4/8/12/16/24), escala de raio, elevação.
- Elevação/sombra consistente nos cards; estados hover/focus.
- Movimento: fade de página 120ms, escala de pressão de botão, deslize de toast.
- Sistema de ícones: substituir emoji por ícones SVG (glifos da marca).
- Estados vazios e skeletons para detecção de dispositivos.
- Modo de alto contraste + alternância de movimento reduzido.

## Fase 4 — Fluxos de UX
- Diálogo unificado de seleção de dispositivo com busca/filtro e badges de transporte.
- Progresso da operação: lista de passos com checkmarks, ETA, cancelar por dispositivo.
- Apresentação de erros: cards acionáveis com “tentar novamente / abrir docs / copiar log”.
- Configurações: pesquisáveis, agrupadas, com reset para padrões.
- Console: filtrar por nível/dispositivo, exportar, buscar.

## Fase 5 — Acessibilidade & i18n
- Ordem completa de Tab, foco visível, rótulos estilo ARIA.
- Atalhos de teclado documentados no app.
- Extração de strings para traduções (sem strings de usuário codificadas em widgets).

## Fase 6 — Testes
- Testes de smoke da GUI com pytest-qt (headless).
- Screenshots de regressão visual para cada página/tema.
- Benchmarks de desempenho para renderização de log/dispositivos.

## Entregáveis
- `python/gui/pages/*`, `python/gui/widgets/*`
- Sistema de tokens atualizado em `theme.py`
- `tests/test_gui_smoke.py`
- Atualização de docs no README/INDEX.

## Riscos
- Monolito de 15k LOC; extração incremental necessária.
- Regras de threading do PyQt; manter todo toque em widget na thread principal.
- Preservar escopo multi-dispositivo e semântica de cancelamento.

## Tarefa sugerida primeiro
Extrair `_build_console` e `_build_conn_bar` para `widgets/console.py` e `widgets/connection_bar.py` com API baseada em sinais; sem mudança de comportamento.

## Fase 7 — Renderização de fluxo e job (novo)
### Problemas observados
- `_add_job_flows` achata todos os modos em uma lista de botões por job; o modo fica apenas no tooltip, causando confusão.
- Botões duplicados entre páginas (Quick, seções de operações por chip, abas Unlock) com gating inconsistente.
- Botões experimentais/destrutivos distinguidos apenas por cor/borda; sem legenda.
- Sem busca/filtro, sem usados recentemente, sem favoritos.
- Rótulos longos de fluxo transbordam/quebram de forma imprevisível no FlowLayout.
- Sem agrupamento visual por risco (somente leitura vs flash vs experimental).

### Modelo de renderização proposto
- Navegação **Job → Mode → Method** em três níveis:
  - Esquerda: lista de Jobs (verbo primeiro, ícones).
  - Meio: abas de Mode (ADB, MTP, …) com contagens.
  - Direita: cards de Method (nome, badge de risco, badge experimental, tooltip).
- Fonte única de verdade: `core.modes_for` / `core.methods_for`; sem listas duplicadas nas páginas.
- Desduplicar por (job, mode, key) globalmente; páginas por chip filtram por modos suportados em vez de reexecutar `_add_job_flows`.
- Estados do card de método: habilitado/desabilitado por gates de capacidade do dispositivo, em execução (spinner), último resultado (ok/falha).

### O que mover
- Mover a construção de botões de `_add_job_flows` para `widgets/flow_button.py` + `widgets/method_card.py`.
- Mover enumeração de mode/job para um modelo `FlowRegistryView` (fino, sem lógica) para binding na UI.
- Mover a lógica de confirmação destrutiva/experimental para um `ConfirmDialog` reutilizável.

### O que mesclar
- Mesclar página Quick e páginas de operações por chip para usar o mesmo widget `FlowBrowser` com filtro `modes`.
- Mesclar o tratamento de aviso experimental em badge do card + diálogo.

### O que remover / desduplicar
- Remover chamadas por página a `_add_job_flows` que duplicam os mesmos fluxos de job; substituir por `FlowBrowser` filtrado.
- Remover instâncias duplicadas de `Flow` (mesma chave sob múltiplos modos) agrupando modos no card.
- Remover cabeçalhos crus `QLabel(job.upper())` em favor de cabeçalhos de seção com contagens.

### Novos recursos
- Caixa de busca filtra por nome de job/mode/método e chave.
- Favoritos/recentes persistidos nas configurações.
- Legenda de risco: somente leitura (verde), médio (âmbar), alto (vermelho), experimental (âmbar tracejado).
- Seleção em lote: checkboxes para enfileirar múltiplos métodos (execução sequencial com cancelamento por passo).
- Arrastar para reordenar favoritos.

### Aceitação
- Um navegador de fluxos consistente em todas as páginas.
- Nenhum botão de método duplicado para o mesmo (job, mode, key).
- A busca filtra em <50ms para 280 linhas.
- Gates de capacidade desabilitam visualmente métodos com tooltip de motivo.

### Fase 7 — status (implementado até agora)
- **Forma escolhida: atualização in-place.** Introduzir o caminho único de renderização agora e atualizá-lo no local — `FlowBrowser` (view) + `MethodCard` (botão) + `flow_meta` (roteamento/risco) — *sem* a navegação em três painéis Job → Mode → Method ainda. As páginas mantêm o layout atual; `_add_job_flows` constrói linhas e as renderiza via `FlowBrowser`, e os cliques roteiam via `flow_meta.route_for`.
- **Modelo de risco derivado** (`flow_meta.risk_for`, a única fonte que um badge pode ler): `experimental` = chave em `_EXPERIMENTAL_FLOW_MAP`; `high` = chave em `_DESTRUCTIVE_CONFIRM` e portanto **exatamente os fluxos que a UI já pede para confirmar** (um badge nunca pode alegar `high` sem um diálogo, nem `read` sem ser somente leitura); `read` = apenas para `READ_ONLY_JOBS` (`{"Read Device Info", "Detect Devices"}`); todo o resto, incluindo chaves/jobs desconhecidos, fecha por segurança para `medium`.
- **Fatia B1 — renderização de fluxos agrupada (esta fatia).** `FlowBrowser.set_rows` agora agrupa o que renderiza, corrigindo os três problemas nomeados:
  - Cabeçalho de job agora é `{"REMOVE FRP"} · 6` — o `QLabel(job.upper())` cru ganhou uma **contagem** de métodos (atenuada com o token `border_hi`, o nome mantém o tratamento existente 11px / 800 / 1px).
  - Dentro de cada job, os cards são agrupados por **modo de transporte** atrás de um pequeno subcabeçalho de modo (`— ADB`), em vez de uma lista plana por job com o modo apenas no tooltip. As linhas chegam em ordem por modo de `_flow_rows`, então uma sequência de modos iguais é uma seção; nenhum modo é expandido em cards extras.
  - Todo `MethodCard` pinta uma **borda semântica à esquerda** (`ok` somente leitura, `warn` médio, `err` alto, `experimental` experimental) composta sobre `_btn_ghost()`, para que o risco seja visível de relance junto à legenda existente. Cards experimentais mantêm sua borda **tracejada** âmbar — agora pertencente a `MethodCard.set_risk(level)`; `set_state` permanece inerte.
  - Inalterado por construção: o conjunto de linhas renderizadas, a regra de desduplicação ("primeiro modo vence" por job), o texto do botão (`btn_sha`), toda string de tooltip, o roteamento de clique, as sobreposições de confirmação/experimental e o registro de gates (`job=`/`mode=`, nunca `command=`). Apenas widgets de agrupamento/rótulo foram adicionados.
- **Golden regenerado deliberadamente aqui.** `tests/ui_inventory_golden.json` foi reconstruído com `REGEN_INVENTORY=1` nesta fatia. A **única** diferença é a contagem de **widgets por página** (os rótulos subcabeçalho de modo adicionados; +113 widgets em cinco páginas de fluxo intenso). `gated_count`, `gated_unique_triples`, `gated_triples_sha256`, `core_flows`, `action_meta` e os `buttons` / `acts` / `btn_sha` de cada página são byte-idênticos — o registro de gates e a superfície de clique não se moveram.
- **Fatia B2 — placa de modelo de dispositivo (cards de ação verticais) (esta fatia).** As linhas por ação da página do modelo agora são cards `ActionRow` (`python/gui/widgets/action_row.py`) em vez do `QFrame` de 50px feito à mão com `mousePressEvent` monkeypatched:
  - uma **borda esquerda semântica de 3px** (`err` para ações de apagar/destrutivas, senão `accent_hi`) — a mesma linguagem de borda de risco que `MethodCard.set_risk` pinta no navegador de fluxos,
  - um **tile de ícone 40x40**, um título **13px / 800** e uma descrição **elidida em uma linha**. Isso corrige o "rótulos longos de fluxo transbordam/quebram de forma imprevisível" do plano: a descrição elide em vez de quebrar, para que um rótulo longo nunca force a placa mais larga que seu painel nem leia como um bloco ragged de múltiplas linhas,
  - um **chip opcional de engine/mode** e um chevron **`›` atenuado**; hover/pressionado/foco pertencem ao widget (propriedade dinâmica QSS + anel de foco). O chip é pintado como uma **pílula de tom único** a partir da cor de acento que `common._mode_chip` já retorna (preenchimento tinto de acento, texto de acento, borda hairline de acento), para que todo badge leia como uma família,
  - **alcançável por teclado** — `StrongFocus` + Enter / Return / Space emitem o sinal `activated` (substituindo o `mousePressEvent` monkeypatched). A placa mantém suas tags `flow_act` / `flow_tip` e apenas conecta `activated`, então o roteamento não muda,
  - os contêineres de grupo agora carregam a **contagem** de ações do job (`FRP REMOVE · 4`) — a mesma linguagem nome + contagem dos cabeçalhos de job do navegador de fluxos.
- **Invariantes mantidos.** `_ACTION_META` ainda tem **62** entradas; os `acts` e `btn_sha` de cada página `dev_*` são byte-idênticos (nenhuma linha de ação, texto de botão ou botão foi adicionado/removido/renomeado); `gated_count` **418**, `gated_triples_sha256` `c89acce…7d75`, `gated_unique_triples` **61**, `core_flows` **116**, `stack_count` **25**. A largura mínima natural da pilha de páginas ainda é **699px**, provando que os rótulos elididos não ampliaram nada.
- **Golden regenerado deliberadamente aqui.** `tests/ui_inventory_golden.json` foi reconstruído com `REGEN_INVENTORY=1` nesta fatia: a única diferença é a contagem de **widgets por página** (`dev_apple` 59→63, `dev_motorola` 85→99 — as duas placas de modelos pesquisados com cards/rótulos adicionados). O md5 transitório do golden após B2 foi `929f428638e91a42865ddde1ac96dd19`. O polimento posterior desta fatia do documento (família de chip de tom único e a divisão do painel de dispositivos na primeira exibição) não alterou a contagem de widgets de nenhuma página, então o golden não precisou de nova regeneração.
- **Fatia B4 — a placa de modelo preenche a altura da página (esta fatia).** Na placa de modelo do dispositivo → modelo (`devices.build_brand_page`) a linha de divisão em dois painéis não recebia a altura da página, então uma grande banda vazia era deixada **abaixo** de ambos os painéis. Em uma janela 1600x951 (viewport externa da página `878x717`) os painéis mediam `left 250x313 / right 598x333` com uma **banda morta de 333px** abaixo, e a placa de ações recebia apenas `333` dos `717`px. Causa raiz: a linha de divisão foi adicionada a `outer` **com stretch 1** *e* um trailing `outer.addStretch(1)` foi adicionado logo após — os dois itens esticados dividiam o espaço vertical restante ~50/50, e nenhum painel era verticalmente `Expanding`, então nada o absorvia. Correção (cirúrgica, apenas em `build_brand_page`): remover o trailing stretch concorrente (a linha de divisão agora toma **toda** a altura restante) e dar à `list_col` esquerda e à `right_stack` direita uma política vertical explícita `Expanding`, para que o `lscroll` interno e o `_scroll` interno da página do modelo atual recebam a altura completa e tenham suas próprias barras de rolagem. As linhas da esquerda permanecem alinhadas ao topo (`lv2.addStretch(1)` intocado) e rolam quando a lista cresce. Depois: `left 250x646 / right 598x665`, banda morta **1px** (apenas a margem inferior de 8px do layout), a placa da direita mostra muitos mais fluxos e rola o restante internamente (`vscroll_max` 900 → 557), e o `_page_scroll` externo do shell permanece oculto (`verticalScrollBar().maximum() == 0`). Antecipando o requisito futuro do usuário, 40 modelos extras em memória aumentam o alcance de rolagem da lista da **esquerda** (`vscroll_max > 0`) **sem** alterar a altura de nenhum painel.
  - Novos testes: `tests/test_device_board_layout.py` — `TestBrandPageFillsHeight::test_no_dead_band_below_split`, `::test_both_panes_get_the_real_height`, `::test_right_board_scrolls_its_own_content`, `::test_more_devices_scroll_left_without_growing_the_panes`. Ambos os testes de geometria foram confirmados **falhar** no código não corrigido primeiro (banda morta 295px em H=640; painel esquerdo 275px vs o piso de 412px) antes da correção.
  - **Nenhum widget foi adicionado ou removido** (apenas uma política de tamanho mudou e um espaçador de stretch foi removido), então a contagem de widgets de nenhuma página se moveu e `tests/ui_inventory_golden.json` não precisou de **nova** regen — ainda `929f428638e91a42865ddde1ac96dd19`.
- **Fatia C — registro completo de fluxos na placa de dispositivo (REVERTIDA).** Esta fatia adicionava um grupo final `MORE FLOWS · N` renderizando o registro completo de fluxos da engine do dispositivo como cards `ActionRow`, mais uma barra de filtro texto/modo. Era escopada por **engine + modo de transporte**, o que não é o mesmo que *funções deste dispositivo*: qualquer telefone expondo ADB portanto puxava todos os fluxos registrados em ADB no registro, então a placa do Motorola oferecia jobs apenas da Samsung (`knox_bypass`, `kg_remove`, `odin_flash_tar`), `imei_repair_spd`, `apple_icloud_*` e `huawei_frp_guide`. Pior, os modelos Motorola carregam **engines por modelo** (`Moto G13` = `spd`, `G24` = `mtk`, `G6` = `qcom`), portanto modelos `planned` mostravam um registro inteiro SPD/MTK para trabalho não realizado, e as marcas motorola/apple contornam o gate `researched` na placa por design. Revertida por completo: o grupo de registro, sua barra de filtro, `_ENGINE_MODES`, a postergação da primeira exibição e `tests/test_device_flows.py` se foram; a placa é novamente exatamente as ações curadas por dispositivo. O golden de inventário foi byte-idêntico ao longo (`929f428638e91a42865ddde1ac96dd19`) porque o grupo era construído preguiçosamente, então a reversão não precisa de regen também.
  - Lição para qualquer retentativa: escopar por **as `actions` declaradas do próprio modelo** (`supported_devices.json`), expandindo apenas os fluxos para os quais essas ações realmente despacham — nunca por engine + modo.
  - Fato verificado que sobrevive e é reutilizável: `win._route_flow_activation(job, mode, key, label)` é o único sumidouro que aplica a confirmação destrutiva e o ack de ownership EXPERIMENTAL; `_dispatch`/`start_model_action` não é (sua verificação experimental é o conjunto estreito `devices._EXPERIMENTAL_ACTS`, então por exemplo `emmc_raw` rodaria sem ack).
- **Adiado (ainda):** caixa de busca / chips de filtro de modo sobre uma lista de fluxos por dispositivo, favoritos/recentes (persistidos em configurações), fila de seleção em lote (checkboxes + execução sequencial), arrastar para reordenar, navegação em três painéis Job → Mode → Method, expandir as variantes de modo de um job em cards extras (um card por `(job, mode, key)` é uma decisão posterior deliberada — esta fatia NÃO expande modos) e um `ConfirmDialog` reutilizável (as sobreposições de confirmação/experimental permanecem modais pertencentes à janela).

## Fase 8 — Polimento profissional e diferenciação (novo)
### Identidade visual
- Tema escuro signature “atelier” com textura sutil de grão/ruído e vinheta suave.
- Marca + monograma; iconografia consistente (estilo Lucide) em todas as ações.
- Cards herói de dispositivo: silhueta de imagem do modelo, chip, badges de transporte, visto pela última vez.
- Cena de conexão animada aprimorada: pulso real do cabo, pontos de status por dispositivo.

### Densidade de informação
- Painel inspetor colapsável: detalhes do dispositivo selecionado, partições, resumo de PIT, logs.
- Visão em linha do tempo de operações (início/fim, duração, resultado) por dispositivo.
- Visão de diff para mudanças de PIT/partição antes do flash.

### Segurança e confiança
- Card de checklist pré-voo antes de operações destrutivas (dispositivo, firmware, correspondência de PIT).
- Escada de risco clara com cor + ícone + texto; nunca apenas cor.
- Visualizador de log de auditoria (ações experimentais) com exportação.

### Produtividade
- Paleta de comandos (Ctrl+K) para buscar fluxos, dispositivos, configurações.
- Busca global em logs e dispositivos.
- Navegação com teclado em primeiro lugar; sobreposição de atalhos (?).
- Restauração de sessão: reabrir último dispositivo + página.

### Sensação nativa do Linux
- Diálogos de arquivo nativos, consciência do tema do sistema, tratamento Wayland/X11.
- Notificações do desktop para operações longas; ícone de bandeja com progresso.
- Arrastar e soltar arquivos de firmware na página de flash.

### Onboarding
- Assistente de primeira execução: setup udev, status de build do bridge, teste de dispositivo.
- Estados vazios com ilustrações e próximos passos.
- Gaveta de ajuda contextual com docs por fluxo de `operations/`.

### Ativos de marca
- Novo conjunto de logotipos, splash, gráficos do instalador, ícone do app.
- Screenshots do README atualizados para corresponder à nova UI.

## Fase 9 — Redesign do console / terminal (novo)
### Objetivo
Fazer o log do console parecer um terminal Linux de primeira classe (estética UEFI-shell/TTY) em vez de uma caixa de texto apertada.

### Layout
- Dock dedicado à **direita** em um divisor horizontal (páginas à esquerda, console à direita); redimensionável, colapsável para uma barra fina. Largura padrão 420px, mínimo 360px (medido a partir da própria linha de controle do dock para nada ser cortado). _Decisão (usuário): o console permanece à direita — um rascunho anterior desta fase disse "dock inferior / 35% de altura"; isso está superado._
- Terminal wide monoespaçado com padding confortável (16px), altura de linha 1.45.
- Modo terminal em tela cheia opcional (F11) com chrome mínimo.
- Abas por dispositivo ou chips de filtro para que os logs não se intercalem.

### Estilo
- Paleta TTY escura: fundo preto, texto verde/âmbar/ciano, scanline sutil opcional.
- Suporte a cores ANSI para saída do bridge; cabeçalhos em negrito, timestamps atenuados.
- Alternância de números de linha / timestamps.
- Seleção + copiar; menu de clique direito (copiar, salvar, limpar, filtrar).

### Comportamento
- Streaming com backpressure; sem congelamento da UI em 10k+ linhas.
- Busca com regex, destaque de correspondências, saltar próximo/anterior.
- Exportar para arquivo; salvamento automático do log da sessão.
- Filtro de dispositivo e filtro de nível (info/warn/error/step).

### Sem compressão
- Restrições de largura/altura mínimas; agrupamento responsivo; scroll horizontal para linhas longas.
- Colunas redimensionáveis para timestamp/nível/dispositivo.

## Fase 10 — Mensagens do console & sistema de toast (novo)
### Mensagens do console
- Entradas de log estruturadas: timestamp, chave do dispositivo, nível, mensagem.
- Níveis coloridos: info (ardósia), sucesso (verde), warn (âmbar), erro (vermelho), step (ciano).
- Saída multilinha colapsável (stack traces, JSON) com “mostrar mais”.
- Barras de progresso inline para passos de flash; ícones de status por passo.
- Chaves de dispositivo clicáveis para focar o dispositivo; chaves de fluxo clicáveis para abrir docs.

### Toasts
- Toasts não bloqueantes, empilhados, com ícone, título, mensagem, botão de ação.
- Dispensa automática com barra de progresso; pausa ao passar o mouse.
- Estilos por severidade (info/success/warn/error) com paleta consistente.
- Limite de fila (máx. 3 visíveis) com contador de overflow.
- Opções de posição (superior direita/inferior direita) e suporte a movimento reduzido.
- Som/haptics opcionais para erros.

## Fase 12 — Pesquisa de paridade HiProTool (novo)
### Status
- Busca online indisponível neste ambiente (HTTP 402). Pesquisa manual necessária.

### Tarefas de pesquisa
- Coletar lista de recursos do HiProTool (FRP, MDM, bloqueio de tela, carrier, IMEI, flashing).
- Mapear cada método para uma engine (ADB, modo download, BROM, EDL, fastboot, SPD).
- Identificar atalhos e pré-requisitos específicos de dispositivo.
- Documentar em `operations/` com etapas de verificação e notas de segurança.
- Priorizar métodos de alto valor e baixo risco primeiro.

## Fase 14 — Próximos recursos (novo)
### Recursos-alvo
- Remoção de IMEI da blacklist (pesquisa + playbooks por dispositivo).
- Melhorias de desbloqueio de carrier (SIM lock, caminhos NVDATA/QCN).
- Melhorias de desbloqueio de MDM (device owner, provisionamento QR, recovery).
- Melhorias de FRP (métodos por chip/versão do Android).
- Melhorias de remoção de bloqueio de tela (ADB, recovery, download, EDL).
- Remoção de Samsung Knox Guard (EXPERIMENTAL, audit-logged).
- Remoção de inscrição MDM Apple (profile/DEP).
- Ferramentas de gerenciamento Samsung Knox.
- Tratamento de inscrição Android Enterprise.
- Tratamento de inscrição zero-touch.
- Remoção de Apple Activation Lock (escopo checkm8/DFU, limites honestos).
- Recuperação de PUK do SIM para desbloquear PIN do SIM.
- Remoção de bloqueio biométrico (pesquisa, limites de dispositivo).

### Notas
- Cada recurso deve ser respaldado pelo Rust e gateado como EXPERIMENTAL onde for arriscado.
- Documentar em `operations/` com verificação e notas de segurança.

## Fase 15 — Auditoria e limpeza de documentação (novo)
### Referências obsoletas encontradas (históricas/retiradas)
- `operations/*/README.md` mencionam módulos Python retirados (`knox.py`, `qcn.py`, `health.py`, `apple.py`, `flows/*.py`) como contexto; aceitável, mas deve ser claramente marcado como histórico.
- `INDEX.md` previamente referenciava `SPLIT_PLAN.md` ausente (corrigido).
- `README.md` listava anteriormente módulos inexistentes no layout do repositório (corrigido).
- `DESCRIPTION.md` tinha contagens incorretas de transporte/job (corrigido).

### Tarefas de documentação restantes
- Normalizar todas as notas “retirado” em uma única seção “History” por arquivo.
- Adicionar uma nota “Current architecture” no topo de cada README de operations.
- Remover ou arquivar planos de migração obsoletos (DESIGN.md → nova versão).
- Manter `operations/` apenas como pesquisa; ponteiros de código devem dizer `src/flows.rs`.
