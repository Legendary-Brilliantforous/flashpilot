# Plan intensif d'amélioration de l'UI FlashPilot

Language switcher: [English](../../ui-improvement.md) · **Français** · [Español](../es/ui-improvement.md) · [Deutsch](../de/ui-improvement.md) · [简体中文](../zh/ui-improvement.md) · [Русский](../ru/ui-improvement.md) · [Português](../pt/ui-improvement.md) · [日本語](../ja/ui-improvement.md) · [العربية](../ar/ui-improvement.md) · [हिन्दी](../hi/ui-improvement.md) · [Türkçe](../tr/ui-improvement.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## Objectif
Transformer la GUI PyQt6 d'un monolithe fonctionnel en atelier poli, maintenable et performant, tout en préservant tous les flux adossés à Rust et le comportement multi-appareils.

## État actuel
- `python/gui/qt_app.py` (~15k LOC) est une fenêtre monolithique unique.
- Le système de thème (`theme.py`) est centralisé, mais le QSS est large et dupliqué par endroits.
- La barre de connexion, le rail de nav, les pages par chip, la console et les paramètres sont dans un seul fichier.
- Une forte identité visuelle existe déjà (cartes glass, 10 accents, scène câble).

## Principes
1. Aucune logique de protocole en Python ; l'UI se contente d'afficher et d'appeler le pont.
2. Garder Rust comme source de vérité pour les flux/jobs/modes.
3. Améliorer la réactivité : déplacer le travail lourd hors du thread UI, réduire le churn de widgets.
4. Accessibilité : navigation clavier, anneaux de focus, libellés pour lecteurs d'écran.
5. Maintenabilité : découper `qt_app.py` en modules par fonctionnalité.

## Phase 0 — Coque de fenêtre, logo, écran d'accueil (nouveau)
- Remplacer le logo actuel par une marque vectorielle/SVG professionnelle (variantes monochrome + accent, 16/32/64/128/256 px + .ico/.icns).
- Écran d'accueil : marque animée, étapes de progression (init du pont Rust, scan des appareils, chargement du thème), version, sans scintillement ; fondu entrée/sortie 200 ms.
- Rendu de fenêtre : fenêtre frameless translucide compatible avec l'alpha du compositeur, coins arrondis, ombre portée, mise à l'échelle DPI-aware, mémoire de placement multi-écran.
- Fluidité : activer `Qt AA_UseHighDpiPixmaps`, définir le format de surface (OpenGL/RGBA), animations respectueuses du vsync, réduire le chamboulement de layout ; cible 60 fps pour les interactions.
- Branding : logo cohérent dans la barre de titre, la barre des tâches, la boîte « À propos », l'installateur.
- Colonnes de coque redimensionnables : la frontière **panneau d'appareils | page** est un séparateur horizontal draggable (par défaut 232 px, draggable 228–420 px, mémorisé dans `layout/device_panel_width`). La page garde sa largeur naturelle et vit dans une zone de défilement sans cadre, pour que la compresser fasse défiler latéralement au lieu de reflow ses onglets/grille ; la largeur du panneau est conservée au redimensionnement de fenêtre jusqu'à ce que l'utilisateur le glisse. _Décision (utilisateur) : précédemment un `setFixedWidth(232)` strict._

## Phase 1 — Découpage architecture (aucun changement visuel)
- Extraire les constructeurs de page dans `python/gui/pages/` :
  - `samsung.py`, `mtk.py`, `qc.py`, `spd.py`, `battery.py`, `network.py`, `settings.py`, `quick.py`.
- Extraire les widgets partagés dans `python/gui/widgets/` : `metric_card.py`, `collapsible.py`, `console.py`, `device_picker.py`.
- Garder `qt_app.py` comme coque : chrome de fenêtre, nav, routage, signaux.
- Critère d'acceptation : l'app démarre, tous les onglets s'affichent, les tests passent.

## Phase 2 — Performance
- Virtualiser la liste d'appareils et le journal de console (`QAbstractListModel` + `QListView`) pour éviter la création O(n) de widgets.
- Regrouper les mises à jour de log (flush toutes les 50 ms ou 100 lignes).
- Mettre en cache le QSS rendu par thème ; régénérer seulement au changement d'accent.
- Chargement paresseux des pages lourdes (construction à la première visite).
- Critère d'acceptation : 10k lignes de log sans gel UI ; défilement à 60 fps.

## Phase 3 — Finition visuelle
- Jetons de design : échelle d'espacement (4/8/12/16/24), échelle de rayon, élévation.
- Élévation/ombre de carte cohérentes ; états hover/focus.
- Motion : fondu de page 120 ms, échelle de pression de bouton, glissement de toast.
- Système d'icônes : remplacer les emoji par des icônes SVG (glyphes de marque).
- États vides et squelettes pour la détection d'appareil.
- Mode haut contraste + bascule mouvement réduit.

## Phase 4 — Flux UX
- Boîte de dialogue de sélection d'appareil unifiée avec recherche/filtre et badges de transport.
- Progression d'opération : liste d'étapes avec coches, ETA, annulation par appareil.
- Présentation des erreurs : cartes actionnables avec « réessayer / ouvrir la doc / copier le log ».
- Paramètres : recherchables, groupés, avec réinitialisation aux valeurs par défaut.
- Console : filtre par niveau/appareil, export, recherche.

## Phase 5 — Accessibilité & i18n
- Ordre de tabulation complet, focus visible, libellés de type ARIA.
- Raccourcis clavier documentés dans l'app.
- Extraction des chaînes pour les traductions (aucune chaîne utilisateur codée en dur dans les widgets).

## Phase 6 — Tests
- Tests smoke GUI avec pytest-qt (headless).
- Captures de régression visuelle pour chaque page/thème.
- Benchmarks de performance pour le rendu log/appareil.

## Livrables
- `python/gui/pages/*`, `python/gui/widgets/*`
- Système de jetons `theme.py` mis à jour
- `tests/test_gui_smoke.py`
- Mise à jour docs dans README/INDEX.

## Risques
- Monolithe de 15k LOC ; extraction incrémentale requise.
- Règles de threading PyQt ; garder toutes les manipulations de widgets sur le thread principal.
- Préserver le cadrage multi-appareils et la sémantique d'annulation.

## Première tâche suggérée
Extraire `_build_console` et `_build_conn_bar` dans `widgets/console.py` et `widgets/connection_bar.py` avec une API basée sur les signaux ; aucun changement de comportement.

## Phase 7 — Rendu flux & jobs (nouveau)
### Problèmes observés
- `_add_job_flows` aplatit tous les modes en une liste de boutons par job ; le mode n'est qu'en infobulle, ce qui porte à confusion.
- Boutons dupliqués entre pages (Quick, sections d'ops chip, onglets Unlock) avec un gating incohérent.
- Les boutons expérimentaux/destructifs ne se distinguent que par couleur/bordure ; pas de légende.
- Pas de recherche/filtre, pas de récemment utilisés, pas de favoris.
- Les longs libellés de flux débordent/se replient de façon imprévisible dans FlowLayout.
- Aucun groupement visuel par risque (lecture seule vs flash vs expérimental).

### Modèle de rendu proposé
- Navigation à trois niveaux **Job → Mode → Méthode** :
  - Gauche : liste des jobs (verbe d'abord, icônes).
  - Milieu : onglets de mode (ADB, MTP, …) avec compteurs.
  - Droite : cartes de méthode (nom, badge de risque, badge expérimental, infobulle).
- Source unique de vérité : `core.modes_for` / `core.methods_for` ; aucune liste dupliquée dans les pages.
- Déduplication globale par (job, mode, key) ; les pages chip filtrent par modes supportés au lieu de relancer `_add_job_flows`.
- États de carte de méthode : activée/désactivée selon les portes de capacité, en cours (spinner), dernier résultat (ok/fail).

### Ce qui doit bouger
- Déplacer la construction de boutons de `_add_job_flows` vers `widgets/flow_button.py` + `widgets/method_card.py`.
- Déplacer l'énumération mode/job dans un modèle `FlowRegistryView` (fin, sans logique) pour le binding UI.
- Déplacer la confirmation destructive/expérimentale dans un `ConfirmDialog` réutilisable.

### Ce qui doit fusionner
- Fusionner la page Quick et les pages d'ops chip pour utiliser le même widget `FlowBrowser` avec un filtre `modes`.
- Fusionner la gestion des avertissements expérimentaux dans le badge de carte + boîte de dialogue.

### Ce qui doit être supprimé / dédupliqué
- Supprimer les appels par page à `_add_job_flows` qui dupliquent les mêmes flux de job ; remplacer par un `FlowBrowser` filtré.
- Supprimer les instances dupliquées de `Flow` (même clé sous plusieurs modes) en groupant les modes sur la carte.
- Supprimer les en-têtes bruts `QLabel(job.upper())` au profit d'en-têtes de section avec compteurs.

### Nouvelles fonctionnalités
- La boîte de recherche filtre par nom et clé de job/mode/méthode.
- Favoris/récents persistés dans les paramètres.
- Légende de risque : lecture seule (vert), moyen (ambre), élevé (rouge), expérimental (ambre pointillé).
- Sélection par lot : cases à cocher pour mettre en file plusieurs méthodes (exécution séquentielle avec annulation par étape).
- Glisser-déposer pour réordonner les favoris.

### Critères d'acceptation
- Un navigateur de flux cohérent sur toutes les pages.
- Aucun bouton de méthode dupliqué pour le même (job, mode, key).
- La recherche filtre en < 50 ms pour 280 lignes.
- Les portes de capacité désactivent visuellement les méthodes avec une infobulle de raison.

### Phase 7 — état (implémenté jusqu'ici)
- **Forme choisie : mise à niveau en page.** Introduire le chemin de rendu unique maintenant et le mettre à niveau sur place — `FlowBrowser` (vue) + `MethodCard` (bouton) + `flow_meta` (routage/risque) — *sans* la navigation trois volets Job → Mode → Méthode pour l'instant. Les pages conservent leur layout actuel ; `_add_job_flows` construit les lignes et les rend via `FlowBrowser`, et les clics routent via `flow_meta.route_for`.
- **Modèle de risque dérivé** (`flow_meta.risk_for`, la seule source qu'un badge peut lire) : `experimental` = clé dans `_EXPERIMENTAL_FLOW_MAP` ; `high` = clé dans `_DESTRUCTIVE_CONFIRM` et donc **exactement les flux pour lesquels l'UI demande déjà confirmation** (un badge ne peut jamais revendiquer `high` sans boîte de dialogue, ni `read` sans être lecture seule) ; `read` = uniquement pour `READ_ONLY_JOBS` (`{"Read Device Info", "Detect Devices"}`) ; tout le reste, y compris les clés/jobs inconnus, bascule par sécurité vers `medium`.
- **Slice B1 — rendu de flux groupé (cette slice).** `FlowBrowser.set_rows` groupe maintenant ce qu'il rend, corrigeant les trois problèmes nommés :
  - L'en-tête de job est désormais `{"REMOVE FRP"} · 6` — le brut `QLabel(job.upper())` a gagné un **compteur** de méthodes (atténué avec le jeton `border_hi`, le nom garde le traitement existant 11 px / 800 / 1 px).
  - Dans chaque job, les cartes sont groupées par **mode de transport** derrière un petit sous-titre de mode (`— ADB`), au lieu d'une liste plate par job avec le mode seulement en infobulle. Les lignes arrivent mode-major depuis `_flow_rows`, donc une série de modes égaux forme une section ; aucun mode n'est jamais éclaté en cartes supplémentaires.
  - Chaque `MethodCard` peint un **bord gauche** sémantique (`ok` lecture seule, `warn` moyen, `err` élevé, `experimental` expérimental) composé par-dessus `_btn_ghost()`, pour que le risque soit visible d'un coup d'œil à côté de la légende existante. Les cartes expérimentales gardent leur bordure **pointillée** ambre — désormais possédée par `MethodCard.set_risk(level)` ; `set_state` reste inerte.
  - Inchangé par construction : l'ensemble de lignes rendu, la règle de déduplication (« premier mode gagne » par job), le texte du bouton (`btn_sha`), toutes les chaînes d'infobulle, le routage des clics, les surcouches confirm/expérimental et le registre de portes (`job=`/`mode=`, jamais `command=`). Seuls des widgets de groupement/libellé ont été ajoutés.
- **Golden régénéré délibérément ici.** `tests/ui_inventory_golden.json` a été reconstruit avec `REGEN_INVENTORY=1` dans cette slice. La **seule** différence est le **compteur de widgets** par page (les libellés de sous-titre de mode ajoutés ; +113 widgets répartis sur les cinq pages riches en flux). `gated_count`, `gated_unique_triples`, `gated_triples_sha256`, `core_flows`, `action_meta` et les `buttons` / `acts` / `btn_sha` de chaque page sont octet-identiques — le registre de portes et la surface de clic n'ont pas bougé.
- **Slice B2 — tableau de modèle d'appareil (cartes d'action verticales) (cette slice).** Les lignes d'action par modèle de la page modèle sont maintenant des cartes `ActionRow` (`python/gui/widgets/action_row.py`) au lieu du `QFrame` fait à la main de 50 px avec un `mousePressEvent` monkeypatché :
  - un **bord gauche sémantique de 3 px** (`err` pour les actions d'effacement/destructives, sinon `accent_hi`) — le même langage de bord de risque que peint `MethodCard.set_risk` dans le navigateur de flux,
  - une **tuile d'icône 40x40**, un titre **13 px / 800** et une description **sur une ligne elided**. Cela corrige le « longs libellés de flux débordent/se replient de façon imprévisible » du plan : la description s'élise au lieu de se replier, donc un long libellé ne peut jamais forcer le tableau plus large que son panneau ni se lire comme un bloc ragged multi-lignes,
  - un **chip** moteur/mode optionnel et une **chevron** `›` atténuée ; hover / pressed / focus sont possédés par le widget (propriété dynamique QSS + anneau de focus). Le chip est peint comme un **pill monochrome** à partir de la couleur d'accent que renvoie déjà `common._mode_chip` (remplissage teinté à l'accent, texte accent, fine bordure accent), donc chaque badge se lit comme une même famille,
  - **accessible au clavier** — `StrongFocus` + Entrée / Retour / Espace émettent le signal `activated` (remplaçant le `mousePressEvent` monkeypatché). Le tableau conserve ses tags `flow_act` / `flow_tip` et connecte simplement `activated`, donc le routage est inchangé,
  - les conteneurs de groupe portent désormais le **compteur** d'actions du job (`FRP REMOVE · 4`) — le même langage nom + compteur que les en-têtes de job du navigateur de flux.
- **Invariants respectés.** `_ACTION_META` compte toujours **62** entrées ; les `acts` et `btn_sha` de chaque page `dev_*` sont octet-identiques (aucune ligne d'action, texte ou bouton ajouté/supprimé/renommé) ; `gated_count` **418**, `gated_triples_sha256` `c89acce…7d75`, `gated_unique_triples` **61**, `core_flows` **116**, `stack_count` **25**. La largeur minimale naturelle de la pile de pages reste **699 px**, prouvant que les libellés elided n'ont rien élargi.
- **Golden régénéré délibérément ici.** `tests/ui_inventory_golden.json` a été reconstruit avec `REGEN_INVENTORY=1` dans cette slice : la seule différence est le **compteur de widgets** par page (`dev_apple` 59→63, `dev_motorola` 85→99 — les cartes/libellés ajoutés des deux tableaux researched). Le md5 transient du golden après B2 était `929f428638e91a42865ddde1ac96dd19`. Le polish de suivi de cette slice de document (la famille de chips monochrome et la séparation du panneau d'appareils au premier affichage) n'a changé **aucun** compteur de widgets de page, donc le golden n'a eu besoin d'**aucune** régénération supplémentaire.
- **Slice B4 — le tableau de modèle remplit la hauteur de la page (cette slice).** Sur la page modèle d'appareil → tableau (`devices.build_brand_page`), la ligne de séparation en deux volets ne recevait pas la hauteur de la page, laissant une large bande vide **sous** les deux volets. À une fenêtre 1600x951 (viewport de page extérieure `878x717`) les volets mesuraient `gauche 250x313 / droit 598x333` avec une **bande morte de 333 px** en dessous, et le tableau d'actions ne recevait que `333` des `717` px. Cause racine : la ligne de séparation était ajoutée à `outer` **avec stretch 1** *et* un `outer.addStretch(1)` trailing ajouté juste après — les deux éléments étirés se partageaient l'espace vertical restant ~50/50, et aucun volet n'était verticalement `Expanding`, donc rien n'absorbait. Correction (chirurgicale, dans `build_brand_page` seulement) : retirer le stretch trailing concurrent (la ligne de séparation prend désormais **toute** la hauteur restante) et donner à `list_col` gauche et `right_stack` droit une politique verticale `Expanding` explicite, pour que `lscroll` intérieur et le `_scroll` intérieur de la page modèle courante reçoivent la hauteur pleine et possèdent leurs propres barres de défilement. Les lignes de gauche restent alignées en haut (`lv2.addStretch(1)` est inchangé) et défilent quand la liste grandit. Après : `gauche 250x646 / droit 598x665`, bande morte **1 px** (seulement la marge basse de 8 px du layout), le tableau de droite montre bien plus de flux et défile le reste en interne (`vscroll_max` 900 → 557), et le `_page_scroll` extérieur de la coque reste masqué (`verticalScrollBar().maximum() == 0`). Pour répondre à la future exigence utilisateur, 40 modèles en mémoire supplémentaires font croître la plage de défilement de la liste **gauche** (`vscroll_max > 0`) sans aucun changement de hauteur des volets.
  - Nouveaux tests : `tests/test_device_board_layout.py` — `TestBrandPageFillsHeight::test_no_dead_band_below_split`, `::test_both_panes_get_the_real_height`, `::test_right_board_scrolls_its_own_content`, `::test_more_devices_scroll_left_without_growing_the_panes`. Les deux tests de géométrie ont été confirmés comme **échouant** sur le code non corrigé d'abord (bande morte 295 px à H=640 ; volet gauche 275 px contre le plancher de 412 px) avant la correction.
  - **Aucun widget ajouté ni retiré** (seule une politique de taille a changé et un espaceur stretch a été retiré), donc aucun compteur de widgets de page n'a bougé et `tests/ui_inventory_golden.json` n'a eu besoin d'**aucun** regen — toujours `929f428638e91a42865ddde1ac96dd19`.
- **Slice C — registre complet de flux sur le tableau d'appareils (REVERTED).** Cette slice ajoutait un dernier groupe `MORE FLOWS · N` rendant le registre complet de flux du moteur de l'appareil en cartes `ActionRow`, plus une barre de filtre texte/mode. Elle était cadrée par **moteur + mode de transport**, ce qui n'est pas la même chose que les *fonctions de cet appareil* : tout téléphone exposant ADB tirait donc tous les flux enregistrés ADB du registre, donc le tableau Motorola proposait des jobs réservés à Samsung (`knox_bypass`, `kg_remove`, `odin_flash_tar`), `imei_repair_spd`, `apple_icloud_*` et `huawei_frp_guide`. Pire, les modèles Motorola portent des **moteurs par modèle** (`Moto G13` = `spd`, `G24` = `mtk`, `G6` = `qcom`), donc les modèles `planned` montraient un registre SPD/MTK entier pour un travail non fait, et les marques motorola/apple contournent par conception le portillon `researched` sur le tableau. Revert complet : le groupe du registre, sa barre de filtre, `_ENGINE_MODES`, le report au premier affichage et `tests/test_device_flows.py` ont disparu ; le tableau est à nouveau exactement les actions curatées par appareil. Le golden d'inventaire est resté octet-identique (`929f428638e91a42865ddde1ac96dd19`) car le groupe était construit paresseusement, donc le revert ne nécessite aucun regen non plus.
  - Leçon pour toute nouvelle tentative : cadrer par les **`actions` déclarées du modèle lui-même** (`supported_devices.json`), en n'étendant que les flux que ces actions dispatchent vraiment — jamais par moteur + mode.
  - Fait vérifié qui survit et est réutilisable : `win._route_flow_activation(job, mode, key, label)` est le seul sink qui applique la confirmation destructive et l'acquittement EXPERIMENTAL de propriété ; `_dispatch`/`start_model_action` ne l'est pas (sa vérification expérimentale est le set étroit `devices._EXPERIMENTAL_ACTS`, donc par ex. `emmc_raw` s'exécuterait sans acquittement).
- **Différé (encore) :** boîte de recherche / puces de filtre par mode sur une liste de flux par appareil, favoris/récents (persistés dans les paramètres), file de sélection par lot (cases + exécution séquentielle), réordonnancement par glisser-déposer, la navigation Job → Mode → Méthode en trois volets, l'expansion des variantes de mode d'un job en cartes supplémentaires (une carte par `(job, mode, key)` est une décision volontairement repoussée — cette slice NE déploie PAS les modes), et un `ConfirmDialog` réutilisable (les surcouches confirm/expérimental restent des modales possédées par la fenêtre).

## Phase 8 — Finition professionnelle & différenciation (nouveau)
### Identité visuelle
- Thème sombre signature « atelier » avec texture de grain/bruit subtile et vignette douce.
- Marque + monogramme ; iconographie cohérente (style Lucide) sur toutes les actions.
- Cartes hero d'appareil : silhouette d'image du modèle, puce, badges de transport, dernier vu.
- Scène de connexion animée améliorée : vraie impulsion de câble, points de statut par appareil.

### Densité d'information
- Panneau inspecteur pliable : détails de l'appareil sélectionné, partitions, résumé PIT, logs.
- Vue chronologique des opérations (début/fin, durée, résultat) par appareil.
- Vue diff pour les changements PIT/partition avant flash.

### Sécurité & confiance
- Carte de checklist pré-vol avant les ops destructives (appareil, firmware, correspondance PIT).
- Échelle de risque claire avec couleur + icône + texte ; jamais couleur seule.
- Visualiseur de journal d'audit (actions expérimentales) avec export.

### Productivité
- Palette de commandes (Ctrl+K) pour rechercher flux, appareils, paramètres.
- Recherche globale dans les logs et les appareils.
- Navigation clavier d'abord ; superposition des raccourcis (?).
- Restauration de session : rouvrir le dernier appareil + page.

### Sentiment Linux-natif
- Boîtes de dialogue de fichier natives, conscience du thème système, gestion Wayland/X11.
- Notifications bureau pour les ops longues ; icône de tray avec progression.
- Glisser-déposer des fichiers firmware sur la page de flash.

### Onboarding
- Assistant de premier lancement : setup udev, statut de build du pont, test d'appareil.
- États vides avec illustrations et prochaines étapes.
- Tiroir d'aide contextuelle avec docs par flux depuis `operations/`.

### Ressources de marque
- Nouveau jeu de logos, splash, graphiques d'installateur, icône d'app.
- Captures README rafraîchies pour correspondre au nouvel UI.

## Phase 9 — Refonte console / terminal (nouveau)
### Objectif
Faire du journal de console un terminal Linux de premier ordre (esthétique UEFI-shell/TTY) plutôt qu'une boîte de texte exiguë.

### Layout
- Dock **à droite** dédié dans un séparateur horizontal (pages à gauche, console à droite) ; redimensionnable, pliable en une barre fine. Largeur par défaut 420 px, minimum 360 px (mesuré depuis la propre rangée de contrôles du dock pour que rien ne soit tronqué). _Décision (utilisateur) : la console reste à droite — une version antérieure de cette phase disait « dock bas / 35 % de hauteur » ; cela est remplacé._
- Terminal large, monospace, avec un padding confortable (16 px), hauteur de ligne 1.45.
- Mode terminal plein écran optionnel (F11) avec chrome minimal.
- Onglets par appareil ou puces de filtre pour que les logs ne s'entremêlent pas.

### Style
- Palette TTY sombre : fond noir, texte vert/ambre/cyan, scanline optionnelle subtile.
- Support des couleurs ANSI pour la sortie du pont ; en-têtes gras, horodatages atténués.
- Bascule numéros de ligne / horodatages.
- Sélection + copie ; menu clic droit (copier, enregistrer, effacer, filtrer).

### Comportement
- Streaming avec backpressure ; pas de gel UI sur 10k+ lignes.
- Recherche avec regex, mise en surbrillance des correspondances, saut suivant/précédent.
- Export vers fichier ; auto-enregistrement du journal de session.
- Filtre par appareil et par niveau (info/warn/error/step).

### Pas serré
- Contraintes de largeur/hauteur minimales ; habillage réactif ; défilement horizontal pour les longues lignes.
- Colonnes redimensionnables pour horodatage/niveau/appareil.

## Phase 10 — Messages console & système de toasts (nouveau)
### Messages console
- Entrées de log structurées : horodatage, clé d'appareil, niveau, message.
- Niveaux colorés : info (ardoise), succès (vert), avertissement (ambre), erreur (rouge), étape (cyan).
- Sortie multi-lignes pliable (traces de pile, JSON) avec « afficher plus ».
- Barres de progression en ligne pour les étapes de flashage ; icônes de statut par étape.
- Clés d'appareil cliquables pour focaliser l'appareil ; clés de flux cliquables pour ouvrir la doc.

### Toasts
- Toasts non bloquants, empilés avec icône, titre, message, bouton d'action.
- Disparition automatique avec barre de progression ; pause au survol.
- Styles de sévérité (info/succès/avertissement/erreur) avec palette cohérente.
- Limite de file (max 3 visibles) avec compteur de débordement.
- Options de position (haut-droite/bas-droite) et support du mouvement réduit.
- Son/haptique optionnel pour les erreurs.

## Phase 12 — Recherche de parité HiProTool (nouveau)
### Statut
- Recherche en ligne indisponible dans cet environnement (HTTP 402). Recherche manuelle requise.

### Tâches de recherche
- Collecter la liste de fonctionnalités HiProTool (FRP, MDM, verrou d'écran, opérateur, IMEI, flashage).
- Mapper chaque méthode à un moteur (ADB, mode download, BROM, EDL, fastboot, SPD).
- Identifier les raccourcis et prérequis spécifiques aux appareils.
- Documenter dans `operations/` avec étapes de vérification et notes de sécurité.
- Prioriser les méthodes à haute valeur et faible risque d'abord.

## Phase 14 — Fonctionnalités suivantes (nouveau)
### Fonctionnalités cibles
- Suppression de l'IMEI de la liste noire (recherche + playbooks par appareil).
- Améliorations du déverrouillage opérateur (verrou SIM, chemins NVDATA/QCN).
- Améliorations du déverrouillage MDM (device owner, provisionnement QR, recovery).
- Améliorations FRP (méthodes par puce/version Android).
- Améliorations de la suppression de verrou d'écran (ADB, recovery, download, EDL).
- Suppression du Samsung Knox Guard (EXPERIMENTAL, journalisée).
- Suppression de l'enrôlement MDM Apple (profil/DEP).
- Outils de gestion Samsung Knox.
- Gestion de l'enrôlement Android Enterprise.
- Gestion de l'enrôlement zero-touch.
- Suppression du verrou d'activation Apple (portée checkm8/DFU, limites honnêtes).
- Récupération du PUK SIM pour déverrouiller le PIN SIM.
- Suppression du verrou biométrique (recherche, limites appareil).

### Notes
- Chaque fonctionnalité doit être adossée à Rust et marquée EXPERIMENTAL là où c'est risqué.
- Documenter dans `operations/` avec vérification et notes de sécurité.

## Phase 15 — Audit & nettoyage de la documentation (nouveau)
### Références obsolètes trouvées (historiques/retirées)
- `operations/*/README.md` mentionnent des modules Python retirés (`knox.py`, `qcn.py`, `health.py`, `apple.py`, `flows/*.py`) comme contexte ; acceptable mais doit être clairement marqué historique.
- `INDEX.md` référençait précédemment un `SPLIT_PLAN.md` manquant (corrigé).
- `README.md` la mise en page du dépôt listait précédemment des modules inexistants (corrigé).
- `DESCRIPTION.md` avait de mauvais comptes de transports/jobs (corrigé).

### Tâches de doc restantes
- Normaliser toutes les notes « retiré » dans une seule section « History » par fichier.
- Ajouter une note « Architecture actuelle » en tête de chaque README d'operations.
- Supprimer ou archiver les plans de migration obsolètes (DESIGN.md → nouvelle version).
- Garder `operations/` comme recherche uniquement ; les pointeurs de code doivent dire `src/flows.rs`.