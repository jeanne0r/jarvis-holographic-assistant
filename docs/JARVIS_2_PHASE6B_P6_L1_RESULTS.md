# P6-L1 — Journal du pilote autorisé

Accord utilisateur reçu le 15 novembre 2026 pour le bloc P6-L1 uniquement.
Une mission synthétique maximum, fenêtre de ressources de 300 secondes, six
appels maximum, quota partagé de 98 304 tokens, coût distant 0 CHF.
Aucune autorisation P6-L2, gateway active, données personnelles ou action physique.

## Préparation et contrôles

- Préflight Windows en lecture seule : RTX 3080, 10 240 Mio, 9 168 Mio libres,
  charge 0 %, minage non détecté; Ollama et Hermes non démarrés.
- Archive Hermes épinglée vérifiée : 25 615 fichiers.
- Huit fichiers d’application et de supervision Windows : empreintes conformes.
- Aucun correctif ou installation nécessaire sur Windows.
- Nouveau lanceur local limité à P6-L1 et au panneau; /ask refusé explicitement.
- Test réel du navigateur + façade + SQLite avec runtime simulé réussi. Le test
  exige un verdict global faux en l’absence d’appels modèle réels.
- Le test initial a corrigé une attente networkidle inadaptée aux rafraîchissements
  de l’interface; attente DOM puis des éléments précis. Aucun processus GPU lancé.
- Le premier préflight de lancement a différé sur des connexions TCP TIME_WAIT
  laissées par le test hors ligne. Aucun listener ni service concurrent, aucune
  suppression de connexion et aucun changement de garde : attendre leur expiration.

Les jetons, la base synthétique et les captures restent dans le dossier privé
ignoré par Git sous data/phase6. Seules des preuves synthétiques sans identifiants
secrets sont ajoutées aux rapports.

## Résultat matériel effectif — intégration réussie

Essai unique du **15 novembre 2026, 05:58:44 à 05:59:52 UTC**, soit 68 secondes
pour le cycle supervisé. Rapport brut conservé :
[JARVIS_2_PHASE6B_P6_L1_REAL_20261115T055844Z-b5242289.json](JARVIS_2_PHASE6B_P6_L1_REAL_20261115T055844Z-b5242289.json).

| Contrôle | Observation réelle |
|---|---|
| Admission | Un clic automatisé Playwright sous identité opérateur dédiée dans le panneau holographique réel de la copie; POST façade 202, état queued |
| Bridge | Serveur HTTP et nouvelle SQLite synthétique réels, admission persistée avant dispatch |
| Runtime | Hermes Windows épinglé 4959268e312a21a361f248e49030d5f5df3984d5, compte standard, aucun shell offert |
| Modèle | qwen3.5:4b local, digest d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04 |
| GPU | RTX 3080 10 Go; contexte servi 64 000 confirmé par /api/ps |
| Outils | jarvis_memory_search puis deux jarvis_memory_history; trois événements tool.completed sans erreur |
| Identifiants | L’historique a utilisé les memory_id de la connaissance et de l’expérience synthétiques |
| Sortie | Quatre cellules de 1 kg, ancienne configuration [1,2,5,10], sources correction/old et expérience visibles dans le panneau |
| Persistance | Résultat terminal dans SQLite et une expérience inferred, sans duplication ni promotion en fait vérifié |
| Budget | Une mission, 3 appels, **13 453 tokens** sur 98 304; coût distant **0 CHF** |
| Fin | Arrêt des processus/Jobs et tunnels du pilote; fenêtre close, switch désactivé |

Le navigateur est réel et les requêtes du panneau ne sont pas simulées.
L’opérateur de test est automatisé après l’autorisation humaine; aucun clic manuel
sur la production. Les autres fonctionnalités Jarvis hors périmètre sont refusées
par le serveur du pilote. Le chemin `/ask` est explicitement interdit et n’a reçu
aucune requête. Aucun microphone, transcription Google ou appel Codex n’est testé.
Aucun contact avec CT205/Qdrant : cette démonstration utilise le lecteur SQLite/FTS
existant et ne répète pas la preuve sémantique C1.

### Mesures observées

- Appels modèle : 3 393, 4 385 et 5 675 tokens; latences du relais environ
  8,86 s, 5,07 s et 5,74 s. Ce sont des durées complètes d’appel, pas du débit pur.
- Pic VRAM échantillonné : **6 873 Mio / 10 240 Mio**, marge 3 367 Mio;
  puissance GPU maximale échantillonnée **328,13 W**. Échantillonnage périodique,
  pas une preuve du maximum instantané ni une mesure d’énergie à la prise.
- Pic mémoire processus Hermes : **316 Mio**, Job **352 Mio**, sous sa limite
  indépendante de 2 Gio sur Windows; durée supervisée Hermes environ 51,8 s.
- Le modèle a déclaré via /api/ps 5 154 285 812 octets résidents VRAM,
  contexte 64 000. Cela diffère de la VRAM totale qui inclut affichage/overhead.

### Réserve de qualité — aucune validation factuelle automatique

La vérification humaine/déterministe après essai détecte une **date erronée** dans
la réponse : la correction est annoncée au 2023-11-15, alors que sa provenance
canonique est **2023-11-14T22:15:00Z**. La configuration initiale est horodatée
2023-11-14T22:13:20Z. Les capacités et références demandées sont correctes.
Les deux appels d’historique sont réussis et concernent deux vrais memory_id :
les traces ne montrent pas d’erreur d’outil à attribuer à ces appels.

Le verdict d’intégration `passed=true` est conservé avec ses critères annoncés;
il **ne signifie pas** que tout le texte du modèle est vérifié. La revue séparée
[JARVIS_2_PHASE6B_P6_L1_QUALITY.json](JARVIS_2_PHASE6B_P6_L1_QUALITY.json)
porte `content_fully_verified=false`. Aucun essai supplémentaire pour effacer
cette réserve. Les deux révisions de connaissances restent celles de la fixture;
l’expérience enregistrée est un récit du résultat, statut inferred et validation
unreviewed_report_not_verified_fact, jamais une nouvelle date vérifiée.

Avant d’utiliser des dates dans une restitution factuelle, privilégier leur rendu
à partir des champs SQLite et leur contrôle indépendant plutôt qu’une conversion
libre par Qwen. Aucun correctif ni réindexation de mémoire réelle effectué ici.

### Vérification d’arrêt et absence d’impact

- Jobs Windows Hermes et Ollama : owned_process_stopped_after_close=true.
- Écouteurs Windows **8643, 11434, 8792, 11436 fermés** après fermeture des tunnels.
- Panneau Chromium, serveur de laboratoire et tunnel arrêtés.
- GPU revenu à **1 072 Mio utilisés / 9 168 Mio libres**, charge 0 %;
  minage non détecté avant/après, aucun réglage ou arrêt Kryptex effectué.
- Tous les fichiers actifs du manifeste sont inchangés. Gateway active conservée,
  **PID 2033987**, aucun redémarrage, aucune allocation Proxmox modifiée.
- Base et capture conservées dans le dossier privé ignoré par Git :
  data/phase6/p6-l1-20261115T055844Z-b5242289.
- Les preuves C1, B2, phases 5 et 6B hors ligne restent inchangées.

## Suite

P6-L1 est terminé. **P6-L2 reste non autorisé et non exécuté.** Sa proposition
reste un essai distinct du vrai `/ask` sur copie, avec texte transcrit synthétique,
une mission, 5 minutes, six appels, 98 304 tokens partagés, 0 CHF distant.
Ce pilote ne valide pas la chaîne microphone/transcription/synthèse réelle.
Aucune activation de gateway, mémoire personnelle, service permanent Windows,
commande physique ni publication automatique n’est incluse.

## Commandes et portée de validation

- Préparation : `python3 -m unittest memory_manager.phase6.test_panel_pilot -v`
  (un test, réussi après correction du raccordement; vrai navigateur et vraie
  SQLite, runtime simulé; jamais présenté comme preuve GPU).
- Essai autorisé : `python3 -u -m scripts.pilot_phase6b_panel --approved-p6-l1`.
  Le premier appel s’est arrêté au bind en lecture seule, avant fenêtre et avant
  tout démarrage Windows; après expiration des TIME_WAIT, le seul essai matériel
  a créé la mission et la preuve horodatée ci-dessus.
- Contrôles finaux : syntaxe Node du lanceur panneau, compilation Python des
  nouveaux modules, empreintes des préimages actives, état du service gateway et
  absence de listeners locaux du laboratoire. Node reste 18.19.1.

Le correctif d’erreur du lanceur masque désormais les messages pouvant inclure
une valeur de champ de connexion; seuls étape et classe d’erreur sont exposés.
Le parcours de succès mesuré n’est pas modifié. Aucun composant actif du patch
minimal de phase 6B n’a changé pendant ce pilote.
