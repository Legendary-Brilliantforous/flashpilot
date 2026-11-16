# FlashPilot — index

Language switcher: [English](../../INDEX.md) · **Français** · [Español](../es/INDEX.md) · [Deutsch](../de/INDEX.md) · [简体中文](../zh/INDEX.md) · [Русский](../ru/INDEX.md) · [Português](../pt/INDEX.md) · [日本語](../ja/INDEX.md) · [العربية](../ar/INDEX.md) · [हिन्दी](../hi/INDEX.md) · [Türkçe](../tr/INDEX.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

Le README présente le marketing. Ce fichier est l'index d'ingénierie — chaque dossier, ce qu'il fait, et où commencer.

## Lancer

```bash
# GUI
python main.py

# CLI (pont) — même protocole, sans GUI
./target/release/flashpilot-bridge detect-all
./target/release/flashpilot-bridge spd-detect
```

## Structure racine (17 entrées)

| Entrée | Quoi | Quand l'ouvrir |
|---|---|---|
| `main.py` | Point d'entrée de l'application. Ajoute le dépôt à `sys.path` et appelle `python.gui.qt_app.main()`. | Pour changer la façon dont l'app démarre. |
| `pyproject.toml` | Métadonnées du paquet Python (name=flashpilot, deps, backend de build). | Pour ajouter une dépendance Python ou monter la version. |
| `Cargo.toml` / `Cargo.lock` | Cœur Rust (le binaire `flashpilot-bridge`). | Pour changer la CLI du pont ou ajouter un protocole. |
| `python/` | Couche Python fine sur le moteur Rust : `python/core/` (shim + helpers GUI) et `python/gui/` (PyQt6). Tous les flux vivent dans `src/flows.rs`. | Plomberie GUI et appareils. |
| `src/` | Sources Rust. Mise en page miroir de `python/core/`. | Quand vous ajoutez une commande de pont ou changez un protocole USB. |
| `tests/` | Suite pytest. ~149 tests, ~1s d'exécution. | Lancez avec `.venv/bin/python -m pytest tests/ -q`. |
| `scripts/` | Outils shell autonomes. Aujourd'hui : `dump-connected.sh`, `validate_mtp_at.py`. | Pour une opération par lot hors GUI. |
| `docs/` | Ressources du README (captures, logo). | Pour le README. |
| `packaging/` | Script de build `.deb` + fichiers de contrôle. | Pour livrer une release. |
| `root/` | Règles udev (pour que les téléphones marchent sans sudo). | Configuration ponctuelle. |
| `operations/` | **Arborescences de documentation par job** — voir section « operations/ » ci-dessous. | Pour comprendre un job spécifique (FRP, MDM, verrou d'écran, etc.). |
| `build/` | **Tous les artefacts de build/runtime gitignored** — voir section « build/ » ci-dessous. | Vous n'ouvrez presque jamais ça. |
| `.github/` | Workflows CI, modèles d'issues. | Pour changer la CI. |
| `LICENSE` `CODE_OF_CONDUCT.md` `CONTRIBUTING.md` `SECURITY.md` `DESCRIPTION.md` | Métadonnées standard du projet. | À la release. |

## Mise en page `python/`

```
python/
├── main.py                 <- point d'entrée (ajoute le dépôt au sys.path, appelle python.gui.qt_app.main)
├── gui/                    <- application PyQt6
│   ├── qt_app.py           <- Fenêtre principale + toutes les UI par mode (~12k LOC)
│   ├── devices.py          <- Drill-down « appareils supportés » piloté par les données (marque -> modèle -> action)
│   ├── theme.py            <- Jetons de design (couleurs, styles de boutons, helpers de version)
│   ├── animations.py       <- Glyphes peints : scène de connexion, orbe de statut, etc.
│   ├── nav.py              <- Rail de navigation principal + barre de chips OEM
│   ├── toast.py            <- Notifications toast
│   └── supported_devices.json  <- Base de données des actions par modèle
└── core/                   <- Couche Python fine (sans deps Qt ; délègue au pont Rust)
    ├── core.py             <- Miroir FLOWS/JOBS/MODES (cache codé en dur + Rust flow_list())
    ├── bridge.py           <- Dialogue avec le binaire `flashpilot-bridge`
    ├── flow.py             <- Primitives Flow/Step + annulation
    ├── jobs.py             <- Cycle de vie FlashJob (couche job isolée)
    ├── cancel.py           <- Registre d'annulation coopérative
    ├── devices.py          <- Identité multi-appareils (clés stables, liste, résolution, mapping transports)
    ├── frp.py              <- Surface de réexport FRP uniquement (nom == responsabilité)
    ├── mtk.py              <- PIDs/stages/chips MTK (0003=BROM, 2000=preloader)
    ├── mtp.py              <- Samsung MTP/AT (activation ADB multi-séquence)
    ├── pit.py pitstore.py  <- Parseur PIT Samsung + cache
    ├── adb.py device_info.py actions.py experimental.py fus.py
    └── (no flows/ dir)     <- les flux vivent dans src/flows.rs ; Python ne fait que déléguer via bridge.flow_run()
```

**Les flux vivent dans Rust.** `python/core/core.py` est un shim fin : `_RustFlow` délègue l'exécution à `bridge flow-run <key>`. Le registre canonique est `src/flows.rs` (macro `flow!`, ~280 lignes) ; Python le reflète pour la recherche GUI.

## Mise en page `src/` (Rust)

```
src/
├── main.rs                 <- Tout le dispatch CLI (eprintln! est le canal « log ») + flow-run
├── flows.rs                <- LE registre de flux (macro flow! ; FLOWS/JOBS/MODES)
├── usb/                    <- Contexte libusb, parsing de descripteurs, filtrage (mod.rs + filtering.rs)
├── devices.rs              <- Lignes d'appareils USB+ADB fusionnées
├── sam_download.rs         <- Session Samsung Download/Odin (commandes odin-*)
├── sam_errors.rs sam_setup.rs sam_*.rs  <- Helpers Samsung
├── mtk.rs mtk_da.rs        <- Flashage MediaTek BROM/DA
├── mtk_exploit.rs          <- Exploits BROM (bypass/kamakiri2/crash-to-BROM)
├── mtk_sla.rs mtk_sla_keys.rs <- Secure Lock Authentication
├── mtk_daloader.rs         <- Parsing de conteneur DA
├── qualcomm/               <- EDL : Sahara + Firehose + GPT
├── spd.rs                  <- UNISOC BSL (BSL_CMD_*, BSL_REP_*, FDL1/FDL2)
├── pac.rs                  <- Extraction/paquage PAC SPD
├── pit.rs                  <- Parseur PIT Samsung
├── mtp.rs at.rs adb.rs     <- Plomberie MTP, commande AT, ADB
├── fastboot.rs             <- Transport fastboot natif
├── moto_flash.rs           <- FRP fastboot Motorola en étapes
├── apple.rs                <- usbmuxd/lockdown Apple
├── bulk.rs hid.rs          <- Helpers bulk + HID
├── fwtar.rs sparse.rs imgtools.rs <- Firmware tar/sparse/boot-vbmeta
├── hostinfo.rs             <- Santé eMMC/UFS de l'hôte
├── config.rs error.rs util.rs device.rs
└── (no odin.rs)            <- La logique Odin vit dans sam_download.rs
```

## `operations/` — arborescences de documentation par job

Ces dossiers contiennent des **README par opération** qui expliquent comment chaque job fonctionne, quelles clés de flux il utilise, quels appareils il supporte et les mises en garde connues. Ce n'est **pas** du code — l'arborescence est du markdown pur (un nettoyage passé a supprimé les shims `.py` obsolètes qui y vivaient ; rien n'importe `operations/`). Le code vit dans `src/flows.rs` (le registre `flow!` ; `python/core/core.py` est un shim fin) et les modules par domaine (`knox.py`, `qcn.py`, `imei.py`, `emmc.py`, …). Les README de `operations/` sont écrits pour les utilisateurs finaux / chercheurs d'outils commerciaux ; le code fait foi.

| Dossier | Quoi | Vrai code dans |
|---|---|---|
| `operations/apple/` | iCloud, verrou d'activation, MDM, suppression code/clavier/perdu | Flux Rust (`src/flows.rs` : lignes `apple_*`, CLI `flow-run`) |
| `operations/frp/` | Contournement FRP par moteur + notes de recherche par appareil. **Commencez par `operations/frp/INDEX.md`**. | Flux Rust (registre `src/flows.rs`, CLI `flow-run`) ; shim fin `python/core/core.py` |
| `operations/mdm/` | Déverrouillage MDM / device-owner + notes par marque | Flux Rust (registre `src/flows.rs`, CLI `flow-run`) |
| `operations/screen_unlock/` | Suppression du verrou d'écran (ADB / recovery / download / complet) | Flux Rust (registre `src/flows.rs`, CLI `flow-run`) |
| `operations/battery/` | Rapport / réparation / test de charge batterie (par ADB) | Flux Rust (registre `src/flows.rs`, CLI `flow-run`) |
| `operations/network/` | État SIM, DNS, réinitialisation radio | Flux Rust (registre `src/flows.rs`, CLI `flow-run`) |
| `operations/carrier_unlock/` | Verrou opérateur (Apple, MTK) | Flux Rust (registre `src/flows.rs`, CLI `flow-run`) |
| `operations/flashing/` | Guides de flashage par vendeur (Samsung Odin, MTK DA, Qualcomm EDL, UNISOC SPD, PIT) | Flux Rust (registre `src/flows.rs`, CLI `flow-run`) |
| `operations/usb/` | Notes d'énumération et de détection USB | `src/usb/`, `src/devices.rs`, `python/core/devices.py` |

## `build/` — artefacts de build/runtime gitignored

| Sous-dossier | Contenu | Créé par |
|---|---|---|
| `build/target/` | Sortie `cargo build` Rust | `cargo build` |
| `build/dist/` | Paquets `.deb` | `packaging/build-deb.sh` |
| `build/cache/` | Caches TAR par appareil et dumps rétro-ingéniérés | GUI / `scripts/dump-connected.sh` |
| `build/mdm_qr/` | QR codes de provisionnement MDM générés | Flux GUI MDM |
| `build/pit/` | Fichiers `.pit` de table de partitions en cache | Flux GUI PIT |

**Règle :** ne faites jamais `git add` sur quoi que ce soit de `build/`. Si vous devez effacer l'état, supprimez le sous-dossier — il sera reconstruit.

## Comment ajouter une fonctionnalité (la fiche « quel fichier toucher ? »)

| Vous voulez… | Toucher |
|---|---|
| Ajouter un nouvel appareil à la liste supportée | `python/gui/supported_devices.json` |
| Ajouter une action par vendeur à un appareil supporté | `src/flows.rs` (ajouter une ligne `flow!(...)`) ; Python l'auto-découvre via `bridge.flow_list()` |
| Ajouter un flux ADB pour un sujet existant | Idem (Rust `src/flows.rs`) |
| Ajouter une nouvelle commande CLI de pont | `src/<sujet>.rs` + `src/main.rs` (branche `<cmd>` dans le match) |
| Ajouter une nouvelle page de navigation principale | `python/gui/qt_app.py` (`_build_*_page` + `_section_index`) |
| Ajouter une couleur / style de bouton | `python/gui/theme.py` (`C` dict / `_btn_*()`) |
| Documenter les notes par job d'un nouvel appareil | `operations/<job>/<marque>/<modèle>.md` |
| Ajouter un test | `tests/test_<zone>.py`, suivre le motif `test_mtk.py` |

## Comment fonctionne le lanceur d'opérations (à lire une fois)

La GUI n'appelle jamais un flux directement. Le sélecteur d'appareil par opération (`FlashPilotWindow._choose_device`) résout d'abord une clé d'appareil stable ; puis `_run_ops_flow` / `_run_job_flow` appellent `python.core.core.flow_for(job, mode, method)`, qui renvoie un objet `Flow()` (une liste de `Step()`), puis `flow.run(ctx, log)` est appelé sur un thread worker à l'intérieur de `devices.device_scope(key)` (pour que chaque résolveur cible le téléphone choisi). Chaque flux écrit sur un appelable `log(line)` que la GUI relie à sa console. L'annulation est à portée par appareil (`flow.request_cancel(key)` ; la diffusion sans clé arrête tout), vérifiée en tête de chaque `_run`.

Pour ajouter un flux : ajoutez une ligne `flow!("my_op", "My op", "Job Name", "MODE")` à `src/flows.rs`. Python l'auto-découvre via `bridge.flow_list()` et le drill-down job/mode/méthode de la GUI le prend en compte automatiquement. La CLI Rust `flow-run` l'exécute ; les résolveurs doivent accepter un serial cible / `vid:pid@bus:addr` (voir `src/device.rs`).
