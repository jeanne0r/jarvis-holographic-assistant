# Phase 6B — Préflight et pilotes proposés, non démarrés

## Vérifications hors ligne

- `python3 scripts/evaluate_memory.py --phase6b` : régressions établies, tests
  `/ask` hybride et interface, transport vocal simulé; rapport dédié 6B.
- `python3 scripts/prepare_phase6b_patch.py` : empreintes, application et inversion
  sur overlay temporaire, aucune écriture cible.
- `python3 scripts/phase6b_preflight.py` : préimages actives, moteur hybrid,
  branche isolée et fichiers de conversation/audio inchangés; **ne démarre rien**.

Ces vérifications ne mesurent pas l'état GPU courant et ne valent pas autorisation.
Rapports : `JARVIS_2_PHASE6B_TEST_RESULTS.json`,
`JARVIS_2_PHASE6B_PREFLIGHT_RESULTS.json`, `phase6b/patch-manifest.json`.

## P6-L1 — Panneau, une mission réelle, autorisation distincte demandée

**Machines** : copie Jarvis isolée sur VM Codex/Proxmox; runtime existant sous compte
Windows dédié sur PC Gamer; Ollama loopback/RTX via les tunnels privés déjà validés.
Aucune VM Hermes Proxmox, aucun changement RAM.

**Préparer avant lancement** : répertoire privé dédié sous le worktree pour copie
complète du code nécessaire, sans copier `data/`, `.env`, historiques ou secrets
actifs. N'utiliser que configuration hybride et fixtures synthétiques. La gateway
active et ses imports ne sont jamais réutilisés comme processus de laboratoire.
Le serveur expérimental écoute sur un port loopback libre distinct, vérifié avant
bind; accès navigateur par tunnel privé et Origin épinglée. Pas d'exposition LAN,
pare-feu ou modification SSH. Les jetons de laboratoire sont distincts et 0600.

Le Memory Manager/bridge existant pointe vers **une nouvelle SQLite synthétique**;
la fixture laboratoire actuelle charge DoseLab avec correction/historique et
références `synthetic://…`. Aucun index ou document personnel. Pas de nouvelle
collection Qdrant ni de changement CT205 pendant ce pilote d'intégration.
Réutiliser les briques `memory_manager/phase4/windows.py`,
`memory_manager/phase4/native_trial.py` et les gardiens du pilote
`scripts/pilot_phase5_windows.py`, sans relancer ce pilote historique. Le lanceur
6B doit relier cette copie et son bridge propres, puis être revu avant lancement;
il n’est pas encore validé avec le runtime Windows. Aucune commande de ces scripts
à effets réels n’a été exécutée pour la préparation 6B. Vérifier les clés hôtes
épinglées et le compte dédié avant tout tunnel; aucune acceptation aveugle.
Le runtime reçoit uniquement MCP contrôlé et le template synthétique, aucun shell,
HA, fichier personnel, promotion de fait ou publication de compétence.

**Exécution proposée après accord** : contrôler hashes et versions de l'installation
Windows existante; sauvegarder seulement les fichiers labo qui nécessiteraient une
adaptation approuvée. Vérifier GPU, VRAM et Kryptex avec les gardiens existants.
Si charge incompatible, différer/arrêter le pilote sans interrompre le minage.
Démarrer temporairement le runtime/Ollama et les seuls tunnels possédés par le labo;
se connecter humainement au panneau de la copie; cliquer une seule fois le template.
Capturer mission_id, admission, événements et résultat provenant du vrai Hermes.
Vérifier `source.ref` visible dans le panneau et résultat conservé dans SQLite.

**Bornes proposées** : une mission; fenêtre totale 5 minutes; au plus 6 appels
modèle et 98 304 tokens partagés; mission limitée à 240 secondes par son budget
serveur; distant 0 token / 0 CHF; contexte Ollama 64 000 déjà validé, aucun modèle
téléchargé. Recontrôler le gardien des appels/tokens avant démarrage : absence de
preuve d'application de ces bornes interdit l'essai.

**Arrêt** : annuler par bridge si nécessaire; conserver état et preuves. Fermer les
seuls processus/tunnels/Jobs identifiés comme créés par ce pilote. Ne pas tuer un
Ollama préexistant ou Kryptex. Une interruption incertaine devient à réconcilier,
jamais un run repris automatiquement. Vérifier absence de processus lab restants,
GPU libéré selon état initial et service gateway inchangé. Désactiver flags,
révoquer jetons labo; conserver la SQLite de preuve privée, ne pas l'effacer.

## P6-L2 — Chemin hybride /ask, autorisation séparée demandée

Démarrer seulement après P6-L1 validé et un accord propre à P6-L2. **Une seconde
mission** synthétique, identifiants et preuves distincts; mêmes bornes et arrêt.
Depuis la copie UI, soumettre « Jarvis, demande à Hermes de vérifier la configuration
DoseLab. » par `window.jarvisAsk`, y compris un canal `voice` simulant la sortie de
transcription. Vérifier POST réel `/ask`, 202 avant tout run, aucune classification
Gemini ni appel Codex pour cette demande, mission unique et résultat Hermes/source
restitué dans le panneau.

Vérifier avant toute mission des refus anon/expiré/espace usurpé/approbation et
commande mêlée. Les demandes ordinaires sont testées avec fournisseurs simulés,
**sans nouveau crédit distant**. Un véritable essai microphone → transcription
Google → synthèse Google n'est pas inclus : il nécessite un périmètre voix et
coût explicitement approuvé. Ne pas présenter le test de texte transcrit comme
preuve audio complète. Les mécanismes audio restent couverts hors ligne.

Le panneau seul ne valide pas /ask; /ask seul ne valide pas le microphone. Les
preuves portent les versions/hashes, identité pseudonymisée, modes réels/simulés,
latence d'admission, appels/tokens et métriques GPU; jamais les jetons ou données
personnelles.

## Autorisations non demandées par ces pilotes

Aucune modification gateway active, serveur Windows permanent, réglage minage,
allocation Proxmox, HA, import personnel, Qdrant historique, transfert de sauvegarde,
publication ou fallback distant. Une activation de production sera proposée
séparément après preuve laboratoire et revue du patch exact.

## Restauration d'un éventuel déploiement ultérieur

Avant toute application approuvée : revalider préimages du manifeste, sauvegarder
chaque ancien fichier dans une archive privée avec index SHA-256 et tester sa
restauration sur copie. Les fichiers créés sont distingués des anciens; ne pas
écraser un fichier ayant dérivé depuis la revue. Aucune migration de base réelle.
Un redémarrage gateway constituerait une opération approuvée distincte, absente
ici. Flags à zéro au montage initial, aucun lancement automatique Windows.

Arrêt Hermes immédiat via switch privé `{enabled:false}` : bloque nouvelles
admissions et garde l'authentification. N'arrête pas magiquement les runs actifs;
les annuler selon procédure. Le flag hybride seul à 0 garde le panneau disponible.
Restaurer les patchs à l'inverse de leurs dépendances uniquement après sauvegarde
et revue; restaurer tout l'ancien wrapper retirerait aussi l'authentification,
ce qui ne constitue pas un retour arrière de sécurité acceptable par défaut.

## Clôture des pilotes — 15 novembre 2026

Les deux autorisations ont été reçues séparément et consommées par un seul essai
matériel par bloc. P6-L1 et P6-L2 sont clos, leurs ressources arrêtées. Voir
`JARVIS_2_PHASE6B_P6_L1_RESULTS.md` et `JARVIS_2_PHASE6B_P6_L2_RESULTS.md`.
L2 démontre le vrai /ask à partir d’un texte de transcription synthétique, pas le
microphone. Aucun déploiement production, service Windows permanent ou accès
personnel n’est autorisé par cette clôture. Les périmètres ci-dessus restent la
trace de ce qui a été approuvé, pas une permission de répéter les essais.
