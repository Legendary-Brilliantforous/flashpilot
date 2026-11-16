# Politique de sécurité

Language switcher: [English](../../SECURITY.md) · **Français**

## Versions supportées

Le projet est en pré-1.0. Les correctifs de sécurité arrivent sur la branche
`main` et, quand elle existe, sur la dernière release taggée.

## Signaler une vulnérabilité

Veuillez **ne pas** ouvrir d'issue publique pour un problème de sécurité.
Signalez de façon privée :

- Email : **flashpilot@proton.me** (créez cette adresse sur proton.me → compte
  gratuit), ou
- Formulaire de signalement privé de vulnérabilité de GitHub sur ce dépôt.

Veuillez inclure :
- Commande / flux affecté et version,
- Étapes de reproduction,
- Impact (ex. exécution de code arbitraire, risque de brick, perte de données,
  exposition d'identifiants).

Nous visons à accuser réception sous 72 heures et coordonnerons la divulgation.

## Portée et attentes

Cet outil effectue intentionnellement des opérations USB / bootloader de bas
niveau. Par nature il peut effacer ou bricker un appareil. C'est un
comportement documenté, pas une vulnérabilité. Ce qui nous importe :

- Les exploits qui exécutent du code non fiable au-delà de l'opération prévue,
- Le contournement des confirmations de sécurité / vérifications d'appareil
  d'une façon qui nuit aux utilisateurs,
- La livraison de blobs propriétaires ou de secrets dans le dépôt,
- Tout ce qui fuite les données ou les identifiants d'appareil d'un utilisateur.

Veuillez n'opérer que sur des appareils que vous possédez ou que vous êtes
autorisé à entretenir.