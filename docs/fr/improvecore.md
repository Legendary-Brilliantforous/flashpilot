# ImproveCore — Améliorations du cœur Rust

Language switcher: [English](../../improvecore.md) · **Français**

Source : éléments liés à Rust déplacés depuis `ui-improvement.md`.

## Flashage ADB par appareil
- Sessions ADB indexées par appareil avec retry/backoff et machine à états claire.
- Vérification après écriture (hash) par défaut ; progression par partition.
- Gestion robuste des états non autorisé/hors ligne ; invite de ré-authentification automatique.
- Prise en charge de plusieurs appareils ADB concurrents sans interférence.

## Innovation Odin (Samsung)
- Dépasser le dernier Odin : résilience de session unique, récupération par réinitialisation de port, streaming multi-partition.
- Meilleure validation PIT, gestion vbmeta/AVB, conseils de réparation drk.
- Reprise/réessai sur erreurs USB transitoires ; explications détaillées des échecs.

## Communications BROM / bas niveau
- Abstraction BROM unifiée pour MTK, Samsung, SPD, Qualcomm.
- Assistants crash-to-BROM, SLA/auth, fiabilité d'upload DA.
- Classification des erreurs avec correctifs actionnables ; délais par étape.

## Prise en charge MTK récente
- Analyse des preloader V5/V6 et sélection de DA (`mtk_daloader.rs`).
- Suivi des dernières versions DA/preloader MTK ; auto-détection et sélection.
- Garantir le fonctionnement des chemins exploit/SLA sur les puces les plus récentes ; ajouter des fixtures de test.

## Détection d'interface USB
- Détecter CDC ACM, ECM/NCM, stockage de masse, HID, spécifique au vendeur, diagnostic/modem.
- Détecter bootrom, preloader, ADB, mode download, EDL, MTK, SPD.
- Exposer la liste des interfaces dans les lignes d'appareil ; mapper vers les flux pris en charge.

## Suppression instantanée (FRP/MDM/verrous)
- Recherche d'intégration à la HiProTool : chemins rapides quand c'est sûr, documentés.
- Playbooks par appareil dans `operations/` avec étapes vérifiées.
- Conserver l'encadrement expérimental + la journalisation d'audit pour les ops risquées.