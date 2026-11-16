# operations/frp/ — Protection contre la réinitialisation d'usine (Android uniquement)

Language switcher: [English](../../frp/INDEX.md) · **Français**

> Les appareils Apple n'ont pas de FRP (Apple utilise Activation Lock / iCloud
> à la place) — voir `operations/apple/`.

Ce répertoire contient des **arbres de documentation par moteur** pour le
contournement FRP. Le code réel vit dans `src/flows.rs` (Rust). Quand vous
avez une recette fonctionnelle pour un appareil (puce, paire de FDL, offsets de
partitions, etc.), déposez une courte note de recherche dans
`devices/<brand>/<model>.md`. Le README à la racine de ce fichier mappe chaque
flux FRP du codebase à l'endroit où il vit et à ce qu'il lui faut.

## Carte des moteurs

| Moteur | Quand l'utiliser | Code | CLI bridge |
|---|---|---|---|
| **Générique (ADB)** | Première tentative sur tout téléphone avec débogage USB activé | Flux Rust (`adb_frp`, lignes `frp_*` dans `src/flows.rs`) | `flow-run adb_frp` / `adb shell ...` via `bridge.adb_shell` |
| **MTK BROM** | MediaTek (Helio / Dimensity / MT6765) — éteindre → maintenir Vol-/+ → brancher USB | Flux Rust (lignes `mtk_*` dans `src/flows.rs`) | `flow-run mtk_brom_info` (CLI : `mtk-detect`, `mtk-da-upload`, `mtk-frp`, `mtk-bypass`) |
| **MTK DA** | MTK BROM ayant survécu au chargement du DA (puces à état verrouillé) | Flux Rust (`mtk_brom_backup`, `mtk_auth_flash`) | `flow-run mtk_brom_backup` |
| **Qualcomm EDL** | Téléchargement d'urgence 9008 (Snapdragon) | Flux Rust (lignes `edl_*`, `qcom_*`) | `flow-run edl_frp` (CLI : `qcom-*`) |
| **Samsung Exynos** | A14 (Exynos 850/1330), A15/A16 — le mode download Odin ne flash que, PAS pour FRP | Lignes Rust `frp_*` (contournement de compte Samsung) | (principalement sur l'appareil, pas de bridge) |
| **Samsung MTK (A05/A06)** | A05/A06 avec Helio G85 — utilise le MTK BROM (ci-dessus) | Flux Rust (`mtk_brom_info`, `mtk_brom_backup`) | `flow-run mtk_brom_backup` |
| **UNISOC/SPD** | 1782:4d00 FDL1+FDL2 (SC9863A, T606/UMS9230) | Flux Rust (lignes `spd_*`) + `src/spd.rs` | `flow-run spd_detect_info` (CLI : `spd-detect`, `spd-frp`, `spd-format`, `spd-magic-pack`) |
| **HiSilicon Kirin** | 12d1 — aucun flux ouvert pour l'instant (pas rétro-conçu) | (aucun pour l'instant) | (aucun) |

(Les anciens modules moteur `python/core/flows/*.py` n'ont jamais été livrés ;
`mtk-brom-backup` est la ligne de flux `mtk_brom_backup`. Vérifiez toute clé
avec `flow-list`.)

## Correspondance clé de flux → fonction

Chaque flux que les actions FRP de la GUI peuvent appeler. Les clés sont des
lignes du registre Rust (`src/flows.rs`, `flow-list` pour vérifier) ; la GUI
les route par (job, mode) et le bridge les exécute via `flow-run <key> [target]`.

| Clé de flux | Moteur | Ce qu'il fait |
|---|---|---|
| `adb_frp` | ADB générique | `settings put secure frp 0` + désactive les assistants de config + efface les données GMS |
| `frp_browser` | ADB générique | Ouvre `chrome://settings/` sur l'appareil via intent |
| `frp_emergency` | ADB générique | Ouvre les Paramètres via le composeur d'appel d'urgence (sur l'appareil) |
| `frp_settings` | ADB générique | Ouvre les Paramètres via le chemin de l'ombre de notifications (sur l'appareil) |
| `frp_fake_login` (+`_testdpc`, `+_adp`) | ADB générique | Provisionnement QR avec un DPC device-owner, puis effacement FRP |
| `at_info` | Samsung MTP/AT | Lit le mode + devconinfo via le canal AT (Samsung pré-Android 8) |
| `at_method` | Samsung MTP/AT | AT+DEBUGLVC pour activer ADB via le port diag |
| `download_frp` | Mode Download Samsung | Suppression FRP par firmware CSC/Combo (contrat de sécurité PIT) |
| `odin_enable_adb` | Mode Download Samsung | Active ADB depuis le mode download via tarball Odin |
| `mtk_combo_flash` | MTK Download | Flash de firmware combo (PIT + DA) |
| `mtk_recovery_reset` | MTK Download | Réinitialisation usine en mode recovery |
| `mtk_brom_info` | MTK BROM | Lit l'id de puce / handshake (nécessaire avant tout flash BROM) |
| `mtk_brom_backup` | MTK BROM | Dump des partitions via le DA BROM |
| `edl_frp` | Qualcomm EDL | Effacement Sahara + Firehose (05c6:9008) |
| `qcom_detect_info` | Qualcomm EDL | Détecte + info (lecture seule) |
| `frp_qr_provision` | ADB générique | Provisionnement QR (chemin TestDPC) |

(Retiré : les anciens noms de clés préfixés `flow_*` et
`python/core/flows/*.py` n'ont jamais été livrés — les clés n'ont pas de
préfixe `flow_`.)

## Comment une nouvelle recette par modèle arrive ici

1. **Lancer un dump d'appareil réel** (voir `scripts/dump-connected.sh` pour
   le chemin côté ADB, ou `flashpilot-bridge spd-format` pour le chemin côté
   BROM sur Unisoc). Le dump va dans `build/cache/dumps/<model>_<codename>/`.

2. **À partir du dump, identifiez** le moteur + la puce + le nom de la
   partition FRP (presque toujours `frp`, `frp_a`, ou `userdata` sur
   Android 11+).

3. **Ajoutez l'entrée de l'appareil** dans `python/gui/supported_devices.json`
   sous la bonne marque, avec `actions: ["frp", "info", "backup", "flash"]`
   et `status: "researched"`. (Le flux propre au moteur existant le récupère
   automatiquement — aucun nouveau flux n'est nécessaire sauf si le moteur
   lui-même manque.)

4. **Déposez une courte note de recherche** dans
   `operations/frp/devices/<brand>/<model>.md` avec la puce, le moteur, la
   partition, l'empreinte de build, et une phrase confirmant la recette
   (ex. « mmcblk0p4 = frp, effacement DA BROM instantané, pas de combo »).
   Voir `operations/frp/devices/nokia/nokia_g20.md` pour le format.

5. **Si le moteur lui-même n'a pas de flux** pour ce chipset, enregistrez le
   flux dans `src/flows.rs` (une ligne `flow!(...)`) et ajoutez le dispatch
   CLI dans `src/<engine>.rs` + `src/main.rs`.

## Pourquoi les fichiers par puce ont disparu

Les refactorings antérieurs ont scindé le god `frp.py` en fichiers par puce sous
`operations/frp/chips/` et par moteur sous
`operations/frp/{mtk,qualcomm,unisoc,samsung}_frp/`. Une ancienne révision de
cet INDEX affirmait l'existence de docstubs morts et d'un dispatch
`python/core/flows/brom.py` — ce module n'a jamais été livré. Le vrai dispatch
par puce est le registre de flux Rust (`src/flows.rs` : lignes `mtk_*`/`qcom_*`/
`spd_*`, `flow-list` pour vérifier) ; cet INDEX.md est la carte pour qu'un
nouveau dev sache où le code propre au moteur vit réellement.

## Pourquoi les shims Python par moteur ont disparu

`operations/frp/mtk_frp/mtk_frp.py` (et ses 4 frères) importaient des fonctions
de `python.core.flows.brom` et les ré-exportaient sous un **second** dict
`FLOWS = {}` que la GUI ne lit jamais. Ils entraient en collision avec le
`FLOWS` canonique dans `python/core/flows/__init__.py` et auraient masqué les
vrais s'il se trouvait qu'un jour la GUI les lisait. Remplacés par un README
dans chaque dossier moteur qui pointe vers les vrais modules Python.