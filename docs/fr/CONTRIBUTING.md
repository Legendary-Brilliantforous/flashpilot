# 🧑‍💻 Contribuer à FlashPilot

Language switcher: [English](../../CONTRIBUTING.md) · **Français**

Merci d'être passé ! Ce projet repose sur des protocoles issus de l'ingénierie inverse
et sur le savoir ouvert — chaque contribution le rend plus capable, plus fiable, et
plus proche des suites Windows payantes. Pas besoin d'être expert en flash pour
contribuer.

## Table des matières

- [Code de conduite](#code-de-conduite)
- [Comment le projet est organisé](#comment-le-projet-est-organisé)
- [Façons de contribuer](#façons-de-contribuer)
- [Mise en route](#mise-en-route)
- [Visite architecturale (10 minutes)](#visite-architecturale-10-minutes)
- [Comment ajouter un flux](#comment-ajouter-un-flux)
- [Ajouter un nouveau protocole USB / commande Rust](#ajouter-un-nouveau-protocole-usb--commande-rust)
- [Directives GUI](#directives-gui)
- [Tests](#tests)
- [Checklist de pull request](#checklist-de-pull-request)
- [Feuille de route & idées](#feuille-de-route--idées)

---

## Code de conduite

Voir [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Soyez respectueux, supposez la bonne
intention, et gardez les discussions techniques et utiles. C'est un projet
hobbyiste devenu sérieux : débutants et vétérans bienvenus. Le harcèlement, le
gatekeeping, ou le commit de secrets/identifiants ne seront pas tolérés. Les
charges utiles de protocole sont bienvenues lorsqu'elles documentent leur
provenance et leur licence.

---

## Comment le projet est organisé

Deux moitiés travaillent ensemble :

| Couche | Emplacement | Langage | Rôle |
|---|---|---|---|
| **Moteur / protocoles** | `src/` | Rust | USB brut, tous les protocoles de bootloader (`flashpilot-bridge` CLI) |
| **Registre des flux** | `src/flows.rs` | Rust | lignes de macro `flow!` → `FLOWS` / `JOBS` / `MODES` (source de vérité) |
| **Shim des flux** | `python/core/core.py` | Python | wrappers `_RustFlow` + fallback `JOBS` ; délègue à `bridge flow-run` |
| **Identité appareil** | `python/core/devices.py` | Python | clés stables, liste d'appareils, résolution de cible, portée thread |
| **Surface FRP** | `python/core/frp.py` | Python | ré-export FRP uniquement (nom == responsabilité) |
| **Studio GUI** | `python/gui/` | Python / PyQt6 | Workbench (`qt_app.py`), pages (`devices.py`), thème, animations |

Python ne parle jamais directement à l'USB. Il invoque
`target/release/flashpilot-bridge` (le binaire Rust), qui renvoie du JSON/texte.
La GUI n'écoute que les signaux des threads de travail — ne touchez jamais aux
widgets depuis un thread d'arrière-plan.

---

## Façons de contribuer

Pas de code ? Pas de problème :

- **Tests sur matériel réel** — signalez sur quels appareils/firmwares un flux fonctionne.
- **Documentation** — améliorez le README, ce fichier et les descriptions de flux.
- **Firmware / DA / archives combo** — liens vers des binaires légitimes, librement disponibles.
- **Traductions & thèmes** — l'interface est thémable ; de nouveaux packs d'accent sont des victoires faciles.
- **UI/UX** — maquettes, passes d'accessibilité, conception de raccourcis clavier.
- **Rapports de bug** — utilisez le [modèle de rapport de bug](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=bug&template=bug_report.yml) : étapes, journaux, sortie de `flashpilot-bridge detect`, modèle + version de firmware.
- **Code** — voir ci-dessous.

> 💡 **Nouveau venu ?** Cherchez le label **`good first issue`** dans le tracker —
> tâches sélectionnées, adaptées aux débutants, complètement cadrées et sûres.

---

## Mise en route

```bash
# 1. Build du bridge Rust
cargo build --release

# 2. (Recommandé) Règles udev USB
sudo bash root/setup-usb.sh

# 3. Créer le venv + lancer
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m python.main
```

L'app ouvre une fenêtre native PyQt6. Utilisez la page **Settings → Tools** pour
voir si le bridge est construit et si ADB est détecté.

---

## Migrer depuis un ancien checkout (à lire d'abord si vous revenez)

Une note sur le churn, simplement : entre la 1.2.0 et maintenant nous avons
renommé le module central, scindé un fichier-dieu en modules ciblés, renommé
chaque job, et ajouté une douzaine de fichiers. Cela casse les anciens imports,
les références de docs et tout script hors-arbre écrit contre `python.core.frp`.
Désolé — c'était le seul moyen de tuer le fichier-dieu, de corriger le
mélange de PIDs MTK, et de rendre le support multi-appareil possible sans
empiler des hacks par-dessus. Cette section est le guide d'adaptation complet ;
rien ici n'est déprécié progressivement, tout a changé d'un coup, donc
parcourez le tableau une fois et vous êtes à jour.

### Chemins renommés

| Avant | Après | Ce qu'il faut changer |
|---|---|---|
| `python/core/frp.py` (fichier-dieu : registre + tous les flux) | `python/core/core.py` | `from python.core import frp` → `from python.core import core`; `frp.FLOWS` → `core.FLOWS`, etc. |
| *(rien — FRP vivait dans le fichier-dieu)* | `python/core/frp.py` (nouveau, FRP seulement) | Si vous n'avez besoin que des flux FRP, importez d'ici au lieu de `core`. |
| *(rien)* | `python/core/devices.py` (nouveau) | Identité appareil, `list_devices()`, `resolve_usb_target()`, `device_scope()`. |
| *(rien)* | `python/core/imei.py` (nouveau) | Réparation / changement d'IMEI MTK/SPD. |
| *(rien)* | `python/core/experimental.py` (nouveau) | Gates EXPERIMENTAL + journal d'audit. |
| *(rien)* | `python/core/{knox,qcn,emmc,pac,apple,health,compat,device_info,fastboot,integrity,safety,spd_adb}.py` (nouveau) | Logique par domaine, auparavant inline dans le fichier-dieu ou manquante. |
| *(rien)* | `tests/test_devices.py` (nouveau) | Tests multi-appareils + portée d'annulation. |
| *(rien)* | `CHANGELOG.md` (nouveau) | Changements groupés par release ; consultez-le d'abord. |

### Le passage à Rust (architecture actuelle — le tableau ci-dessus est l'historique)

Après la scission ci-dessus, les moteurs ont migré vers Rust et le côté
Python s'est allégé. Vérité actuelle :

- **Les flux vivent dans `src/flows.rs`** (registre + `flow-run <key> [target]
  [--code/--partition/--file/--dpc ...]`). `flow-list` est la source de
  vérité — vérifiez une clé de flux là-bas avant de la citer dans la doc.
- **`python/core/core.py` est un shim fin** (~450 lignes) : `_RustFlow`
  délègue à `bridge flow-run`, le registre vient du bridge avec un fallback
  `JOBS`. Les 16 modules moteur par domaine (`knox`, `qcn`,
  `emmc`, `imei`, `apple`, `ofp`, `pac`, `health`, `flashing`, `spd_adb`,
  `integrity`, `fastboot`, `usb_watch`, `compat`, `updater`, `safety`)
  ont été supprimés — ne les référencez pas dans les nouvelles docs.
- **La GUI reste en Python** (`python/gui/qt_app.py` + `devices.py`) ; elle
  consomme le registre Rust via `bridge.flow_list()`.
- Les anciens fichiers de tests pour les flux Python supprimés ont été
  supprimés avec eux ; la couverture ce sont les suites par domaine +
  cargo `flows::tests`.

### Changements d'API auxquels vous devez vous adapter

- **Les résolveurs prennent `key=None`.** `find_samsung()`, `_download_mode_device()`,
  `_wait_for_adb()`, `_wait_mtk_brom_target()`, `_mtk_retry()`,
  `wait_clean_download_mode()`, `pit_contract()` acceptent tous une clé d'appareil
  stable optionnelle (portée thread ambiante par défaut — les anciens sites
  d'appel continuent de fonctionner, comportement premier-match préserve quand
  aucune clé n'est définie).
- **L'annulation est par appareil.** `request_cancel()` / `clear_cancel()` /
  `cancel_requested()` dans `flow.py` et `bridge.py` acceptent `key=None`.
  Les appels sans clé `request_cancel()` diffusent encore (STOP global) ;
  les vérifications sans clé consultent la portée ambiante, puis le bus diffusé.
- **Le verrou d'exécution est par appareil.** `_flow_start(label, destructive, key=None)` /
  `_flow_end(key=None)` / `_flow_busy_msg(key=None)` dans `qt_app.py` ; les
  anciennes globales `_FLOW_LOCK` / `_FLOW_LABEL` ont disparu (remplacées par des
  dicts par clé + `_flows_running()`).
- **Les lanceurs prennent `device_key=None`.** `_run_ops_flow()` / `_run_job_flow()`
  affichent le sélecteur d'appareil quand plusieurs téléphones correspondent,
  puis définissent `ctx["device_key"]` (+ `ctx["target"]` si résoluble) et
  s'exécutent dans `devices.device_scope()`.
- **Nouveau mode de transport `"SPD"`** dans `MODES` (VID `0x1782`) ; nouveaux
  jobs `Knox / Warranty`, `QCN / Modem`, `IMEI Repair / Change`, `eMMC / UFS`.
- **Les noms de job sont verbe-d'abord** (`Remove FRP`, pas `FRP bypass` ; voir le
  README). Si votre branche référence encore les anciens noms, renommez selon
  le tableau de « Visite architecturale ».
- **Les PIDs MTK sont au format mtkclient** : `0e8d:0003` = BROM,
  `0e8d:2000` = preloader. Plusieurs anciens commentaires/journaux les avaient
  inversés ; faites confiance à `mtk.pid_stage()` / Rust `boot_stage_for()`, pas
  aux anciennes chaînes.

### Si vous avez un PR ouvert d'avant la restructuration

1. Rebasez sur le nouvel arbre ; attendez des conflits confinés aux imports et
   aux blocs `JOBS`/`FLOWS`.
2. Lancez la checklist ci-dessous — `pytest` détectera immédiatement les
   références obsolètes de clés/noms (les tests du registre assertent que
   chaque méthode `JOBS` se résout).
3. Si votre PR touchait `flows/` (l'expérience abandonnée de paquet scindé) :
   ce répertoire a disparu, portez votre changement sur `core.py` + le module
   domaine.

---

## Visite architecturale (10 minutes)

1. **`src/main.rs`** — une CLI à 80+ commandes. Chaque branche `match` est une
   commande (`detect`, `mtk-flash`, `mtk-crash-brom`, `qcom-firehose`,
   `spd-format`, `odin-pit`, ...).
2. **`src/usb.rs`** — trouve les appareils par VID/PID, donne les endpoints
   (plus des `port_numbers` stables pour un adressage à l'épreuve de la
   ré-énumération).
3. **`src/odin.rs`** — mode download Samsung (protocole Odin 3
   rétro-conçu, dérivé de Heimdall). Lit/écrit le PIT, flashe les partitions
   (y compris le multiplexeur de session persistant `odin-agent`).
4. **`src/mtk*.rs`** — BROM MediaTek (`0e8d:0003`) → preloader (`0e8d:2000`) →
   handshake Download Agent, parsing scatter, travail sur partitions GPT, clés
   SLA, exploits BROM, crash-to-BROM. ⚠️ Convention PID au style mtkclient :
   `0003`=BROM, `2000`=preloader — ne les inversez pas.
5. **`src/qualcomm/`** — handshake Sahara (EDL) et sessions Firehose.
6. **`src/spd.rs`** — BSL Spreadtrum/UNISOC : téléchargement FDL, format,
   FRP, sauvegarde, extraction/packing PAC.
7. **`src/flows.rs`** — le **cœur de l'app**. Les lignes `flow!(key, label, job, mode)`
   construisent le registre `FLOWS` / `JOBS` / `MODES` (~280 lignes, 13 jobs,
   9 modes dont `SPD`). `python/core/core.py` ne fait que le refléter pour la
   recherche GUI.
8. **`python/core/devices.py`** — identité multi-appareil. Clés stables
   (`adb:<serial>` → `usb:<port-path>` → fallback volatile), `list_devices()`,
   `resolve_usb_target()`, et le thread-local `device_scope()` qui porte le
   téléphone choisi dans les résolveurs.
9. **`python/gui/qt_app.py`** — construit toutes les sections (Samsung / MTK /
   QC / SPD / Batterie / Réseau / Paramètres) et les workbenches à sous-onglets,
   plus le sélecteur d'appareil par opération et le verrou d'exécution par
   appareil.

### Flux de données

```
clic sur bouton
  → _choose_device(job, mode)          # silencieux pour 0-1 téléphones correspondants, sinon sélecteur
  → _run_ops_flow(job, mode, method, name, device_key)
  → _flow_start(key) par appareil + device_scope(key) + ctx["device_key"]
  → core.flow_for(...) -> Flow (liste de Steps)
  → chaque Step s'exécute dans un thread worker, appelant bridge._run([...])
  → bridge lance target/release/flashpilot-bridge ...
  → Rust fait l'I/O USB, affiche JSON/texte
  → Python parse + émet les signaux _ui.line() (taggés [device-key])
  → GUI met à jour console / statut / progression en toute sécurité
```

---

## Comment ajouter un flux

La feature la plus simple à livrer. Ouvrez `src/flows.rs` et ajoutez une ligne :

```rust
flow!("my_method", "My method", "Remove FRP", "ADB"),
```

La clé est en snake_case court (sans préfixe `flow_`). Python la découvre
automatiquement via `bridge.flow_list()` et le drill-down job/mode/méthode de
l'interface la récupère automatiquement ; l'exécution passe par
`flashpilot-bridge flow-run my_method`.

Puis (seulement si du travail de protocole bas niveau est nécessaire) ajoutez la
commande bridge dans `src/<concern>.rs` + `src/main.rs`. Le câblage job/mode est
déjà dans la ligne de flux.

C'est tout — le flux apparaît dans le dropdown/sous-onglet de la GUI
automatiquement et est aussi accessible depuis la CLI. **C'est la zone à plus
forte valeur / plus facile d'accès.**

> Utilisez `log(...)` dans les étapes pour la sortie console, `ctx` pour l'état
> à transmettre entre étapes, et `bridge._run(...)` pour tout ce qui touche le
> binaire Rust. Gardez les étapes coopératives avec `cancel_requested()`
> lorsque c'est pertinent pour que Stop fonctionne (l'annulation est par
> appareil — voir ci-dessous).

### Règles que tout flux doit suivre

- **Ne capturez jamais "le" appareil.** Acceptez `key=None` (portée thread
  ambiante) dans tout résolveur que vous ajoutez, et filtrez par celui-ci —
  voir `devices.device_key()`, `devices.match_key()`,
  `devices.device_scope()`. La GUI définit la portée par opération ; les appelants
  headless aussi.
- **Les noms de job sont verbe-d'abord** (`Remove FRP`, `Flash Firmware`,
  `Unlock Carrier`). **Les clés de flux sont en snake_case court**
  (`adb_frp`, pas `flow_adb_frp`) ; le seul alias historique (`fastboot_read`)
  a été supprimé — n'ajoutez pas d'alias.
- **La convention de PID MTK est au style mtkclient** : `0e8d:0003` = BROM
  (tenu), `0e8d:2000` = preloader. Rust, Python, libellés GUI et docs doivent
  tous être d'accord.
- **Les écritures EXPERIMENTAL** (Knox/IMEI/QCN/eMMC) passent par
  `experimental.check_gate_strict()` avec un ack par exécution — un ack stocké
  ne doit jamais passer automatiquement. Gâtez-les côté GUI via
  `_EXPERIMENTAL_FLOW_MAP` + le motif repliable ambre sur la page puce
  propriétaire (jamais une page LAB globale).
- **Les cibles bridge sont volatiles** (`vid:pid@bus:addr` change à la
  ré-énumération). Résolvez de nouveau depuis la clé stable avant d'ouvrir les
  sessions (`devices.resolve_usb_target()`) ; épinglez odin4 avec
  `-d /dev/bus/usb/BBB/AAA`.

---

## Ajouter un nouveau protocole USB / commande Rust

1. Ajoutez votre module sous `src/` (ex. `src/myproto.rs`).
2. Ajoutez `mod myproto;` dans `src/main.rs` et une nouvelle branche `match` +
   ligne d'usage.
3. Renvoyez `Result<T>` via `crate::error` et utilisez `serde_json` pour une
   sortie structurée.
4. Exposez-le depuis Python dans `python/core/bridge.py` comme wrapper autour de
   `_run([...])`.
5. Construisez un `Flow` dans `core.py` qui l'appelle (respectez les règles de
   flux ci-dessus).
6. Ajoutez un test si possible — les tests unitaires vivent dans `src/*.rs`
   (`#[test]`) et `tests/`.

**Hygiène protocolaire :** citez votre source (forums, write-ups en clean-room,
autres projets OSS) dans la docstring du module. Nous n'incluons pas de blobs
propriétaires — seulement l'implémentation du protocole.

---

## Directives GUI

- **PyQt6 uniquement.** Pas d'autres bindings Qt, pas de dépendances UI
  supplémentaires (voir `requirements.txt`).
- Respectez le langage visuel existant : `_btn_ghost()`, `_btn_primary()`,
  `_card_qss()`, `SectionTitle`, couleurs de thème `C[...]`, `FlowLayout` pour
  les grilles de boutons.
- **Tokens de thème, pas d'accent brut :** les remplissages peuvent utiliser
  `C['accent'/'grad_a'/'grad_b']`, mais les anneaux de focus, les bordures
  d'onglet sélectionné et les cases à cocher DOIVENT utiliser le neutre
  `C['focus_ring']` / `C['sel_border']` — sinon les thèmes d'accent rouge
  (Crimson, Sunset) fuient du rouge dans les états de focus. Ne codez jamais en
  dur d'hex pour le chrome.
- **Règle des threads :** le travail d'arrière-plan va dans `threading.Thread` ;
  les mises à jour GUI ne passent que par les signaux `self._ui.*`
  (`.line`, `.status`, `.toast`, `.ui`, `.progress`).
- **Animations :** `Motion.shake()` / `Motion.rubber()` sont mutuellement
  exclusifs par widget (gardés par `_anim_lock`) — ne lancez jamais les deux
  simultanément ou les sites d'appel doivent sérialiser via
  `QTimer.singleShot`. Aucun ne doit laisser `setFixedSize`, des bordures
  restylées, ou des layouts désactivés derrière ; `cleanup()` restaure tout.
- Gardez les lignes UI longue durée scrollables — les pages puce
  encapsulent le contenu dans un `QScrollArea` pour ne jamais écraser sur les
  petites fenêtres.
- Les nouveaux sous-onglets réutilisent `SamsungSubTabs` + un `QStackedWidget`
  (voir `_build_chip_ops_section`).
- Les boutons d'action sont `NoFocus` (pas d'anneau de focus collant) ; les
  pilules d'onglet à bascule gardent le style `checked` pour l'état actif.

---

## Tests

```bash
cargo test                      # tests unitaires Rust (incl. mapping d'étage MTK, SLA, PIT)
.venv/bin/python -m pytest tests/   # suite Python (actuellement 173 passés, 4 ignorés)
```

Disposition de la suite de tests :

- `tests/test_frp_flow.py` — exécution `Flow`/`Step` + annulation coopérative + verrou d'exécution par appareil.
- `tests/test_mtk.py` — logique MediaTek (scatter, DA, helpers de boot-stage, attente/crash-retry BROM).
- `tests/test_devices.py` — clés d'appareil stables, filtrage de téléphone, résolution de cible, annulation par portée.
- `tests/test_carrier_lock.py` — verdict de verrou SIM + gating de patch MTK + découverte DA.
- `tests/test_odin_safety.py` — vérification tar.md5, gates BL, négociation des flags odin4.
- `tests/test_pit.py` — parsing PIT Samsung.
- `tests/test_bridge_io.py`, `tests/test_fus.py` — I/O bridge + téléchargeur de firmware Samsung.

Si vous ajoutez de la logique Rust, ajoutez des modules `#[test]` dans le même
fichier. Si vous ajoutez des flux, ajoutez un pytest qui exécute le flux avec
un contexte fake/offline quand possible. Les nouveaux résolveurs doivent
accepter `key=None` ; les nouveaux tests doivent couvrir le filtrage
multi-appareils (voir `test_devices.py`) plutôt qu'assumer un seul téléphone.

---

## Checklist de pull request

- [ ] `cargo build --release` passe.
- [ ] `cargo test` passe (ou notez pourquoi non exécutable).
- [ ] `.venv/bin/python -m pytest tests/` passe.
- [ ] Nouveau flux : câblé dans `JOBS` (job + mode) pour être accessible dans la GUI.
- [ ] Nouveau résolveur : accepte `key=None` (portée ambiante) et couvert par un test multi-appareils.
- [ ] Nouvelle commande Rust : ajoutée au texte d'usage de `main.rs` + au wrapper `bridge.py`.
- [ ] Changements GUI : couleurs thémées (tokens de focus neutres !), mises à jour par signaux, layouts sûrs au scroll.
- [ ] Aucun secret/binaire/donnée identifiant un appareil ajouté au dépôt.
- [ ] README mis à jour dans la matrice de fonctionnalités si vous avez ajouté une capacité.

Gardez les PR ciblées. Une fonctionnalité ou un correctif par PR est idéal ;
référencez le numéro d'issue.

---

## Politique de support de plateforme (à lire avant de porter)

**Linux est la seule plateforme supportée.** Le développement, les tests
matériels et les releases ciblent Linux. Les issues Windows/macOS seront
fermées comme non supportées — à moins qu'elles n'arrivent sous forme de code,
comme suit.

**Pourquoi :** `odin4` est Linux-only ; Windows USB nécessite des drivers par mode
(Zadig / QDLoader / Samsung) qui ne peuvent pas être débogués à distance ;
macOS nécessite la signature/notarisation pour une demande négligeable. Voir la
section « Platform support » du README pour le raisonnement complet et
l'invitation ouverte à l'argumenter.

**Comment contribuer à un port quand même (la forme acceptée) :**

1. N'éparpillez PAS de vérifications `sys.platform` dans les flux ou la GUI.
2. Ajoutez `python/core/platform.py` avec des fonctions backend —
   `open_file_manager()`, `detach_kernel_drivers(target)`,
   `usb_device_path(bus, addr)`, `needs_udev_setup()`,
   `kernel_module_loaded(name)` — Linux implémenté, les autres levant
   `NotImplementedError` avec un message utile.
3. Migrez les sites d'appel Linux-only existants (`xdg-open`, `rmmod cdc_acm`,
   `/dev/bus/usb`, `lsmod`, docs udev) vers lui, un PR par groupe de site d'appel.
4. Un PR backend Windows/macOS doit inclure : l'implémentation backend, les
   mises à jour de docs, et des preuves de test CI ou manuel vérifié par le
   mainteneur. L'équipe cœur ne possède pas de matériel de test non-Linux —
   les PR de port vivent ou meurent selon la capacité de leur auteur à les prouver.

**PySide6 vs PyQt6 :** la migration vers PySide6 (LGPL, compatible MIT — PyQt6
est GPLv3) est souhaitée mais bloquée par la couverture de smoke-test GUI. Si
vous vous en chargez : convertissez mécaniquement `pyqtSignal→Signal`,
`pyqtProperty→Property`, `PyQt6.sip→shiboken6`, étendez les smoke tests de
fenêtre/picker/guard hors-écran dans `tests/`, et gardez le comportement
pixel-identique. Discutez d'abord dans Discussions.

## Feuille de route & idées

Nous serions ravis que des contributeurs portent ces idées :

- **Ports & empaquetage :** Flatpak / AppImage / AUR, matrice CI (distros Linux),
  flux de release `pip`/`cargo`.
- **MediaTek :** plus de variantes de DA, cas limites de scatter, dumps de
  sauvegarde eMMC/UFS, nouvelles entrées `hw_code` dans `CHIP_NAMES` (avec une
  source citée — ne devinez jamais les codes hex).
- **Qualcomm :** cas limites rawprogram/patch XML, combos fh-loader, plus de PIDs
  de puces.
- **Samsung :** charges utiles supplémentaires de mode download HID par SoC,
  amélioration UX multi-partition Odin.
- **Multi-appareil :** onglets console par appareil/progression, granularité STOP
  par appareil (STOP diffuse actuellement), corrélation `port_numbers` pour les
  hubs exotiques.
- **Nouvelles sections :** FRP TEE/clavier, profils carrier (dé-bloating),
  utilitaires EDL-only.
- **Communauté :** traductions, wiki de compatibilité d'appareils, catalogue
  d'archives firmware reproductible.
- **Sécurité :** mode dry-run, sauvegarde automatique pré-flash, docs de
  récupération de brick.

---

## Contributeurs

Toute personne qui aide — code, docs, rapports d'appareils ou combo testé — est
listée ici et célébrée. Ouvrez un PR en vous ajoutant (ordre alphabétique par
nom d'utilisateur, une ligne de lien) :

```md
- [@your-github](https://github.com/your-github) — ce que vous avez fait
```

Les premiers contributeurs à ce projet l'ont rendu réel. Soyez le suivant.

---

## Questions ? Ouvrez une discussion/issue. Merci d'aider à faire avancer le logiciel
de flash libre et ouvert sur Linux. 🚀