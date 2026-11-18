# JARVIS 2 — Audit de l’existant

Complément phase 2 : le worktree a été retrouvé à `c6dda50`, propre, puis prolongé
sur la même branche. Audit GPU en lecture seule : Windows Gamer joignable via
SSH, RTX3080 10Go ; exécutable Ollama installé sans API active. Le nouveau code
Hermes officiel a une API native /v1/runs vérifiée ; aucune installation faite.
Preuves et limites : [audit GPU](JARVIS_2_PHASE2_GPU.md),
[rapport phase 2](JARVIS_2_PHASE2_REPORT.md). L’audit initial suivant reste daté
et n’est pas réinterprété comme un nouvel état de production.

Audit en lecture seule le 13 novembre 2026. Référence JARVIS :
`2d40cc2` (branche de production observée). Développement isolé :
`codex/jarvis-2-memory-20261113`, worktree `jarvis-2-memory`.
Les fichiers non suivis déjà présents dans `semantic/` n’ont pas été déplacés.

## Périmètre et preuves

La gateway active a pour répertoire de travail `/home/user/gateway`.
Son `server.js:1` importe directement `jarvis/backend.mjs` depuis le workspace ;
`routeRequest` délègue `/api/jarvis/*` à `handleJarvis`. Le HTML servi vient de
`gateway/public/jarvis`. Le dépôt `jarvis-holographic-assistant` est une autre
copie versionnée (HEAD observé `17c4d31`), pas la cible de cet import.
Modifier le checkout principal serait donc potentiellement modifier la production.

Preuves consultées : sources citées ci-dessous, schémas SQLite via connexions
`mode=ro`, propriétés systemd sans environnement ni secrets, et GET authentifié
`/health` du pont sémantique. Aucun appel modèle, commande HA, déploiement,
redémarrage ou migration de données réelles durant cet audit.

## Capacités observées

| Domaine | Existant et preuve | Limite observée |
|---|---|---|
| Serveur | Node 18.19.1 ; gateway HTTP/HTTPS, modules ESM `backend.mjs`, processus Python SQLite ; dépendances gateway `ws`, OCR et image | Chemins absolus couplés au déploiement ; pas de package.json propre au dépôt actif |
| Interface | `public/` : hologramme, mémoire 3D, fenêtres, conversation iPhone, interruption et mute | Sources et fichiers statiques servis sont deux emplacements distincts |
| Routage | `ai.mjs`, `core-settings.mjs`, `hybrid-brain.mjs` : Codex, Gemini fast/live ou hybride ; classification Gemini, délégation locale | Classification distante avec coût ; ce n’est pas une autorisation d’action |
| Voix | `speech.mjs`, `public/codex-voice.js`, `voice-gate.js`, `live.mjs` ; STT/TTS et mode Live ; archivage des tours | Mémoire de page/historique court distinct de l’archive durable |
| Archive | `store.py` : notes, imports ChatGPT, synchronisation `_memory` et sessions Codex, FTS5, empreintes et tours révisables | `INSERT OR REPLACE` : un document ou tour révisé ne garde pas toutes ses versions |
| Faits | `voice-memory.py` : faits explicites, alias HA, journal de corrections ; `user-corrections.mjs` vérifie citations et rejette certaines injections | 64 faits/espace ; journal limité à 512 événements ; sauvegarde simple et oubli effacent des corrections |
| Apprentissage | `ha-learning.py/.mjs` : repères de recherche HA appris depuis observations ; invalidation des repères contradictoires | Cache de correspondances, pas apprentissage/versionnement d’une procédure technique |
| Recherche | `semantic/search.py` : fusion textuelle/vectorielle, faits SQLite, filtre espace, validation version et existence contre SQLite | Pas de temporalité métier, contradiction ou statut de validation unifié |
| Vectoriel | `semantic/service.py` : Qdrant `jarvis_memory_v1`, cosine 384D ; FastEmbed local `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` ; chunks 400 caractères, chevauchement 60 | Modèle borné en tokens ; précision à évaluer sur les longs passages et références techniques |
| Indexation | `semantic/index.py` : verrou flock, table indexed, reprise incrémentale, priorité aux tours récents ; timer systemd actif | `/prune` est global à la collection, dangereux pour tout nouveau producteur partageant cette collection |
| Profils | `user`, `amelie`, `malik`, `theo`, `commun` ; sélection via paramètre `space`, faits communs lisibles | Segmentation logique, pas authentification individuelle ni ACL forte observée |
| HA | `home-assistant.mjs` : états, registres, catalogue des services ; cibles exactes consultées, paramètres contrôlés, pas de rejeu automatique | Domaines autorisés larges : switch, climate, script, automation, valve, etc. Pas d’interverrouillage physique indépendant démontré |
| Exécutant Codex | `codex-worker.mjs` : app-server chaud, threads éphémères, MCP privé, interruption, délai de 300 s, outils limités à 30 appels | Shell et réseau actifs ; workspace-write incluant les statiques de production ; HOME disponible ; ce n’est pas un confinement de mission autonome |
| Développement | `evolution.mjs` : branche/worktree, proposition de fichiers bornés, refus symlinks, syntaxe JS, commit et patch ; pas d’installation automatique | État JSON, drapeau running en RAM ; interruption signalée après délai, pas reprise transactionnelle ; syntaxe seule ne prouve pas l’absence de régression |
| Tâches | timers indexation et facturation ; sync archive toutes les 5 min dans backend | Pas de registre général de missions persistantes ni budget central ; aucune consolidation nocturne/hebdomadaire générale observée |

La configuration locale `data/core-engine.json` sélectionne effectivement **hybrid**.
Le GET du pont sémantique a répondu `ready=true`, collection `jarvis_memory_v1`,
modèle ci-dessus, **41 223 points** au moment de l’audit. Il ne prouve pas
l’exhaustivité de l’index. Un GET authentifié ultérieur `/collections` ne liste
que `jarvis_memory_v1`. Les versions effectives des binaires du CT n’ont pas été
contrôlées directement. Le README
sémantique documente Qdrant 1.20.0 et CT205 ; ce sont des indications de
déploiement, distinctes de l’observation du service.

## Schémas SQLite effectivement présents

Inspection des noms de colonnes, sans extraction de conversations :

- `brain.sqlite` : `docs(id,title,body,kind,topic,status,source,updated,fingerprint,space)`,
  FTS5 `search(id,title,body)`, `meta(key,value)`,
  `conversation_sessions(id,space,channel,created)`,
  `conversation_turns(session_id,turn,revision,user,assistant,status,updated)`.
- `voice-memory.sqlite` : `facts(space,key,label,fact,entity_id,area,updated)`,
  `correction_events(id,space,key,kind,previous_fact,new_fact,evidence,updated)`.
- `ha-learning.sqlite` : `hints(key,space,query,filters,entities,uses,updated)`.
- `semantic-index.sqlite` : `indexed(doc_id,version,updated)`.
- `voice-usage.sqlite` : `settings`, `sessions`, `reports` (comptabilité, hors migration mémoire).
- `before-spaces.sqlite` existe ; autres sauvegardes avant modifications dans
  `data/before-*`. README demande l’API SQLite backup compatible WAL.

`store.py` crée les tables à l’ouverture et ajoute `space` sous transaction,
sans registre général de migrations. `voice-memory.py` normalise des clés à
l’ouverture et peut fusionner/remplacer des lignes. Ne pas importer ces scripts
pour un audit en lecture seule. Des sauvegardes historiques et sauvegardes
Proxmox sont documentées, mais leur restauration n’a pas été démontrée ici.

## Risques et recommandations

1. **Accès** : les routes JARVIS sont déléguées avant `handleApi`, sans appel
   observé à `isAuthorized`. Le contrôle Origin de certaines écritures n’est pas
   une authentification. Ne pas transformer les profils actuels en ACL supposées.
   Ajouter une identité serveur et des droits vérifiés au futur service isolé.
2. **Historique** : ne pas réutiliser les opérations d’oubli/remplacement comme
   mécanisme de correction canonique. Conserver les versions et changements de
   pointeur actif ; annulation par nouvelle révision compensatrice.
3. **Production** : le shell du worker actuel et les outils HA ont des capacités
   excessives pour des missions autonomes. Nouveau compte isolé, réseau filtré,
   aucune donnée secrète ou capacité HA physique dans l’exécutant expérimental.
4. **Index** : collection dédiée pour les connaissances structurées, jamais
   `jarvis_memory_v1` ; son prune supprimerait les nouveaux points. Valider toute
   réponse vectorielle contre la révision SQLite courante et les ACL.
5. **Vérité** : citation utilisateur = déclaration attribuée, pas mesure réelle.
   Distinguer inférence, observation et vérification ; aucune promotion par modèle.
6. **Durabilité** : outbox, checkpoints transactionnels et délais/budgets ; ne
   pas utiliser les timers du processus vocal pour exécuter des missions longues.
7. **Réutilisation** : garder interface, voix, routage, SQLite/FTS5, service
   d’embeddings, outils consultatifs HA et approche worktree. Le Memory Manager
   expose un contrat indépendant du fournisseur IA.

## Écarts à combler et incompatibilités

Manquent : six types unifiés, relations, validité, révisions complètes, provenance
vérifiable par révision, contradictions, décisions projet actuelles, consolidation
auditable, évaluations de compétences, registre de missions avec approbations.
Hermes n’est pas trouvé dans PATH ni dans les services utilisateur inspectés ;
cela ne démontre pas son absence sur les autres machines Proxmox.
Pas de remplacement ni réinstallation nécessaire pour amorcer ces travaux.

Le second dépôt exige Node >=22.6 alors que la gateway active tourne sur Node18 :
une fusion aveugle serait incompatible. Hermes ajoute sa propre mémoire et ses
propres profils : ne pas recopier les faits canoniques dans ses fichiers persistants.
Son code officiel est étudié séparément et épinglé dans le document d’intégration.
