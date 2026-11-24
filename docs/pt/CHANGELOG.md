# Registro de alterações

Language switcher: [English](../../CHANGELOG.md) · [Français](../fr/CHANGELOG.md) · [Español](../es/CHANGELOG.md) · [Deutsch](../de/CHANGELOG.md) · [简体中文](../zh/CHANGELOG.md) · [Русский](../ru/CHANGELOG.md) · **Português** · [日本語](../ja/CHANGELOG.md) · [العربية](../ar/CHANGELOG.md) · [हिन्दी](../hi/CHANGELOG.md) · [Türkçe](../tr/CHANGELOG.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## 1.2.2 (atualizações automáticas, 10 idiomas, Rockchip + multi-dispositivo seguro para modem)

*Consolida as notas do ciclo de desenvolvimento 1.2.2 → 1.3.2 — tudo o que foi lançado desde 1.2.1.*

### Atualizações automáticas e Novidades (novo)

- As atualizações instalam-se sozinhas: o `.deb` baixado instala via sudo em segundo plano, o app reinicia e uma janela de uso único "o que foi adicionado ou mudou" mostra o changelog da nova versão no primeiro lançamento (o aviso manual "Install Now" permanece quando a auto-instalação está desligada em Ajustes → Atualizações).

### UI em 10 idiomas + troca de idioma ao vivo (novo)

- Toda a UI chega em 10 idiomas adicionais (Français, Español, Deutsch, 简体中文, Русский, Português, 日本語, العربية, हिन्दी, Türkçe): ajustes, ladrilhos de dispositivos, páginas e cadeias de console.
- Trocar o idioma da UI é imediato — sem reinício; os layouts se ajustam a métricas reais de fonte para que traduções longas quebrem linha em vez de cortar controles.
- Catálogos de tradução JSON baseados em chaves com verificação de cobertura; a CI faz smoke-tests dos catálogos instalados.

### Rockchip + detecção mais inteligente (novo)

- Nova página de marca Rockchip: família RK28xx–RK35xx via modo fastboot.
- A detecção identifica modelo, marca e fator de forma — não apenas o chip.
- Cada estágio de flash é capturado (paridade TFT): MediaTek BROM/preloader/DA em todo o conjunto de PIDs de estágio e VIDs OEM (incluindo o preloader VCOM 0x2000/0x2001), a família estendida de PIDs de download Qualcomm EDL, a união de PIDs de download SPD, e os diagnósticos Qualcomm HS-USB nomeados como um modo próprio.
- O badge de modo segue o dispositivo SELECIONADO e nomeia o protocolo USB real (ADB/MTP/PTP/DIAG/storage/RNDIS) em vez de OTHER: apenas os PIDs de flash reivindicam o rótulo de baixo nível MediaTek, Qualcomm EDL mantém seu chip de badge, e as quedas por subcadeia 'MEDIATEK'/'download' estão corrigidas.

### FRP Motorola (novo)

- Cadeia FRP fastboot CVE-2016-10277, provisionamento QR de fake-login com DPC próprio (TestDPC / Device Policy / Adobe), FRP fastboot em estágios com ciclos de flash + reinício, e um ciclo ADB em bootmode de fábrica.

### Caminhos de motor reais (novo)

- Caminhos reais de flash, FRP e bloqueio MTK/QCOM/Unisoc/Samsung no núcleo Rust.
- odin4 se foi: o motor Odin Rust nativo lida com todo o pipeline de tar, PIT e cada classe de problema conhecida do odin4; usbmuxd/lockdown da Apple movidos para Rust; o núcleo é só Rust (todos os fallbacks Python de dispositivo/protocolo removidos).

### ADB seguro para modem (corrigido)

- Os caminhos poll/monitor/display são zero-touch (`adb-devices --no-probe`): sem open/claim/handshake a partir de loops — modems USB param de re-enumerar a cada ciclo (verificado ao vivo: 114 ciclos de poll silenciosos em um modem MSM8916).
- Brigas de claim delegam em escada: nativo → transporte servidor Rust (serial explícito) → binário host → kill de rescue (último recurso), de modo que as ops ADB tenham sucesso enquanto o servidor do sistema retém a interface.
- Correção de fusão USB-ADB (cadeias de linha são analisadas, então as linhas realmente carregam estado ADB), resgate do detentor ocupado + retry transitório + estado ocupado honesto, guarda babble/overflow, comando de isolamento de teste de claim, valores CNXN de adb modernos, e os cantos QCOM/MTK mostram a sobreposição ADB como as branches irmãs.

### Confiabilidade multi-dispositivo (corrigido)

- Seleção com settle-retry: todo executor de ferramenta tenta novamente uma vez após 2,5 s quando um scan perde transitoriamente um dispositivo em re-enumeration, em vez de recusar com "no device" enquanto a GUI o mostra conectado.
- O AUTH do ADB mantém SHA-256 em jogo ao longo das rodadas de token (rodadas ímpares SHA-256, pares SHA-1), de modo que uma assinatura perdida na rodada 1 não se mure mais em um falso "not authorized"; `_wait_for_adb` tolera falhas de scan transitórias.
- Vínculo de identidade do alvo: um dispositivo substituído ocupando um bus:addr reutilizado é recusado (verificação serial zero-touch) — o transporte nunca segue para outro telefone.
- Troca da lista de dispositivos: a reconstrução da barra de conexão tenta novamente quando o segundo scan perde um dispositivo, trocar de dispositivo não cai mais para o primeiro telefone, e as ferramentas ADB caem para a linha daemon ADB quando a seleção USB falha ("mostra conectado mas as ações dizem no adb").
- Classificação + seletor de dispositivos: dispositivos não correspondentes reportam USB em vez de um rótulo MTP incorreto, e uma seleção USB perdida oferece o seletor de linha daemon ("Run on this device" / "Cancel") em vez de recusar.

### Resultados honestos e polimento de GUI (corrigido)

- Os fluxos FRP exigem flags verificados e um status de saída de shell real; uma saída de bridge não zero levanta uma falha com a cauda do log — sem mais toasts falsos de "completed".
- GUI: chips de job por linha, memória de janela, teto de toasts, navegação por teclado, STOP ciente do dispositivo (um job cancela esse dispositivo), kg_unlock movido para uma thread worker (cadeias de 30 segundos não congelam mais a janela), splash segue o build real, páginas diferidas continuam repetíveis, toasts limpam a barra superior.

### Segurança e robustez

- Saídas privadas por padrão, nomes temporários à prova de symlink, verificações de symlink.
- Verificação do firmware após escrita por padrão + gate de modelo + correções numéricas.
- FRP: o certificado de assinatura DPC é lido nativamente e o checksum de provisionamento está corrigido.
- Arnês de teste de hardware HIL: regressões multi-dispositivo / substituição de dispositivo / tempestade USB em hardware real; testes de backoff do monitor ADB tornados determinísticos.
- Página de destino pública (`website/`) com a matriz de capacidades e o console de protocolos.

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
