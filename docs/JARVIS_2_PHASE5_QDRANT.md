# Phase 5 — Qdrant et embeddings

## Audit initial réel, lecture seule

Preuves : `JARVIS_2_PHASE5_CT205_AUDIT_REAL.json` et
`JARVIS_2_PHASE5_EMBEDDING_RUNTIME_REAL.json`. Services actifs : `jarvis-qdrant`
et `jarvis-embeddings`. Qdrant **1.20.0**, collection historique
`jarvis_memory_v1`, **41 407 points** au relevé. La collection
`jarvis_knowledge_experimental_v1` est **absente** (404). Aucune collection expérimentale créée.

Le service existant utilise `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`,
384 dimensions, Cosine, ONNX quantifié. FastEmbed **0.9.1**, ONNX Runtime **1.31.1**,
Tokenizers **0.23.3**. L'artefact ONNX observé fait 235 052 644 octets et son SHA256 est
`634d0f66c29dc934c8fa72b8a4fe91dd4d420a22f1d82a241058d4316e659a99`.
Les empreintes des fichiers tokenizer/config sont dans la preuve d'audit.

Le service actuel propose `/health`, `/index`, `/search`, `/prune` ; il ne propose
**pas** `/v1/embeddings`. `/index` et `/prune` sont liés à la collection historique :
ils ne doivent pas être utilisés pour le prototype. Les accès sans clé sont refusés.
La clé historique n'a été utilisée que dans le processus d'audit CT205, sans sortie.

Ressources observées : environ **873 Mio disponibles** et **5,48 Gio de disque
libre** dans CT205. Ce relevé n'est pas une réservation. Relever de nouveau les
ressources avant intervention. Ne pas dupliquer une instance de modèle dans CT205.

## Extension déployée après accord A2

Le patch du worktree `semantic/service.py` garde le comportement existant tant que
les flags sont absents. Les flags suivants sont maintenant imposés sur CT205 :

```
JARVIS_EMBEDDINGS_READONLY_STARTUP=1
JARVIS_EXPERIMENTAL_EMBEDDINGS=1
JARVIS_EMBEDDINGS_MANIFEST_FILE=<fichier privé 0600>
JARVIS_EXPERIMENTAL_EMBEDDINGS_TOKEN_FILE=<jeton expérimental distinct 0600>
```

Le démarrage en lecture seule vérifie l'existence de la collection historique par
GET et ne réémet aucun PUT d'index. L'activation expérimentale sans cette protection
échoue. Les routes historiques ne sont pas réutilisées par le nouveau client.

L'extension réutilise le modèle et le verrou déjà chargés. Elle vérifie la version
exacte des bibliothèques, le chemin ONNX effectivement chargé et les empreintes
ONNX/tokenizer/config ; le manifeste couvre le pipeline entier. Elle clone le
Tokenizer chargé pour compter les tokens sans troncature, sans muter le tokenizer
historique. Un changement de preprocessing query non étudié provoque un refus.
Le hash ONNX seul ou la dimension 384 ne suffisent pas.

`POST /v1/embeddings`, authentification Bearer indépendante, reçoit exactement
`model`, `kind` (`document`/`query`), `input`. Réponse : `model`, `artifact_sha256`,
`dimensions`, `kind`, `input_tokens`, `data[0].embedding`. Maximum 128 tokens,
contrôle d'entrée 8 000 octets, corps 16 000 octets, une requête expérimentale
admise à la fois ; capacité occupée → 429. Vecteur fini, non nul, 384 dimensions.
Les requêtes HTTP ne peuvent pas sélectionner un modèle ni déclencher un téléchargement.

**Validé sur le runtime réel après accord A2** : FastAPI, session ONNX, tokens,
identité séparée et empreinte du pipeline. Précontrôle ASGI avec faux modèle :
concurrence 200/429 ; sondes HTTP réelles : 11/11. Le compteur refuse le dépassement
au lieu de tronquer. RSS après essai 886,84 Mio, sans référence RSS avant.
La qualification sous charge et la pertinence sur grand corpus restent à faire.
Voir `JARVIS_2_PHASE5_A2_RESULTS.md`.

## Sauvegarde et restauration vérifiable — A1 autorisé et validé

`scripts/phase5_qdrant_plan.py` imprime uniquement le plan HTTP de
`JARVIS_2_PHASE5_QDRANT_REQUEST_PLAN.json`. Il n'exécute aucune requête.

1. Relever version, schéma, nombre de points et taille disque sans payloads.
   Vérifier la place nécessaire au snapshot ; suspendre l'intervention si insuffisante.
2. Après accord, demander un snapshot de `jarvis_memory_v1` (création de fichier,
   aucun changement de points). Télécharger uniquement le nom retourné vers un
   répertoire privé 0700, fichier exclusif 0600. Enregistrer taille et SHA256 dans
   un manifeste privé, avec version/config/date et identifiant du snapshot.
3. Vérifier le fichier sur le stockage de sauvegarde. Préparer une instance isolée
   Qdrant **1.20.0**, sans routage vers Jarvis ni accès du modèle. Restaurer sur
   volume vide, sans `force`, sans cible existante. Vérifier schéma et nombre
   correspondant au snapshot ; les écritures concurrentes rendent une comparaison
   avec le compteur de production ultérieur non pertinente.
4. Tester la disponibilité de la copie isolée, enregistrer la preuve de restauration,
   arrêter cette instance ; conserver la sauvegarde. Ne publier aucun contenu privé.
5. Sauvegarder aussi le fichier source du service, les références de configuration
   et les unités avant patch ; aucune copie de secrets dans Git ou les rapports.

Un snapshot contient les données/configurations de collection, pas les alias.
Voir [documentation Qdrant snapshots](https://qdrant.tech/documentation/snapshots/).
Prévoir au moins deux fois la taille restaurée, en plus de l'archive présente ; voir
[options de récupération Qdrant](https://qdrant.tech/documentation/migration-recovery-options/).
L'audit complémentaire relève 307 330 079 octets dans l'arborescence Qdrant.
Les 5,48 Gio libres sont compatibles avec un petit essai, mais la taille réelle
du snapshot, le budget disque et la marge RAM doivent être revérifiés avant
lancement. Le rapport principal propose une instance de vérification temporaire
bornée sur CT205, distincte de l'instance principale. Depuis l'accord A1, un snapshot privé de 168 229 376 octets a été vérifié et
restauré réellement : voir `JARVIS_2_PHASE5_A1_RESULTS.md`. La copie est locale à
CT205 ; aucune copie hors hôte n'est encore réalisée.

## Collection, index et recherche

Collection créée après accord A2 : **jarvis_knowledge_experimental_v1**, 6 points
synthétiques. Pour toute extension future, provisionner **uniquement** `jarvis_knowledge_experimental_v1`, après sauvegarde
vérifiée et accord. Si elle existe déjà, vérifier sa configuration et arrêter en cas
d'écart ; ne jamais la remplacer. Schéma proposé : Cosine/384, vecteurs/payload
sur disque. Ne pas créer ni modifier d'index sur la collection historique.

L'indexeur refuse tout autre nom. Identifiant UUID5 déterministe : collection,
empreinte du pipeline, identifiant mémoire, révision et numéro de fragment.
Payload minimal : ces références, owner/scope, schéma 1, empreinte du texte complet,
modèle/artefact ; le contenu canonique n'est pas récupéré depuis ce payload.
Seuls les éléments actuels `verified` ou `user_confirmed`, non contradictoires et
non masqués, sont éligibles.

Découpage conservateur à 96 octets UTF-8, recompté par l'endpoint : ce choix protège
le contexte mais peut diminuer la pertinence. Le benchmark réel doit mesurer les
paraphrases et le rang du résultat attendu avant d'importer des données personnelles.
Pas de score sémantique revendiqué à partir des vecteurs constants de test.

Chaque upsert exige `wait=true` et `status=completed` avant accusé SQLite. Un crash
après l'accusé distant et avant le checkpoint rejoue le même identifiant, sans
nouveau point. Lots bornés à 100 points/10 secondes par défaut, maximum 1 000/30 ;
les délais réseau suivent le temps restant (précontrôle collection jusqu'à 5 s).
Une reconstruction explicite rejoue les mêmes IDs, même si les accusés existent.
Une nouvelle identité de modèle produit un autre espace d'IDs et nécessite revue.
Aucun delete, prune ou nettoyage global n'est fourni.

FTS5 + fusion des rangs vectoriels + filtres structurés + priorité aux statuts
acceptés. Chaque référence est relue dans SQLite : droits, révision actuelle,
validité temporelle, contradictions et visibilité. Un ancien point reste inoffensif
pour la récupération courante ; l'historique reste accessible explicitement.
Une panne Qdrant/embeddings retourne un résultat FTS marqué `fts_only_degraded`.

La suppression logique est une décision propriétaire/reviewer journalisée ; elle
retire le souvenir des recherches phase 5, sans effacer révisions ni points. Le
retour arrière restaure sa visibilité. L'historique demeure consultable selon ACL.

## Commandes de laboratoire préparées

Depuis le worktree, uniquement après revue des fichiers et accords nécessaires :

```
python3 -m memory_manager.phase5.lab init --database data/phase5/lab.sqlite
python3 -m memory_manager.phase5.lab index --database data/phase5/lab.sqlite --config <config-0600> --approved-services
python3 -m memory_manager.phase5.lab rebuild --database data/phase5/lab.sqlite --config <config-0600> --approved-services
python3 -m memory_manager.phase5.lab serve --database data/phase5/lab.sqlite --config <config-0600> --approved-services
```

Configuration : `qdrant_url`/`embedding_url` exclusivement loopback via SSH,
`qdrant_token_file`, `embedding_token_file`, `embedding_manifest_sha256`,
`clients_file` (empreintes des jetons et identités/ACL), `port` (8795 par défaut),
`index_identity` (`owner`, `scopes`). Aucun jeton littéral dans la configuration.
Le runner refuse une base hors `data/phase5` et toute initialisation sur fichier
existant. Le flag CLI est un verrou d'exploitation, pas un substitut à l'accord humain.

Arrêt : Ctrl-C de l'API et fermeture des seuls tunnels de laboratoire. Revenir au
moteur FTS existant en omettant l'extension ; garder bases/accusés/collection pour
analyse. Ne jamais restaurer un snapshot par-dessus la production pour « nettoyer »
un essai.


## Validation réelle A1

Preuve `JARVIS_2_PHASE5_A1_QDRANT_REAL.json` : Qdrant 1.20.0 restauré, comptage exact
41 428, schéma vectoriel et index de payload identiques, requête sans payload avec
vecteur synthétique réussie, authentification vérifiée. Instance temporaire arrêtée.
L'essai réussi a utilisé `PrivateNetwork=yes`, une configuration YAML, le port
16333 uniquement dans ce réseau privé et des appels de contrôle via `nsenter`.
Les limites cgroup ont été lues dans le noyau : memory.max=268435456,
memory.swap.max=0, cpu.max=50000 100000. Le plafond mémoire a été atteint sans
OOM détecté ; ne pas confondre le pic cgroup (256 Mio) avec le RSS relevé (167,65 Mio).

Le lanceur `ops/phase5-qdrant-a1.py` possède une option `--reuse-manifest` qui
revérifie taille/SHA256 et prépare une nouvelle destination vide. Il ne remplace
aucune collection existante et son unique POST autorisé sur l'instance principale
est la création du snapshot historique. Lors d'A1, l'endpoint expérimental n'était pas activé ; il l'est depuis A2.

## Résultat réel A2 et accès préparé pour B

Pipeline `06b237c33b5ff8824befda657bc3c210751771a4138c3af54b12367ae8ba4c7f`,
384D Cosine, poids existants uniquement, chemins et cinq fichiers vérifiés,
`HF_HUB_OFFLINE=1` et `TRANSFORMERS_OFFLINE=1`. Aucun modèle supplémentaire.
Le transport `phase5/ssh_transport.py` ne permet que GET de cette collection,
PUT points avec wait=true, POST points/query et POST /v1/embeddings ; aucun delete.
Les clés restent consommées dans CT205 ; SSH vérifie la clé hôte.

Les 12 contrôles synthétiques réels vérifient reprise/reconstruction stable,
correction/historique, relecture SQLite et isolation. La paraphrase sans FTS
retrouve la configuration au rang 1 sur trois souvenirs actuels ; pas de seuil
calibré. Les contributions de fragments sont dédupliquées avant fusion des rangs.
Le service Qdrant principal est resté PID 11122 et l'historique à 41 428 points.
Preuves `JARVIS_2_PHASE5_A2_REAL.json`. B Windows reste soumis à accord séparé.

## Mise à jour après essai B autorisé

Hermes/Ollama ont démarré temporairement puis ont été arrêtés proprement. Le relais
a refusé la première inférence : réserve 64 000 incompatible avec plafond 50 000.
Aucun token génératif ni apprentissage nouveau ; cinq points synthétiques indexés
avant cette étape portent la collection expérimentale à onze points. Les bases
précédentes et la collection historique ne sont pas modifiées par ce pilote.
Le précontrôle de quota refuse maintenant cette incompatibilité avant démarrage.
Une enveloppe B2 à 98 304 tokens partagés est préparée, **non autorisée et non
exécutée**. Voir `JARVIS_2_PHASE5_B_RESULTS.md` pour les preuves et limites.

## Résultat B2 réel après nouvel accord

Trois missions natives Windows réussies, 8 appels Qwen/RTX, 37 918 tokens sur
un budget partagé 98 304 : correction avec historique et sources, compétence
candidate évaluée 3/3 et 16/16, récupération après redémarrage du runtime et retour
d'expériences de missions antérieures. Aucun élément publié. Jobs et tunnels
arrêtés, fenêtre fermée, données synthétiques conservées ; 16 points expérimentaux.

Le verdict strict du lanceur reste en échec car la requête Hermes avait aussi des
hits FTS. Le contrôle hôte séparé avec filtre knowledge réussit sans FTS. Aucune
validation sur données personnelles ni déploiement. Quelques arguments d'outils
présentent un encodage d'accents à diagnostiquer. Les garanties indépendantes de
permissions/publication restent en place ; aucune amélioration intrinsèque de la
résistance de Qwen aux injections n'est déduite de ce succès guidé.
Preuves et limites : `JARVIS_2_PHASE5_B2_RESULTS.md`.
