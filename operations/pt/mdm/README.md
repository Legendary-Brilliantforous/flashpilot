Language switcher: [English](../../mdm/README.md) · [Français](../../fr/mdm/README.md) · [Español](../../es/mdm/README.md) · [Deutsch](../../de/mdm/README.md) · [简体中文](../../zh/mdm/README.md) · [Русский](../../ru/mdm/README.md) · **Português** · [日本語](../../ja/mdm/README.md) · [العربية](../../ar/mdm/README.md) · [हिन्दी](../../hi/mdm/README.md) · [Türkçe](../../tr/mdm/README.md)

> English is the canonical source. This page is a translation; help wanted — see [`../../../docs/TRANSLATION.md`](../../../docs/TRANSLATION.md).

# mdm/ — MDM (Gerenciamento móvel de dispositivos) + KnoxGuard
Desbloqueio de MDM, KG/RMM, garantia Knox.

Fontes: fluxos Rust (registro `src/flows.rs`, CLI `flow-run`): `mdm_qr`, `mdm_diagnostics`, `mdm_unlock*`, `knox_check` / `knox_bypass`
Rust: caminhos AT+KSTRINGB / KGLOCK em src/at.rs
Saída do gerador QR: `mdm_qr/` (raiz do repositório)
(Retirado: `python/core/knox.py`; `python/core/flows/mdm.py` foi planejado mas nunca publicado — a lógica MDM reside nos fluxos Rust.)

Estrutura:
```
mdm/
  devices/  — todas as marcas EXCETO apple (MDM da Apple vive em apple/mdm/)
    samsung/   — MDM Knox / KG da Samsung (série A)
    tecno/ infinix/ itel/ xiaomi/ oppo/ realme/ oneplus/ vivo/ huawei/ motorola/ nokia/ tcl_zte/ lg/ asus_sharp
    ...        — espelho de frp/devices menos apple
```

Irá abrigar: divisões de mdm.py + geração mdm_qr.
Nota: MDM da Apple fica em `apple/mdm/` de nível superior, não aqui.