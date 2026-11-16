# 🔧 FlashPilot

Language switcher: [English](../../README.md) · **Français** · [Español](../es/README.md) · [Deutsch](../de/README.md) · [简体中文](../zh/README.md) · [Русский](../ru/README.md) · [Português](../pt/README.md) · [日本語](../ja/README.md) · [العربية](../ar/README.md) · [हिन्दी](../hi/README.md) · [Türkçe](../tr/README.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

> **Un atelier open source de flashage et de réparation de firmware Samsung pour Linux — une alternative à Odin / Heimdall pour flasher les téléphones Galaxy (mode Download/Odin), les appareils MediaTek (BROM/DA), Qualcomm (EDL) et Spreadtrum/UNISOC.**

**Mots-clés de recherche :** Samsung flashing tool · Odin alternative · Android firmware flashing Linux · Heimdall GUI · Galaxy phone repair · MTK BROM flash · Qualcomm EDL · FRP unlock · UNISOC flashing · device firmware tool · mobile repair · Android bootloader · USB flashing · Linux flashing suite · proprietary tool alternative

[![Rust](https://img.shields.io/badge/Rust-1.70+-orange?logo=rust&logoColor=white)](https://www.rust-lang.org)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-41cd52)](https://www.riverbankcomputing.com/software/pyqt/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](../../LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![CI](https://github.com/Legendary-Brilliantforous/flashpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/Legendary-Brilliantforous/flashpilot/actions)
[![Good First Issues](https://img.shields.io/github/issues/Legendary-Brilliantforous/flashpilot/good%20first%20issue)](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
[![Contributors](https://img.shields.io/github/contributors/Legendary-Brilliantforous/flashpilot)](https://github.com/Legendary-Brilliantforous/flashpilot/graphs/contributors)

**Qu'est-ce que c'est ?** L'équivalent Linux natif des suites de flashage Windows payantes — un seul outil unifié qui dialogue directement avec le bootloader des appareils **Samsung, MediaTek, Qualcomm et Spreadtrum/UNISOC**. Protocoles rétro-ingéniérés + performances natives Rust + une belle interface PyQt6 = l'alternative open source à Odin, Heimdall et aux outils commerciaux coûteux.

---

## ✨ Pourquoi ce projet compte

Le monde de la réparation Android repose sur des outils commerciaux fermés, réservés à Windows. Leurs protocoles sont rétro-ingéniérés par une petite communauté de passionnés — et la plupart de ces connaissances sont verrouillées dans des suites payantes ou dispersées sur les forums sous forme incomplète.

**Ce projet est notre réponse.** Il transforme ces protocoles rétro-ingéniérés en une base de code propre, auditable, sous licence MIT, que chacun peut lire, exécuter, étendre — et distribuer comme sa propre suite de flashage.

| Outil commercial | Windows uniquement, code fermé | Ce projet |
|---|---|---|
| Odin / Smart Switch | Windows, GUI uniquement | Protocole Odin open source (Rust, natif) + outils PIT |
| Outils de flash MTK | Windows, DA fermé | Flashage et sauvegarde MTK BROM/DA (scatter + GPT) |
| Outils EDL Qualcomm | Windows | Implémentation du protocole Sahara + Firehose |
| Outils SPD/UNISOC | Windows | Implémentation BSL en boîte blanche (clean-room) |
| Outils FRP / verrouillage | Payants, marché gris | Flux transparents ADB + mode download, déverrouillage MDM |

---

## 🚀 Points forts — 1.2.1 Stable (0 avertissement)

- **9 modes de transport** — ADB, MTP, mode Download Samsung, BROM Samsung, MTK, MTK BROM, Fastboot, Qualcomm EDL, SPD.
- **13 catégories de jobs** — Flasher le firmware, Supprimer FRP, Supprimer le verrou d'écran, Supprimer MDM, Déverrouiller l'opérateur, Lire les infos de l'appareil, Détecter les appareils, Redémarrer, Réparer les paramètres, plus par puce en EXPERIMENTAL : Knox / Garantie (Samsung), QCN / Modem (Qualcomm), Réparation / changement d'IMEI (MTK/SPD/Qualcomm), eMMC / UFS.
- **Multi-appareils** — branchez plusieurs téléphones : la barre de connexion liste chacun, chaque opération demande à quel téléphone elle s'applique (ou s'exécute silencieusement quand un seul correspond), et différents téléphones peuvent exécuter des opérations en parallèle (une op par appareil, STOP diffuse à tous).
- **Cœur Rust (`flashpilot-bridge`, ~9.3k LOC) — 0 avertissement `cargo check`** — USB brut avec *libusb fourni* (aucune dépendance système), vraies implémentations de protocole (+ 18 chemins morts câblés, trim ltcg -80KB).
  - **Samsung** : protocole de session Odin rétro-ingéniéré (basé sur Heimdall), payloads HID en mode download, lecture/écriture/flash PIT — contexte `AT` conservé, découpage `EndpointConfig`.
  - **MediaTek** : poignée de main BROM / preloader / DA, scatter & GPT, exploits BROM, clés SLA — pourcentage réel du `ProgressReporter`.
  - **Qualcomm** : `ProtocolError` Sahara + `QcomDeviceInfo` Firehose câblés via délais `Duration`.
  - **SPD/UNISOC** : BSL en boîte blanche (clean-room) — tous les `BSL_CMD/REP`, `iface`, `flush/read_flash/chip_uid/power_off` câblés.
  - Plus **MTP**, les commandes **AT** et la plomberie **ADB** complète.
- **Une GUI de niveau studio** — fenêtre frameless translucent, 10 thèmes d'accent, scène animée câble/statut, console live.
  - **Icônes de marque et fonds de bouton distincts** — icônes de marque nettes (Samsung Ⓢ, Apple 🍎 rouge, Motorola Ⓜ, LG Ⓛ, etc.) et couleurs de fond adaptées sur chaque bouton OEM de la barre de chips du haut.
  - **Vues horizontales pour Motorola et Apple** — les tableaux d'actions des modèles adoptent par défaut des dispositions en onglets horizontaux propres.
  - **Micro-interactions et glassmorphisme** — animations de fondu d'entrée de page de 160 ms fluides, typographie monospace des badges de métadonnées (`Consolas`, `Monaco`) et bordures de cartes glassmorphiques améliorées.
  - **Grandes boîtes de dialogue centrées (620 px, déplaçables, ✕)** — portail beta + stable `UPDATE/AHEAD/PATCH` + confirmations de flash/FRP, couleurs de puces `MTK ambre` `QCOM rouge` `SPD violet` `SAMSUNG bleu`, texte haute contraste.
  - **Accordéons EXPERIMENTAL par puce** — Knox (Samsung), QCN/IMEI (Qualcomm), IMEI (MTK/SPD) : bannière ambre, case d'engagement de propriété à chaque exécution, `I UNDERSTAND` à saisir pour confirmer un changement d'IMEI, avec journal d'audit.
  - **⏹ STOP** dans la barre de titre arrête toutes les opérations en cours ; les verrous par appareil laissent les autres téléphones continuer.

---

## 📸 Captures d'écran

| Opérations Samsung | Atelier MediaTek | Réparation batterie | Téléchargement SPD |
|---|---|---|---|
| ![Samsung](../../docs/samsung.png) | ![MediaTek](../../docs/mtk.png) | ![Batterie](../../docs/battery.png) | ![SPD](../../docs/spd.png) |

---

## 🧩 Matrice des fonctionnalités

| Capacité | Samsung | MediaTek | Qualcomm | SPD/UNISOC | Tout ADB |
|---|---|---|---|---|---|
| Détecter / infos | ✅ | ✅ (+ crash preloader→BROM) | ✅ (Sahara) | ✅ | ✅ |
| Flasher le firmware | ✅ (Odin, Rust natif) | ✅ (scatter + GPT) | ✅ (Firehose) | ✅ (FDL/régions) | — |
| Sauvegarder les partitions | ✅ (EFS) | ✅ | ✅ | ✅ | — |
| Contourner le FRP | ✅ (ADB + download) | ✅ | ✅ (EDL) | ✅ | ✅ |
| Supprimer le verrou d'écran | ✅ | ✅ | ✅ (EDL) | — | ✅ |
| Déverrouiller MDM | ✅ (ADB, QR, recovery) | — | — | — | — |
| Knox garantie/détournement (EXPERIMENTAL) | ✅ | — | — | — | — |
| Sauvegarde/restauration QCN + réparation/changement IMEI (EXPERIMENTAL) | — | ✅ (NVRAM) | ✅ (NV 550/682) | ✅ (BSL NV) | — |
| Outils de partition | ✅ (PIT) | ✅ (GPT) | ✅ | ✅ (extraction/paquage PAC) | — |
| Exploits bas niveau | ✅ (HID/BROM) | ✅ (exploit BROM, SLA) | ✅ (Sahara) | ✅ (BSL) | — |
| Batterie / réparation réseau | — | — | — | — | ✅ |

> 💡 Les sections **Batterie** et **Réseau** fonctionnent sur *tout* appareil Android avec débogage USB activé — aucun matériel vendeur requis.

---

## 🖥️ L'interface graphique

Une fenêtre frameless, translucent, à cartes radius, avec une **bannière de connexion** live (scène ordinateur → câble → téléphone avec une impulsion de données animée) au-dessus d'un **rail de navigation** à gauche et d'un **panneau console/log** à droite.

- **Barre de connexion** — liste live des appareils (une ligne par téléphone : modèle · série · transports) ; cliquez sur une ligne pour l'inspecter. Les boutons d'opération demandent quel téléphone quand plusieurs correspondent.
- **Samsung** — sous-onglets du hub Samsung : `ODIN FLASH · UNLOCK · ADVANCED FLASH · INFO & TOOLS`, plus les slots firmware (AP/BL/CP/CSC/USERDATA), les utilitaires Odin et un accordéon `KNOX — EXPERIMENTAL`.
- **MediaTek / Qualcomm / SPD** — ateliers dédiés avec outils bas niveau natifs (scatter/DA + crash-to-BROM, programmer/XML + QCN/IMEI, binaires FDL + adresses de base + IMEI), chacun avec son propre accordéon `— EXPERIMENTAL`.
- **Batterie** — santé de la jauge de carburant en %, temp/tension/courant, principaux consommateurs ; réparation en un clic.
- **Réseau** — état SIM, flags données/Wi-Fi, mode DNS ; réinitialisation radio et ré-enregistrement.
- **Paramètres** — intervalle d'auto-scan, chemins par défaut, purge auto de la console, 10 thèmes d'accent, animations (bascules shake/rubber/cable/bubble), lueur de fenêtre, statut du moteur et `cargo build` intégré.

**Raccourcis :** `F5` rescanner · `Ctrl+Enter` exécuter · `Ctrl+L` effacer la console · `Ctrl+S` enregistrer le journal · `Ctrl+F` rechercher.

---

## 📦 Démarrage rapide

**Prérequis :** toolchain Rust, Python 3.10+, un bureau Linux. C'est tout — libusb est fourni.

```bash
# 1. Compiler le pont Rust (la première compilation compile libusb depuis la source)
cargo build --release

# 2. (Recommandé) installer les règles udev USB pour que les téléphones ne nécessitent pas sudo
sudo bash root/setup-usb.sh

# 3. Environnement Python
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. Lancer
.venv/bin/python -m python.main        # ou : python3 main.py
```

Le flashage en mode download Samsung est natif (protocole Rust Odin) — aucun binaire propriétaire odin4 n'est récupéré, fourni ni requis. Le firmware combo Samsung doit être obtenu depuis les pages de support officielles de Samsung ou des archives de firmware de confiance.

---

## 🖥️ Support des plateformes — nous voulons vos avis

**Linux est la plateforme supportée.** FlashPilot est délibérément *la réponse native à Linux aux suites de flashage réservées à Windows* — le développement, les tests et les releases ciblent Linux, et cela ne changera pas.

**Windows / macOS ne sont pas supportés aujourd'hui**, pour des raisons pratiques :

- Windows USB, c'est l'enfer des pilotes par mode de téléphone (Zadig/WinUSB, QDLoader, pilotes Samsung qui se battent entre eux) ; la plupart des rapports « téléphone non détecté » seraient indébogables à distance.
- macOS ajoute un surcoût de signature/notarisation pour une demande quasi nulle en magasin de réparation.
- La pile *est* portable (Rust + rusb, Python, Qt), donc c'est une décision de maintenance, pas une impossibilité technique.

**Mais c'est une question ouverte, pas un verdict.** Si vous voulez le support Windows/macOS — ou si vous voulez plaider pour Linux uniquement pour toujours — dites-le-nous :

- 💬 Ouvrez une **[Discussion](https://github.com/Legendary-Brilliantforous/flashpilot/discussions)** avec votre cas d'usage (magasin de réparation ? labo ? quel OS ? quels téléphones ?).
- 🔧 Le code parle le plus fort : le plan est une abstraction `python/core/platform.py` (`open_file_manager()`, `detach_kernel_drivers()`, `usb_device_path()`, `needs_udev_setup()`) avec Linux comme seul backend, pour que les portages deviennent des PR additifs plutôt que des forks. Les PR dans cette direction sont bienvenus dès maintenant.
- 🎨 Connexe : des contributeurs ont proposé **PySide6** (LGPL, compatible licence avec ce projet MIT) plutôt que PyQt6 (GPLv3). Donnez votre avis sur la même Discussion — la migration est mécanique mais nécessite d'abord une couverture de smoke-test GUI.

Aucune décision ne sera prise sans l'avis des contributeurs. Venez et soyez-en un.

### CLI / passerelle

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

## 📁 Structure du dépôt

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

## 🧑‍💻 Contribuer

**Ce projet ne s'améliore qu'avec vous.** Nous recherchons des mainteneurs, des hackers de protocole, des designers GUI, des rédacteurs et des testeurs.

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — tout ce qu'il faut pour commencer.
- **Commencez par le label [`good first issue`](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)** — des tâches sélectionnées et accessibles aux débutants.
- Utilisez les modèles de **[rapport de bug](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=bug&template=bug_report.yml)** / **[demande de fonctionnalité](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=enhancement&template=feature_request.yml)**.
- **Tâches pour débutants** — chaque ligne de flux dans `src/flows.rs` est une opportunité : ajoutez une ligne `flow!(...)`, ajustez une séquence de commandes, branchez un nouveau combo d'appareil. Python l'auto-découvre via `bridge.flow_list()`.
- **Le framework de flux (`src/flows.rs`) est très simple** — une nouvelle méthode tient en une ligne :

```rust
flow!("my_method", "My method", "Read Device Info", "ADB"),
```

Elle apparaît automatiquement dans la GUI. C'est toute la boucle de contribution : **écrivez une ligne de flux, livrez une fonctionnalité.**
- **Règle multi-appareils** — ne saisissez jamais « l' » appareil ; acceptez `key=None` (portée ambiante) et filtrez par celui-ci. Voir `python/core/devices.py` et `CONTRIBUTING.md`.
- **Règles de nommage** — les jobs sont verbe d'abord (`Remove FRP`, pas `FRP bypass`) ; les clés de flux sont en snake_case court (pas de préfixe `flow_` dans `FLOWS`) ; les PIDs MTK sont `0003`=BROM / `2000`=preloader (convention mtkclient — ne les échangez pas).

**Idées pour lesquelles nous aimerions de l'aide :**
- Nouveaux modèles d'appareils / combos de firmware dans les tables de flux.
- Variantes de DA MediaTek, bizarreries scatter/GPT.
- Cas limites rawprogram & patch XML Qualcomm.
- Méthodes FRP / suppression de verrou supplémentaires par version d'Android.
- Empaquetage (Flatpak, AppImage, AUR, `cargo` + `pip`), CI, tests unitaires.
- Plus de protocoles ODIN, outillage eMMC/UFS, utilitaires iCloud adjacents et EDL.
- Traductions, thèmes et accessibilité.

---

## 🛡️ Sécurité et légalité

Cet outil dialogue directement avec les bootloaders et peut effacer des données ou bricker un appareil en cas de mauvaise utilisation.

- Utilisez-le uniquement sur des **appareils que vous possédez ou êtes autorisé à réparer** (magasins de réparation au service des téléphones de clients avec consentement).
- Lisez toujours les avertissements à l'écran et **sauvegardez les partitions** avant le flashage.
- Contourner le FRP/MDM sur un appareil qui ne vous appartient pas peut être **illégal dans votre juridiction** — vous êtes responsable de la manière dont vous utilisez ce logiciel.
- FlashPilot fournit les payloads de protocole dont les opérations ont besoin (payloads MTK DA/BROM, programmeurs firehose Qualcomm, FDL1/FDL2 Unisoc, bootloaders Samsung), de la même façon que les suites commerciales de flashage. Les images firmware pour un téléphone donné proviennent toujours de l'utilisateur ou du vendeur.

---

## 📄 Licence

MIT — voir [LICENSE](../../LICENSE). Les constantes du protocole Odin sont dérivées du projet Heimdall (MIT), et la référence BSL SPD provient de documentations de protocole en boîte blanche (spd_cmd.h / docs Opus-Spreadtrum).

---

**Étoile ⭐ ce dépôt, ouvrez une issue, envoyez une PR — et construisons ensemble la meilleure suite de flashage open source sur Linux.**
