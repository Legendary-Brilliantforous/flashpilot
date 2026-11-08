# Registro de alterações

Language switcher: [English](../../CHANGELOG.md) · [Français](../fr/CHANGELOG.md) · [Español](../es/CHANGELOG.md) · [Deutsch](../de/CHANGELOG.md) · [简体中文](../zh/CHANGELOG.md) · [Русский](../ru/CHANGELOG.md) · **Português** · [日本語](../ja/CHANGELOG.md) · [العربية](../ar/CHANGELOG.md) · [हिन्दी](../hi/CHANGELOG.md) · [Türkçe](../tr/CHANGELOG.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## 1.3.2 (o badge nomeia o protocolo USB)

- O badge de modo não mostra mais OTHER para um dispositivo conectado: 'MEDIATEK' não contém a subcadeia 'MTK', então um rótulo genérico de modo MTK ('MEDIATEK MODE (VID 0x0E8D PID 0x2008)') descia até OTHER.
- Um telefone MediaTek/Tecno em inicialização normal com um PID não correspondente (0e8d:2008, interface still-image/MTP, sem linha ADB) não é mais reivindicado como MediaTek de baixo nível: apenas os PIDs de flash (BROM/preloader/DA) reivindicam o rótulo de baixo nível; tudo o mais cai para a nomeação de protocolo baseada em interface (ADB/MTP/PTP/DIAG/storage/RNDIS) em TODAS as listas de dispositivos — antes, apenas dispositivos Samsung eram escaneados por protocolo.
- Transportes Rust: um PID não correspondente que ainda expõe uma interface still-image (classe 6) reporta MTP em vez de USB; hardware sem interface MTP mantém o rótulo USB honesto.
- O rótulo de conexão mostra 'MediaTek device (normal boot)' em vez de 'MediaTek low-level' para PIDs não de flash.
- Qualcomm EDL mantém seu próprio chip de badge: 'EDL MODE (Qualcomm Emergency Download)' contém a subcadeia 'download' e antes descia para o chip DOWNLOAD.
- Os diagnósticos HS-USB da Qualcomm (05c6:9006, ex. Moto em Diag) são nomeados 'QUALCOMM DIAG MODE (HS-USB Diagnostics 9006)' em vez de se fundirem no rótulo genérico 'QUALCOMM DEVICE'.

## 1.3.1 (correção do ModeBadge)

- O badge de modo do dispositivo (barra superior, perto de Stop) segue o dispositivo SELECIONADO e não lê mais MTP para configurações Qualcomm-normal (a subcadeia 'normal' descia para o chip MTP).

## 1.3.0 (classificação de dispositivo + seletor)

- Dispositivos não correspondentes (compósitos vendor-specific/diag) reportam 'USB' em vez do rótulo incorreto 'MTP'.
- Quando a seleção USB falha em um flap, as ferramentas ADB mostram o seletor de linha daemon em vez de recusar: escolha qual dispositivo a operação visa.

## 1.2.9 (identidade do dispositivo exibido)

- Trocar de dispositivo não cai mais para o primeiro telefone: o refresh de 3 s, o resolvedor de identidade live e todos os fallbacks se baseiam no dispositivo exibido; o caminho de ausência mantém os ladrilhos estáticos da linha.

## 1.2.8 (correção de troca da lista de dispositivos)

- A reconstrução da barra de conexão tenta novamente quando seu segundo scan perde um dispositivo que o monitor acabou de ver (janela de re-enumeration): ambos os dispositivos são renderizados e a troca funciona em links instáveis.

## 1.2.7 (vínculo de identidade do alvo)

- Um dispositivo substituído ocupando um bus:addr reutilizado é recusado (verificação serial zero-touch no alvo; a abertura casa vid/pid/bus/addr, não o número de série). Fecha o cenário de substituição de dispositivo: o transporte nunca segue para outro dispositivo.

## 1.2.6 (fallback da linha daemon)

- As ferramentas ADB caem para a linha daemon ADB quando a seleção por scan USB falha em um bus instável (o daemon é baseado em TCP e permanece autoritativo para presença). Corrige 'mostra conectado mas as ações dizem no adb'.

## 1.2.5 (sobreposição ADB no canto MTK)

- O branch de canto mtk_devs agora mostra a sobreposição ADB como as branches irmãs: um dispositivo Tecno/MTK com ADB autorizado nomeia o transporte no canto superior direito (antes mostrava apenas 'MediaTek low-level' enquanto o ADB Status mostrava connected).

## 1.2.4 (correção de AUTH do ADB)

- Alternância de hash AUTH corrigida: SHA-256 permanece em jogo ao longo das rodadas de token (rodadas ímpares SHA-256, pares SHA-1). Antes, uma assinatura perdida na rodada 1 em um link ruidoso re-tokenizava em um muro de SHA-1 -> falso 'not authorized' embora o dispositivo estivesse autorizado.
- `_wait_for_adb` tolera falhas de scan transitórias durante a espera.

## 1.2.3 (resiliência da seleção)

- Seleção de dispositivo com settle-retry: todo executor de ferramenta tenta novamente uma vez após 2,5 s quando um scan perde transitoriamente um dispositivo em re-enumeration, em vez de recusar com "no device" enquanto a GUI o mostra conectado. Seletores cancelados pelo usuário nunca são tentados novamente.

## 1.2.2 (ADB seguro para modem + correções de exibição)

### Transporte ADB (corrigido)

- Os caminhos poll/monitor/display são zero-touch (`adb-devices --no-probe`, `adb_presence`): sem open/claim/handshake a partir de loops. Corrige modems USB re-enumerando a cada ciclo (verificado ao vivo: 114 ciclos de poll silenciosos em um modem MSM8916 após tempestades ~1 Hz).
- Escada de delegação em brigas de claim: nativo -> transporte servidor Rust (`adb-shell-server`, serial explícito apenas) -> binário host -> kill de rescue (último recurso). Ops ADB agora têm sucesso com o servidor do sistema retendo a interface em vez de expulsá-la.
- Correção de fusão USB-ADB: cadeias de linha são analisadas (a desserialização de struct tinha silenciosamente yieldado zero entradas ADB, então as linhas nunca carregavam estado ADB).
- O canto QCOM agora mostra a sobreposição ADB como as branches irmãs.

### Robustez (corrigido)

- Um único settle-retry em recusas transitórias de gate (janelas de re-enumeration) com mensagens precisas; `rescue=False` + pinning de serial em todos os shells diagnostic/tool; detecção de falha Firehose; panics de entrada CLI; clamps de alocação; guards de travessia tar; numéricos XML estritos.

## 1.2.1 (versão estável)

### Suporte a multi-dispositivo (novo)

- Conecte vários telefones: a barra de conexão lista cada um (modelo · serial · transportes); clique em uma linha para inspecioná-lo.
- Toda operação pergunta a qual telefone se aplica quando vários correspondem (silencioso com 0–1 correspondência). Linhas de console carregam uma tag `[device-key]`.
- Uma operação por dispositivo: telefones diferentes podem flashear em paralelo; o mesmo telefone ainda serializa. STOP global transmite para todos os runners.
- Identidade estável (`python/core/devices.py`): `adb:<serial>` → `usb:<port-path>` → fallback volátil. Os alvos são re-resolvidos antes de abrir sessões, então a re-enumeration USB não órfã mais um flash (`usb device Fail`).
- Lista apenas de telefones: hubs, HID, webcams e leitores de cartão são filtrados.
- Novo modo de transporte `SPD` + fluxos read-only de detecção Qualcomm/SPD.

### EXPERIMENTAL por chip (novo)

- Samsung `Knox / Warranty`, Qualcomm `QCN / Modem`, por chip `IMEI Repair / Change`, `eMMC / UFS` — colapsáveis âmbar na página do chip dono (sem página LAB global). Checkbox de ownership em toda execução; mudança de IMEI também requer digitar `I UNDERSTAND`. Audit-logged; acks persistidos nunca passam automaticamente (`check_gate_strict`).

### MTK BROM (corrigido + melhorado)

- **Mapeamento PID/estágio corrigido** para a convenção mtkclient (`0e8d:0003`=BROM, `0e8d:2000`=preloader) em Rust, Python, rótulos GUI, logs e docs.
- Novo comando de ponte `mtk_crash_brom` + fluxo `MTK crash preloader into BROM` (registrado sob MTK BROM).
- `_wait_mtk_brom_target()` prefere o BROM estável mantido em vez da janela de preloader; a descoberta de DA recusa binários truncados (<1 KB).

### Odin / flash (endurecido)

- `_prepare_download_session()`: detach do driver do kernel + 3× retry de handshake através da re-enumeration; todos os PIDs Odin aceitos; cache PIT aquecido pré-flash.
- odin4 pinned com `-d /dev/bus/usb/BBB/AAA` + uma retry automática única em perda USB; trailer `.tar.md5` ancorado ao fim do arquivo (streaming, sem leitura RAM completa).
- Smart flash nativo loga por partição MB/s + ETA.

### Endurecimento de robustez (guiado por revisão)

- Sahara: comando HELLO/version/mode/packet-size validados no parse (antes: qualquer blob ≥32 bytes era confiável); a auto-verificação do formato de transferência agora faz round-trip de structs em vez de descartar bytes; falhas de close logadas; detach roda antes do claim; o handshake reporta resultados de transfer/close/reset em JSON em vez de descartá-los (reset explícito e visível).
- Auth ADB: backoff exponencial limitado entre rodadas de token; pausa única de keygen anunciada em vez de parecer travado.
- MTK: o tamanho de pacote configurado realmente chega à sessão DA (antes calculado e descartado; sessões hard-coded em 64 K), clamped para 512 B–1 MB.
- Backups de segurança: falhas imprimem um banner inegável com tempo decorrido e dica STOP (contrato inalterado: nunca bloqueia a operação).
- Gates experimentais: fluxos iCloud + Pixel migrados para acks estritos por execução; tokens de ack GUI agora contados por feature com expiração (sem bleed entre features, sem acks perdidos, sem autorizações stale).

### Correções de GUI

- Bordas vermelhas na barra superior + encolhimento de botões rastreados a animações shake/rubber concorrentes e anéis de focus tingidos de acento: animações serializadas com `_anim_lock` + limpeza completa; novos tokens de tema neutros `focus_ring`/`sel_border` (acentos vermelhos não podem mais vazar para o focus).
- `os.system()` → `subprocess` para rebuild do bridge / abertura do diretório de logs.
- Stub SPD duplicado "Enable ADB", gating experimental errado de `fastboot_unlock`, caminho morto FUS→slot AP e emissão `finished` faltante corrigidos. Superfície experimental morta LAB/Knox/QCN/PAC removida.

### Reestruturação

- `python/core/frp.py` (arquivo deus) → `python/core/core.py` (registry + fluxos); `frp.py` agora é só FRP. Split morto `python/core/flows/` removido.
- Nomes de job verb-first (`Remove FRP`, `Flash Firmware`, …); uma chave canônica snake_case por fluxo; casing do nome de exibição normalizado.

### Docs

- Screenshots frescos (`docs/samsung.png`, `mtk.png`, `spd.png`), README reescrito (highlights/matrix/layout), arquitetura de CONTRIBUTING + regras de fluxo, este changelog.

### boot.img + AVB (um único motor nativo)

- Novo motor de cirurgia de imagem no bridge Rust (`src/imgtools.rs`): parse do header boot Android, scan cpio newc, patch de props (pad-in-place ou crescimento estilo magiskboot com rewrite de header), gzip determinístico (mtime=0, nível 9), flags AVB vbmeta. CLI `boot-info` / `boot-patch-adb` / `vbmeta-patch`.
- Repack Python `spd_adb` + `core._patch_vbmeta_flags` delegam com fallback local (signatures e contratos de retorno inalterados).
- Trabalho de equivalência corrigiu dois bugs reais: o splice de crescimento discordava da alignment do reader por 2 bytes (corrompendo cada entrada posterior — ambas implementações), e re-patchar crescia `\n` a cada execução (ambos lados agora idempotentes). Bytes de gzip são intencionalmente excluídos da paridade (implementações zlib diferem); conteúdo descomprimido, tamanhos e campos conferem.
- 6 testes unitários Rust + 9 testes cross-implementation.

### PAC (um único motor nativo + ações GUI conectadas)

- Novo motor SPD PAC no bridge Rust (`src/pac.rs`): parse/extract/pack com layout YGDP, builders compartilhados de header/slot agora também usados pelo writer `spd-readback` (saída byte-identical; seus nomes históricos duplicados de slot quarentenados, não propagados). CLI `pac-parse` / `pac-extract` / `pac-pack`.
- Python `pac.*` delega com fallback local; novos `flow_pac_extract` / `flow_pac_pack` (somente arquivo, inputs env estilo ofp) registrados no FLOWS e mapeados no dispatcher GUI — os botões PAC antes mortos agora rodam.
- Testes de equivalência capturaram e corrigiram um bug real: o packer local descartava silenciosamente a cadeia product (escrita slice-copy); mais guards de overflow u32 com mensagens idênticas em ambos os motores.
- 5 testes unitários Rust + 7 testes cross-implementation (roundtrips nos dois sentidos, paridade sanitize incl. colisão de dir, mapeamento de erros).

### PIT (um único motor nativo)

- Novo motor Samsung PIT no bridge Rust (`src/pit.rs`): parse (layout 28/132), cadeias header/model, normalização de nomes, find, scan de overlap, validação forense + verdicts de saúde — mensagens, sumários e verdicts byte-identical à implementação Python em dumps reais e casos de borda (incluindo paridade Python-`repr` para nomes lixo).
- CLI `pit-parse` / `pit-health` / `pit-find` / `pit-overlaps` / `pit-model`; caminhos Python `pit.*` de bytes crus delegam com fallback local quando o binário está ausente (contratos preservados: ValueError/None/never-raise). Caminhos de objeto em memória e helpers de display permanecem locais e rápidos; regras compartilhadas pinadas por 11 testes de equivalência cross-implementation.
- 8 testes unitários Rust (vetores de layout, tabela de normalize, classificação de meta overlap, formas de summary/human-size).

### ADB (transporte nativo, sem platform-tools)

- Novo cliente ADB nativo no bridge Rust (`src/adb.rs`): transporte USB (255/66/1) com detach do driver do kernel, handshake CNXN, AUTH RSA-SHA256/SHA-1 (reusa `~/.android/adbkey`, gerado quando ausente), serviços `shell:` e `sync:` (STAT/RECV/SEND).
- `adb-devices` mantém seu contrato de linha `adb devices -l` de um scan nativo (`device` / `unauthorized` / `no permissions`); `adb-shell` recebe um serial (`-` = primeiro autorizado), além dos novos `adb-pull` / `adb-push` pinados por serial.
- Python: `bridge.adb_shell()` resolve explícito > escopo ambiental > primeiro serial autorizado (ADB multi-dispositivo agora pinado ao alvo); `adb.py` delega ao bridge; pull/push do backup/restauração EFS passam pelo bridge em vez de chamadas `adb` system sem pin. `has_adb()` agora significa "bridge construído".
- 6 testes Rust (framing, banner, PKCS#1 sign/verify, DER roundtrip, blob de pubkey bit-identical vs chave do adb do sistema) + 9 testes Python.

### Fastboot (transporte nativo + Motorola universal)

- Novo transporte USB fastboot nativo no bridge Rust (`src/fastboot.rs`): `fastboot-devices` (JSON) + `fastboot-cmd <vid:pid@bus:addr> <ms> <cmd…>` para a fase de comando (getvar/oem/erase/reboot) com detach do driver do kernel. Falha do lado do dispositivo renderiza como `FAILED (remote: …)` com exit 0, batendo com a forma de transcript do binário do sistema (incluindo valores `getvar` solitários que viajam no pacote OKAY em bootloaders Moto MBM).
- Helpers Python compartilhados (`_fastboot_run`, `_wait_fastboot`, `_fastboot_getvar`) são native-first com fallback para binário do sistema; comandos de fase DATA (flash/boot/…) sempre usam o binário do sistema, e a listagem lado-host `devices` é servida da detecção nativa. Todo o tráfego fastboot agora é pinado ao alvo (`vid:pid@bus:addr`), fechando o perigo de telefone errado sem `-s`.
- Novos fluxos Motorola em escala de marca (`moto_frp_adb`, `moto_frp_fastboot`, `moto_oem_unlock_token`): reset de provisionamento ADB, fluxo oficial de unlock token com leitura de lock-state + resets de sessão, leitor de token read-only. Mostrados sob Motorola → All Motorola / Lenovo (universal) e todo modelo Moto; URL do portal de unlock corrigida (a antiga `motorola.com/unlockbootloader` está morta).
- `python/core/fastboot.py` (Pixel) e `usb_watch.py` (scraping lsusb) movidos para o bridge; 7 novos testes `tests/test_fastboot_native.py`.
