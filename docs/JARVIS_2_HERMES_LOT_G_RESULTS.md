# Lot G — installation effectuée le 15 novembre 2026

Autorisation G maintenue explicitement après confirmation utilisateur que le S9 est physiquement éteint. Aucun contact avec le mineur, aucun changement de sa boucle ou de ses paramètres.

## Résultat

Patch exact 50fb561 posé : `server.js`, les deux modules relais/contrat, HTML servi et HTML source, et les deux assets embarqués. Empreintes du manifeste revu vérifiées avant pose, fichiers installés identiques aux artefacts. Aucun changement des modules hybrid, audio, Codex, HA ou mémoire. Drop-in d'armement conforme à a5a5940 ; switch privé explicitement **false**, permissions 0600.

Un seul `systemctl --user restart codex-gateway.service` exécuté : PID 2033987 → 2516015. Service actif, compteur de redémarrages automatiques nul. Aucun second restart, aucun démarrage Windows/Hermes/GPU, aucune mission ou dépense API.

## Préconditions et sauvegarde

Aucun run déclaré dans `/api/runs`, aucun processus enfant dans le cgroup gateway aux contrôles précédant l'intervention. Les sessions vocales clientes ne sont pas dénombrables par les endpoints existants ; l'utilisateur a indiqué fermer l'interface vocale et accepté la coupure. Aucun contournement de contrôle ni nouvelle instrumentation du processus.

Espace libre vérifié avant écriture : environ 1,37 Gio, au-delà de la réserve de 256 Mio et du volume du lot. Sauvegarde privée :

`/home/user/workspace/jarvis-2-memory/data/deployments/G-20261115T174634Z-8377cbfb/`

Dossier 0700, copies 0600, contrôle d'égalité des octets effectué ; `result.json` conserve existence initiale, empreinte et métadonnées de chaque cible. Aucun `.env`, secret, conversation ou base personnelle copié. Le lot ne modifie aucune SQLite ; la sauvegarde/restauration synthétique du lot R est conservée séparément.

## Contrôles après redémarrage

- Santé authentifiée HTTPS 200, certificat vérifié avec le certificat local et contrôle du nom/IP.
- `/jarvis/` et nouveaux assets HTTPS 200, contenu identique aux empreintes attendues.
- Statuts voice/live 200 : fournisseur configuré, moteur **hybrid** conservé. Aucun appel de transcription, synthèse ou conversation pour ce contrôle.
- Endpoints embarqués session/config/historique : **404**, conformément au switch false. Aucun test utilisant le code opérateur privé.
- Runs vides, PID stable, aucun redémarrage automatique.
- Chromium sur l'interface effectivement servie : DOM, canvas holographique, bouton micro et script de routage présents ; bouton Hermes caché. Requêtes personnelles et fournisseurs bloquées dans ce navigateur de contrôle ; aucune connexion micro ni lecture de mémoire personnelle.

Limite du contrôle navigateur : l'attente initiale `networkidle` a expiré ; le contrôle fondé sur DOM prêt et éléments attendus a ensuite réussi, sans modification ni redémarrage serveur. L'interface effectue des requêtes récurrentes ; une attente de silence réseau n'est pas un critère d'acceptation adapté. Pas de validation audio physique ni d'iPhone réel pendant ce lot.

## Retour arrière prêt, non utilisé

Les originaux sont `00.original` (serveur), `03.original` (HTML servi), `04.original` (HTML source). Restaurer leurs octets et modes depuis les enregistrements ; retirer seulement les ajouts identifiés comme absents initialement, dont modules, assets et drop-in. Maintenir le switch false pendant toute restauration. Ne pas modifier `.env`, services privés ou données.

Un éventuel rechargement d'unité et second restart nécessitent présentation de la restauration et nouvel accord conformément à l'autorisation G. Aucun retour arrière ni second restart déclenché automatiquement.

**G installé et contrôles ci-dessus réussis ; activation du panneau non effectuée, en attente d'accord distinct.** Les anciennes lacunes globales d'authentification des routes historiques ne sont pas déclarées résolues par ce relais spécialisé. Les protections d'identité et ACL du service privé restent celles validées dans R ; aucune nouvelle capacité n'est accordée au modèle.
