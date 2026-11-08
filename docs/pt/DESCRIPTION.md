# FlashPilot 1.2.1 — Estável

Language switcher: [English](../../DESCRIPTION.md) · [Français](../../fr/DESCRIPTION.md) · [Español](../../es/DESCRIPTION.md) · [Deutsch](../../de/DESCRIPTION.md) · [简体中文](../../zh/DESCRIPTION.md) · [Русский](../../ru/DESCRIPTION.md) · **Português** · [日本語](../../ja/DESCRIPTION.md) · [العربية](../../ar/DESCRIPTION.md) · [हिन्दी](../../hi/DESCRIPTION.md) · [Türkçe](../../tr/DESCRIPTION.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

Bancada open source de flasheo e reparo para dispositivos Android no Linux — o equivalente gratuito das suites comerciais de flasheo para Windows. **1.2.0 é uma versão de estabilidade + avanço: `cargo check` com 0 avisos, `cargo test` 60 + `pytest` 149 passam, canal de release no GitHub ativo e histórico auditável.**

Um núcleo nativo **Rust** (`flashpilot-bridge`, ~9 300 LOC, libusb embutido) fala diretamente com os protocolos de bootloader — Samsung Odin/HID, MediaTek BROM/DA, Qualcomm Sahara/Firehose, Spreadtrum/UNISOC BSL — enquanto um estúdio **PyQt6** polido apresenta 9 transportes, 13 categorias de jobs e ~120 operações: flasheo, bypass de FRP, remoção de bloqueio de tela, desbloqueio MDM, ferramentas de partição, info do dispositivo, reinício e reparo de bateria/rede em qualquer dispositivo ADB.

**Novidades da versão estável 1.2.0:**
- **Puente com 0 avisos** — 18 caminhos mortos conectados: retenção de `Context` AT e validação `vid` (re-enumeration `AT/control` após `+DEBUGLVC`), fragmentação `EndpointConfig.max_packet_size` e `open_target/read_exact/info`, SPD `BSL_CMD`/`BSL_REP` + `iface` + `flush/read_flash/chip_uid/power_off`, `ProgressReporter` → % real de flasheo, Qualcomm `QcomDeviceInfo`/`FirehosePacket`, MTK `read16/write16` — `lto` -80 KB, sem vazamento de handles.
- **Versão dinâmica** — `APP_VERSION` a partir do `importlib.metadata` instalado (o `pyproject.toml` do deb é a verdade), `_display_version` `1.2.0→1.2` / `1.2.1→1.2.1`, GitHub `latest stable` ao vivo (nunca codificado à mão), pílula BETA no logo/barra de título.
- **Diálogos grandes unificados** — cards centralizados de 620 px arrastáveis (vs toast de 320 px) com texto de alto contraste `#e2e8f0`, arrastar por `✕` + `X`, cores do chip: `MTK amber`, `QCOM red`, `SPD violet`, `SAMSUNG blue`; o gate beta exige a caixa `I accept` (persiste por versão, padrão `first_install` / toggle `every_boot` em Ajustes → Atualizações), `Exit` fecha o app, stable `UPDATE/AHEAD/PATCH` usam o mesmo diálogo grande, as sobreposições de confirmação de flasheo/FRP usam o gradiente do chip.
- **Um único STOP global** — um só `⏹ STOP` na barra de título (fora de qualquer card), sincronização em 150 ms para `_FLOW_LABEL`, detém *qualquer* fluxo Samsung/MTK/QC/SPD; os Stops antigos por chip ficam ocultos.
- **Governança** — `dev`/`main` protegidas: CI `strict` `Rust+Python`, `1` revisão, `dismiss_stale`, `require_last_push_approval`, `linear_history`, `force_push:false`; `devin-ai-integration[bot]` removido do histórico/tag `v1.2.1-beta.1` → `55c0da3`.

- **Plataforma:** Linux
- **Linguagem:** Rust (núcleo) + Python 3.10+ / PyQt6 (UI)
- **Licença:** MIT
- **Status:** stable 1.2.0 — contribuidores bem-vindos

Use apenas em dispositivos que você possui ou está autorizado a reparar.