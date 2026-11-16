# FlashPilot 1.2.1 — Stable

Language switcher: [English](../../DESCRIPTION.md) · **Français**

Workbench open source de flashage et de réparation Linux pour appareils Android — l'équivalent gratuit des suites commerciales de flashage Windows. **1.2.0 est une version de stabilité + avancement : `cargo check` 0 avertissement, `cargo test` 60 + `pytest` 149 réussis, canal de release GitHub live, et historique auditable.**

Un cœur natif **Rust** (`flashpilot-bridge`, ~9 300 LOC, libusb fourni) parle directement aux protocoles de bootloader — Samsung Odin/HID, MediaTek BROM/DA, Qualcomm Sahara/Firehose, Spreadtrum/UNISOC BSL — tandis qu'un studio **PyQt6** soigné présente 9 transports, 13 catégories de jobs et ~120 opérations : flashage, contournement FRP, suppression de verrou d'écran, déverrouillage MDM, outils de partition, infos appareil, redémarrage, et réparation batterie/réseau sur tout appareil ADB.

**Nouveautés de la version stable 1.2.0 :**
- **Pont à 0 avertissement** — 18 chemins morts câblés : rétention du `Context` AT et validation `vid` (ré-énumération `AT/control` après `+DEBUGLVC`), découpage `EndpointConfig.max_packet_size` pour USB et `open_target/read_exact/info`, `BSL_CMD`/`BSL_REP` + `iface` + `flush/read_flash/chip_uid/power_off` pour SPD, `ProgressReporter` → vrai % de flash, Qualcomm `QcomDeviceInfo`/`FirehosePacket`, MTK `read16/write16` — `lto` -80 Ko, aucune fuite de handle.
- **Version dynamique** — `APP_VERSION` depuis `importlib.metadata` installé (`pyproject.toml` du deb fait foi), ` _display_version` `1.2.0→1.2` / `1.2.1→1.2.1`, GitHub `latest stable` live (jamais codé en dur), pastille BETA sur le logo/barre de titre.
- **Grandes boîtes de dialogue unifiées** — cartes centrées de 620 px, déplaçables (vs toast de 320 px) avec texte haute contraste `#e2e8f0`, glisser par `✕` + `X`, couleurs de puce : `MTK amber`, `QCOM red`, `SPD violet`, `SAMSUNG blue` ; la porte beta exige la case `I accept` (persiste par version, `first_install` par défaut / bascule `every_boot` dans Paramètres → Mises à jour), `Exit` quitte l'application, stable `UPDATE/AHEAD/PATCH` utilisent la même grande boîte, les superpositions de confirmation flash/FRP utilisent le dégradé de puce.
- **Un seul STOP global** — un seul `⏹ STOP` dans la barre de titre (hors de toute carte), synchronisation en 150 ms vers `_FLOW_LABEL`, arrête *tout* flux Samsung/MTK/QC/SPD ; les anciens Stops par puce sont masqués.
- **Gouvernance** — `dev`/`main` protégés : CI `strict` `Rust+Python`, `1` revue, `dismiss_stale`, `require_last_push_approval`, `linear_history`, `force_push:false` ; `devin-ai-integration[bot]` retiré de l'historique/tag `v1.2.1-beta.1` → `55c0da3`.

- **Plateforme :** Linux
- **Langage :** Rust (cœur) + Python 3.10+ / PyQt6 (UI)
- **Licence :** MIT
- **Statut :** stable 1.2.0 — contributeurs bienvenus

Utilisez-le sur des appareils que vous possédez ou êtes autorisé à réparer.