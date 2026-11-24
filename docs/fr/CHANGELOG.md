# Journal des modifications

Language switcher: [English](../../CHANGELOG.md) · **Français**

## 1.2.2 (mises à jour auto, 10 langues, Rockchip + multi-appareils sûr pour modem)

*Consolide les notes du cycle de développement 1.2.2 → 1.3.2 — tout ce qui est
livré depuis 1.2.1.*

### Mises à jour auto et Nouveautés (nouveau)

- Les mises à jour s'installent automatiquement : le `.deb` téléchargé
  s'installe via sudo en arrière-plan, l'application redémarre, et une fenêtre
  unique « ce qui a été ajouté ou modifié » affiche le changelog de la nouvelle
  version au premier lancement (l'invite manuelle « Install Now » reste
  présente quand l'installation auto est désactivée dans Paramètres → Mises à
  jour).

### Interface en 10 langues + changement de langue à chaud (nouveau)

- Toute l'interface est livrée en 10 langues supplémentaires (Français,
  Español, Deutsch, 简体中文, Русский, Português, 日本語, العربية, हिन्दी,
  Türkçe) : paramètres, tuiles d'appareils, pages et chaînes de console.
- Changer la langue de l'interface est immédiat — sans redémarrage ; les mises
  en page se calent sur les métriques réelles des polices afin que les
  traductions longues passent à la ligne au lieu de rogner les contrôles.
- Catalogues de traduction JSON à base de clés avec vérification de couverture ;
  la CI fait des smoke-tests des catalogues installés.

### Rockchip + détection plus intelligente (nouveau)

- Nouvelle page de marque Rockchip : famille RK28xx–RK35xx via le mode
  fastboot.
- La détection identifie modèle, marque et format — pas seulement la puce.
- Chaque étape de flashage est interceptée (parité TFT) : MediaTek
  BROM/preloader/DA sur l'ensemble complet des PID d'étape et VIDs OEM (y
  compris le VCOM preloader 0x2000/0x2001), la famille étendue des PID de
  téléchargement Qualcomm EDL, l'union des PID de téléchargement SPD, et les
  diagnostics Qualcomm HS-USB nommés comme un mode à part.
- Le badge de mode suit l'appareil SÉLECTIONNÉ et nomme le protocole USB réel
  (ADB/MTP/PTP/DIAG/storage/RNDIS) au lieu de OTHER : seuls les PIDs de
  flashage revendiquent le libellé MediaTek bas niveau, Qualcomm EDL conserve
  sa puce de badge, et les chutes par sous-chaîne 'MEDIATEK'/'download' sont
  corrigées.

### FRP Motorola (nouveau)

- Chaîne FRP fastboot CVE-2016-10277, provisionnement QR par fausse connexion
  avec DPC maison (TestDPC / Device Policy / Adobe), FRP fastboot échelonné
  avec cycles flash + redémarrage, et cycle ADB en bootmode usine.

### Chemins de moteur réels (nouveau)

- Vrais chemins de flash, FRP et verrouillage MTK/QCOM/Unisoc/Samsung dans le
  cœur Rust.
- odin4 a disparu : le moteur Odin Rust natif gère tout le pipeline tar, PIT
  et chaque classe de problème odin4 connue ; usbmuxd/lockdown Apple migrés
  vers Rust ; le cœur est uniquement Rust (tous les replis Python
  appareil/protocole supprimés).

### ADB sûr pour modem (corrigé)

- Les chemins poll/monitor/display sont zero-touch (`adb-devices --no-probe`) :
  aucune ouverture/claim/handshake depuis les boucles — les modems USB cessent
  de se ré-énumérer à chaque cycle (vérifié en direct : 114 cycles de poll
  silencieux sur un modem MSM8916).
- Les conflits de claim se délèguent en échelle : natif → transport serveur
  Rust (série explicite) → binaire hôte → rescue kill (dernier recours), afin
  que les ops ADB réussissent pendant que le serveur système tient l'interface.
- Correctif de fusion USB-ADB (les chaînes de ligne sont analysées, donc les
  lignes portent réellement l'état ADB), secours du détenteur occupé +
  réessai transitoire + état occupé honnête, garde babble/débordement,
  commande d'isolation du test de claim, valeurs CNXN adb modernes, et les
  coins QCOM/MTK affichent la superposition ADB comme les branches sœurs.

### Fiabilité multi-appareils (corrigé)

- Sélection avec settle-retry : chaque lanceur d'outil réessaie une fois après
  2,5 s quand un scan manque transitoirement un appareil en ré-énumération, au
  lieu de refuser avec « no device » alors que la GUI l'affiche connecté.
- L'AUTH ADB garde le SHA-256 en jeu à travers les tours de token (tours
  impairs SHA-256, pairs SHA-1), donc une signature perdue au tour 1 ne mure
  plus en faux « not authorized » ; `_wait_for_adb` tolère les échecs de scan
  transitoires.
- Liaison d'identité cible : un appareil remplacé occupant un bus:addr
  réutilisé est refusé (vérification série zero-touch) — le transport ne suit
  jamais un autre téléphone.
- Changement de liste d'appareils : la reconstruction de la barre de connexion
  réessaie quand le deuxième scan perd un appareil, changer d'appareil ne
  retombe plus sur le premier téléphone, et les outils ADB se rabattent sur la
  ligne daemon ADB quand la sélection USB manque (« montre connecté mais les
  actions disent pas d'adb »).
- Classification + sélecteur d'appareils : les appareils non correspondants
  signalent USB au lieu d'un mauvais libellé MTP, et une sélection USB manquée
  propose le sélecteur de ligne daemon (« Run on this device » / « Cancel »)
  au lieu de refuser.

### Résultats honnêtes et finitions GUI (corrigé)

- Les flux FRP exigent des flags vérifiés et un vrai code de sortie de shell ;
  une sortie de pont non nulle lève un échec avec la fin du journal — plus de
  faux toasts « completed ».
- GUI : puces de job par ligne, mémoire de fenêtre, plafond de toasts,
  navigation clavier, STOP conscient de l'appareil (un job annule cet
  appareil), kg_unlock déplacé vers un thread de travail (les chaînes de
  30 secondes ne figent plus la fenêtre), splash suit le vrai build, les pages
  différées restent réessayables, les toasts dégagent la barre supérieure.

### Sécurité et robustesse

- Sorties privées par défaut, noms temporaires à l'épreuve des symlinks,
  vérifications de symlinks.
- Vérification du firmware après écriture par défaut + porte de modèle +
  correctifs numériques.
- FRP : le certificat de signature DPC est lu nativement et le checksum de
  provisionnement est corrigé.
- Harnais de test matériel HIL : régressions multi-appareils / remplacement
  d'appareil / tempête USB sur du vrai matériel ; tests de backoff du moniteur
  ADB rendus déterministes.
- Page d'accueil publique (`website/`) avec la matrice de capacités et la
  console de protocoles.

## 1.2.1 (version stable)

### Prise en charge multi-appareils (nouveau)

- Branchez plusieurs téléphones : la barre de connexion liste chacun (modèle ·
  série · transports) ; cliquez sur une ligne pour l'inspecter.
- Chaque opération demande à quel téléphone elle s'applique quand plusieurs
  correspondent (silencieux pour 0–1 correspondance). Les lignes de console
  portent une étiquette `[device-key]`.
- Une opération par appareil : différents téléphones peuvent flasher en
  parallèle ; le même téléphone se sérialise toujours. Le STOP global diffuse
  à tous les lanceurs.
- Identité stable (`python/core/devices.py`) : `adb:<serial>` → `usb:<port-path>`
  → repli volatil. Les cibles sont ré-résolues avant l'ouverture des sessions,
  donc la ré-énumération USB n'orpheline plus un flash (`usb device Fail`).
- Liste d'appareils téléphone uniquement : hubs, HID, webcams et lecteurs de
  cartes sont filtrés.
- Nouveau mode de transport `SPD` + flux de détection Qualcomm/SPD en
  lecture seule.

### Per-chip EXPERIMENTAL (nouveau)

- Samsung `Knox / Warranty`, Qualcomm `QCN / Modem`, par puce `IMEI Repair /
  Change`, `eMMC / UFS` — accordéons ambre sur la page de puce propriétaire
  (pas de page LAB globale). Case d'engagement de propriété à chaque exécution ;
  le changement d'IMEI exige en plus de saisir `I UNDERSTAND`. Journalisé ;
  les acks persistés ne passent jamais automatiquement (`check_gate_strict`).

### MTK BROM (corrigé + amélioré)

- **Correspondance PID/étape corrigée** selon la convention mtkclient
  (`0e8d:0003`=BROM, `0e8d:2000`=preloader) dans Rust, Python, libellés GUI,
  journaux et docs.
- Nouvelle commande de pont `mtk_crash_brom` + flux `MTK crash preloader into
  BROM` (enregistré sous MTK BROM).
- `_wait_mtk_brom_target()` préfère le BROM tenu stable au lieu de la fenêtre
  preloader ; la découverte DA refuse les binaires tronqués (<1 Ko).

### Odin / flashage (renforcé)

- `_prepare_download_session()` : détachement du pilote noyau + 3× retry de
  handshake à travers la ré-énumération ; tous les PIDs Odin acceptés ; cache
  PIT réchauffé avant flash.
- odin4 épinglé avec `-d /dev/bus/usb/BBB/AAA` + un retry automatique unique
  sur perte USB ; trailer `.tar.md5` ancré en fin de fichier (streaming, sans
  lecture RAM complète).
- Journaux de flash intelligent natif par partition MB/s + ETA.

### Renforcement de robustesse (piloté par revue)

- Sahara : commande HELLO/version/mode/packet-size validée à l'analyse (avant :
  tout blob ≥32 octets était de confiance) ; l'auto-contrôle du format de
  transfert fait maintenant un aller-retour des structs au lieu de perdre des
  octets ; les échecs de fermeture sont journalisés ; le détachement s'exécute
  avant le claim ; le handshake rapporte les résultats transfert/fermeture/reset
  en JSON au lieu de les écarter (le reset est explicite et visible).
- Auth ADB : backoff exponentiel borné entre les tours de token ; pause de
  génération de clé unique annoncée au lieu de sembler bloqué.
- MTK : la taille de paquet configurée atteint réellement la session DA
  (était calculée puis perdue ; sessions codées en dur 64 K), bornée à
  512 o–1 Mo.
- Sauvegardes de sécurité : les échecs affichent une bannière immanquable avec
  temps écoulé et indice STOP (contrat inchangé : ne bloque jamais
  l'opération).
- Portes expérimentales : flux iCloud + Pixel migrés vers des acks stricts par
  exécution ; les tokens d'ack GUI sont maintenant comptés par fonctionnalité
  avec expiration (pas de fuite inter-fonctionnalités, pas d'acks perdus, pas
  d'autorisations périmées).

### Correctifs GUI

- Bordures rouges de la barre supérieure + rétrécissement des boutons tracés
  aux animations shake/rubber concurrentes et aux anneaux de focus teintés
  d'accent : animations sérialisées avec `_anim_lock` + nettoyage complet ;
  nouveaux tokens de thème neutres `focus_ring`/`sel_border` (les accents rouges
  ne peuvent plus fuiter dans le focus).
- `os.system()` → `subprocess` pour la reconstruction du pont / l'ouverture du
  dossier de journaux.
- Stub SPD dupliqué « Enable ADB », mauvais gating expérimental de
  `fastboot_unlock`, chemin mort FUS→slot AP, et émission `finished`
  manquante corrigés. La surface expérimentale morte LAB/Knox/QCN/PAC a été
  retirée.

### Restructuration

- `python/core/frp.py` (fichier dieu) → `python/core/core.py` (registre + flux) ;
  `frp.py` est maintenant FRP uniquement. La séparation morte
  `python/core/flows/` a été retirée.
- Noms de jobs verbe d'abord (`Remove FRP`, `Flash Firmware`, …) ; une clé
  canonique snake_case par flux ; casse du nom d'affichage normalisée.

### Docs

- Captures d'écran fraîches (`docs/samsung.png`, `mtk.png`, `spd.png`),
  README réécrit (points forts/matrice/layout), architecture CONTRIBUTING +
  règles de flux, ce changelog.

### boot.img + AVB (moteur natif unique)

- Nouveau moteur de chirurgie d'image dans le pont Rust (`src/imgtools.rs`) :
  analyse de l'en-tête boot Android, scan cpio newc, patchage de propriétés
  (pad-in-place ou croissance style magiskboot avec réécriture d'en-tête),
  gzip déterministe (mtime=0, niveau 9), flags AVB vbmeta.
  CLI `boot-info` / `boot-patch-adb` / `vbmeta-patch`.
- Le repack Python `spd_adb` + `core._patch_vbmeta_flags` délèguent avec repli
  local (signatures et contrats de retour inchangés).
- Le travail d'équivalence a corrigé deux vrais bugs : le splice de croissance
  était en désaccord avec l'alignement du lecteur de 2 octets (corrompant
  chaque entrée suivante — les deux implémentations), et le re-patchage
  grossissait de `\n` à chaque exécution (les deux côtés sont maintenant
  idempotents). Les octets gzip sont volontairement exclus de la parité (les
  implémentations zlib diffèrent) ; le contenu décompressé, les tailles et les
  champs correspondent.
- 6 tests unitaires Rust + 9 tests inter-implémentations.

### PAC (moteur natif unique + actions GUI câblées)

- Nouveau moteur SPD PAC dans le pont Rust (`src/pac.rs`) : parse/extract/pack
  avec la disposition YGDP, constructeurs d'en-tête/slot partagés désormais
  aussi utilisés par l'écrivain `spd-readback` (sortie octet pour octet
  identique ; ses noms de slot historiquement doublés sont mis en quarantaine,
  non propagés). CLI `pac-parse` / `pac-extract` / `pac-pack`.
- Python `pac.*` délègue avec repli local ; nouveaux `flow_pac_extract` /
  `flow_pac_pack` (fichier uniquement, entrées env style ofp) enregistrés dans
  FLOWS et mappés dans le dispatcheur GUI — les boutons PAC précédemment morts
  fonctionnent maintenant.
- Les tests d'équivalence ont détecté et corrigé un vrai bug : le packer local
  perdait silencieusement la chaîne produit (écriture slice-copy) ; plus des
  gardes de débordement u32 avec des messages identiques des deux côtés.
- 5 tests unitaires Rust + 7 tests inter-implémentations (aller-retour dans les
  deux sens, parité sanitize incl. collision de répertoire, cartographie
  d'erreurs).

### PIT (moteur natif unique)

- Nouveau moteur Samsung PIT dans le pont Rust (`src/pit.rs`) : parse
  (disposition 28/132), chaînes en-tête/modèle, normalisation des noms,
  recherche, scan de chevauchement, validation forensique + verdicts de santé
  — messages, résumés et verdicts octet pour octet identiques à
  l'implémentation Python sur des dumps réels et cas limites (incluant la
  parité Python-`repr` pour les noms parasites).
- CLI `pit-parse` / `pit-health` / `pit-find` / `pit-overlaps` / `pit-model` ;
  les chemins Python `pit.*` sur octets bruts délèguent avec repli local quand
  le binaire est absent (contrats préservés : ValueError/None/jamais-
  d'exception). Les chemins objet en mémoire et les aides d'affichage restent
  locaux et rapides ; les règles partagées sont figées par 11 tests
  d'équivalence inter-implémentations.
- 8 tests unitaires Rust (vecteurs de disposition, table de normalisation,
  classification de chevauchement méta, formes de résumé/human-size).

### ADB (transport natif, sans platform-tools)

- Nouveau client ADB natif dans le pont Rust (`src/adb.rs`) : transport USB
  (255/66/1) avec détachement du pilote noyau, handshake CNXN,
  AUTH RSA-SHA256/SHA-1 (réutilise `~/.android/adbkey`, généré s'il manque),
  services `shell:` et `sync:` (STAT/RECV/SEND).
- `adb-devices` conserve son contrat de ligne `adb devices -l` depuis un scan
  natif (`device` / `unauthorized` / `no permissions`) ; `adb-shell` prend un
  série (`-` = premier autorisé), plus les nouveaux `adb-pull` / `adb-push`
  épinglés par série.
- Python : `bridge.adb_shell()` résout série explicite > portée ambiante >
  premier série autorisé (ADB multi-appareils est maintenant épinglé sur la
  cible) ; `adb.py` délègue au pont ; les pull/push de sauvegarde/restauration
  EFS passent par le pont au lieu d'appels `adb` système non épinglés.
  `has_adb()` signifie maintenant « pont construit ».
- 6 tests Rust (framing, bannière, signature/vérification PKCS#1, aller-retour
  DER, blob de clé publique octet pour octet vs clé adb système) + 9 tests
  Python.

### Fastboot (transport natif + Motorola universel)

- Nouveau transport USB fastboot natif dans le pont Rust (`src/fastboot.rs`) :
  `fastboot-devices` (JSON) + `fastboot-cmd <vid:pid@bus:addr> <ms> <cmd…>`
  pour la phase de commande (getvar/oem/erase/reboot) avec détachement du
  pilote noyau. L'échec côté appareil s'affiche comme `FAILED (remote: …)`
  avec code de sortie 0, correspondant à la forme de transcript du binaire
  système (y compris les valeurs `getvar` solitaires qui voyagent dans le
  paquet OKAY sur les bootloaders Moto MBM).
- Les aides partagées Python (`_fastboot_run`, `_wait_fastboot`,
  `_fastboot_getvar`) sont natives d'abord avec repli binaire système ; les
  commandes de phase DATA (flash/boot/…) utilisent toujours le binaire système,
  et la liste côté hôte `devices` est servie depuis la détection native.
  Tout le trafic fastboot est maintenant épinglé sur la cible
  (`vid:pid@bus:addr`), fermant le danger téléphone-incorrect sans `-s`.
- Nouveaux flux Motorola à l'échelle de la marque (`moto_frp_adb`,
  `moto_frp_fastboot`, `moto_oem_unlock_token`) : réinitialisation de
  provisionnement ADB, flux officiel de token de déverrouillage avec lecture
  d'état de verrou + réinitialisations de session, lecteur de token en lecture
  seule. Affichés sous Motorola → All Motorola / Lenovo (universel) et chaque
  modèle Moto ; URL du portail de déverrouillage corrigée (l'ancien
  `motorola.com/unlockbootloader` est mort).
- `python/core/fastboot.py` (Pixel) et `usb_watch.py` (scraping lsusb)
  migrés vers le pont ; 7 nouveaux tests `tests/test_fastboot_native.py`.