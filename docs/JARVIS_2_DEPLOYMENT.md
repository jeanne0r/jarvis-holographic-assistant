# JARVIS 2 — Préparation et déploiement soumis à accord

État actuel : le [pilote natif Windows de phase4](JARVIS_2_PHASE4_REPORT.md) a réussi après accord. Hermes est installé sur GAMER, ses processus temporaires sont arrêtés, aucune activation production ou permanente. Les paragraphes de phases antérieures ci-dessous restent historiques.

## Pilote de phase 2, toujours hors production

La RTX est sur Windows Gamer, 10Go ; architecture proposée : Ollama loopback
Windows, tunnel SSH privé, Hermes/Memory Manager isolés sur Proxmox. Ollama
a été démarré temporairement après accord, testé puis arrêté ; les résultats
sont dans [le rapport du pilote](JARVIS_2_PHASE2_GPU_PILOT.md). Le modèle existant
échoue au test de permissions : pas d’activation autonome sensible. Aucun
service ni réglage de minage n’a été modifié. L’accord ne couvre pas les
téléchargements, installations ou une activation permanente.

Après accord pour une préproduction dédiée :

1. Créer une nouvelle base laboratoire via `python3 -m memory_manager init`.
2. Exécuter explicitement `phase2.database.migrate(Memory(chemin_laboratoire))` ;
   cette opération sauvegarde et vérifie avant DDL additif. Ne pas utiliser un
   chemin de base réelle.
3. Configurer des tokens/acteurs distincts : simulateur Jarvis (reader,
   mission_writer), Hermes (reader, proposer), worker d’exécution (reader,
   mission_worker), humain (reader, human_approver, reviewer). Le pipeline de
   confiance a ses propres droits ingester/consolidator/metered_caller ;
   budget_admin n’est jamais accordé à un modèle.
4. Lancer l’API de laboratoire avec `python3 -m memory_manager.api --phase2`
   et les arguments database/clients-file/port existants. Les routes de missions
   sont ajoutées par cette option seulement. SSE renvoie des pages finies ;
   le client se reconnecte avec Last-Event-ID.
5. Après autorisation Windows, démarrer temporairement le binaire Ollama
   existant sur 127.0.0.1 ; tunnel SSH local 127.0.0.1:11435 vers Windows
   127.0.0.1:11434 avec la clé existante et StrictHostKeyChecking=yes.
   Ne pas ouvrir de port Windows au réseau public ou au LAN entier.
6. Actualiser la télémétrie par `python3 scripts/audit_gpu.py --loop` (lectures
   SSH uniquement), vérifier version/API, modèle/digest local et lancer le
   benchmark réel avec sa configuration explicite. Aucun pull automatique.
7. Installer Hermes au commit du manifeste uniquement après accord. Le profil
   a un HOME neuf, mémoire native désactivée, MCP contrôlé, skills publiées en
   lecture seule, outils système/physiques absents et réseau limité à l’inférence
   locale et au Memory Manager. Appliquer les quotas de tous ses appels/enfants
   au même broker ; les paramètres de prompt ne suffisent pas.
8. Le worker séparé lit une configuration 0600. Par défaut enable_live=false.
   Un lancement réel exige enable_live=true et les revues de profil/réseau,
   hermes_base_url privée, token_file privé, modèle fixé, owner/scopes et chemin
   de la base laboratoire. Les booléens de revue n’appliquent pas eux-mêmes
   l’isolation : monter les barrières OS d’abord. `--loop` traite la file toutes
   les 5s ; sans option, un seul passage. Aucune unité systemd n’a été installée.

La collection Qdrant et le endpoint d’embeddings attesté restent une étape
distincte : exact `jarvis_knowledge_experimental_v1`, modèle MiniLM attendu et
empreinte des artefacts à relever sur le service réel avant configuration.
Les snapshots/restaurations et la revue du patch exact précèdent tout déploiement.
Le worker conversationnel existant n’est jamais appelé par le nouveau worker.

Repli : arrêter le nouveau worker/API, garder base/événements et retirer le
tunnel privé. Une livraison ambiguë passe unknown ; ne pas la rejouer ou
déployer un résultat sans réconciliation et revue. Voir le
[rapport de phase 2](JARVIS_2_PHASE2_REPORT.md).

## État actuel

Branche de développement `codex/jarvis-2-memory-20261113`, worktree séparé du
checkout utilisé par la gateway. Aucun fichier de production déployé ou modifié,
aucun service redémarré, aucune base réelle migrée. Hermes officiel est une copie
de référence seulement : pas d’installation, activation, credentials ou appel API.
Les fichiers data/ et les archives Qdrant non suivies préexistantes sont préservés.

## Reproduire le laboratoire

Depuis le worktree de développement, Python3.12 existant suffit :

```bash
python3 -m unittest discover -s memory_manager/tests -v
python3 scripts/evaluate_memory.py
```

Pour explorer manuellement, créer un répertoire privé neuf et une base dédiée :

```bash
mkdir -m 700 data/memory-lab
python3 -m memory_manager init --database data/memory-lab/memory.sqlite
python3 -m memory_manager backup --database data/memory-lab/memory.sqlite --destination data/memory-lab/backup-001.sqlite
```

Ces commandes refusent les destinations existantes. Ne jamais remplacer le
chemin de laboratoire par brain.sqlite ou voice-memory.sqlite.
L’API se lance explicitement avec un fichier clients privé créé hors Git :

```bash
python3 -m memory_manager.api --database data/memory-lab/memory.sqlite --clients-file data/memory-lab/clients.json --port 8791
```

Format clients : objet dont chaque clé est SHA256 d’un token aléatoire ; valeur
`name`, `scopes` et `roles` (`reader`, éventuellement `proposer`). Le token clair
se conserve dans un fichier 0600 séparé pour le client MCP. Ne pas réutiliser ni
copier le token gateway, une clé Qdrant ou les credentials HA. Ne pas publier
clients.json ou le fichier token. L’API n’initialise pas la base et n’écoute
jamais une adresse publique.

Routes effectivement disponibles : GET `/v1/health`, GET `/v1/search?q=...`
(type, subject et limit optionnels), GET `/v1/history?memory_id=...`,
POST `/v1/proposals` (key, reference, candidates, scope optionnel).
Toutes exigent un token ; seul le canal inferred est ouvert en écriture HTTP.

## Étapes proposées après validation humaine

1. **Préproduction** : compte/VM isolé, données synthétiques, pas de secrets HA.
   Fixer ACL, ressources, permissions, stockage et sauvegardes. Tester l’API et
   le MCP avec l’Hermes épinglé seulement après autorisation de son installation
   et d’un budget de fournisseur. Aucun script d’installation distant implicite.
2. **Sauvegardes réelles** : sur fenêtre autorisée, API SQLite backup de chaque
   magasin concerné et manifestes de contrôle ; restaurer dans un chemin neuf,
   vérifier intégrité, schéma et comptes. Snapshot Qdrant et sauvegarde Proxmox
   vérifiés/restaurés en isolation avant tout changement CT205. Archiver les
   manifestes sans données sensibles dans Git et les sauvegardes hors Git.
3. **Import à blanc** : extracteur en lecture seule, manifestes idempotents ;
   importer sources et références dans une nouvelle base, sans promotion
   automatique des historiques. Produire rapport doublons/corrections/ambiguïtés.
   Aucun import des conversations réelles n’a été fait dans ce travail.
4. **Index dédié** : provisionner `jarvis_knowledge_experimental_v1` avec schéma
   384D cosine vérifié ; embeddings locaux identiques et modèle/version enregistrés.
   Ajouter un endpoint embeddings indépendant après revue et sauvegarde.
   Ne jamais appeler le prune global de `jarvis_memory_v1` pour ce magasin.
5. **Observation** : ingress/outbox après sauvegarde de conversation, capture
   des messages originaux et des mesures attribuées ; traitement hors requête
   vocale, erreur du Memory Manager sans rupture de la conversation.
6. **Lecture graduelle** : requêtes parallèles comparées hors réponse publique,
   évaluation des ACL, des corrections, rappel/provenance et latence ; ensuite
   feature flag de lecture avec retour immédiat au chemin historique.
7. **Consolidation** : lancer manuellement en simulation, relire les propositions ;
   activer timers nocturnes/hebdomadaires après quotas et métriques. Ne pas
   automatiquement archiver, fusionner ou déclasser les mémoires existantes.
8. **Missions** : implémenter broker d’approbation et SSE, exécuteur Codex isolé,
   puis raccordement Hermes ; première mission sans commande physique ni déploiement.
   Toute publication de code/config production conserve une validation humaine.

## Retour arrière et critères d’ouverture

Désactiver le feature flag puis stopper le nouveau service, en conservant sa
base et son journal. Ne pas restaurer une ancienne base sur une base ayant reçu
des écritures récentes ; restaurer dans un nouveau chemin et comparer/rejouer
les événements explicitement. Les anciens magasins restent utilisables.

Avant ouverture : tests synthétiques passants, restauration réellement prouvée,
tests de charge et isolation, ACL revues, preuves immuables, budgets/fail-closed,
tests de voix/barge-in/mute sur iPhone, qualité du véritable embedding,
notifications limitées et approbation du patch exact de production.
Le banc local livré ne remplace pas ces vérifications de déploiement.

## Résultat phase 3 observé le 14 novembre 2026

Un premier cycle Hermes officiel + Qwen4B sur RTX3080 + mémoire canonique a
réussi en laboratoire. Le runtime épinglé exige 64000 tokens ; le profil
préparatoire8192 n’est pas compatible. Sources, mesures, limites et procédure
de reprise sont dans [JARVIS_2_PHASE3_REPORT.md](JARVIS_2_PHASE3_REPORT.md).
La VM102 est arrêtée et les allocations des invités existants sont restaurées.
La mission compétence est inachevée, Qdrant réel et gateway restent différés.

## Décision du 14 novembre2026 — phase4 Windows

L'hébergement Hermes passe au PC GAMER Windows natif ; la stratégie de récupération
RAM Proxmox et de réservation4Gio est abandonnée provisoirement. VM102 reste
arrêtée sur disque ; allocations103/201 et absence de gardien vérifiées en lecture
seule. Les anciennes preuves et composants sont conservés. Aucun nouveau
démarrage/installation autorisé par cette note. Plan courant :
[JARVIS_2_PHASE4_WINDOWS_PLAN.md](JARVIS_2_PHASE4_WINDOWS_PLAN.md).
