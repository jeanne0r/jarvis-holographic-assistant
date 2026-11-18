# Phase 5 — Mémoire réelle : préparation contrôlée

État au 14 novembre 2026. Développement exclusivement dans `jarvis-2-memory`, branche
`codex/jarvis-2-memory-20261113`. Les preuves Windows de phase 4 sont conservées.
Aucun redémarrage Hermes/Ollama, import personnel dans le Memory Manager ou
raccordement à la gateway active. A1 : sauvegarde/restauration vérifiées. A2 :
extension embeddings activée après accord et redémarrage contrôlé, collection
expérimentale créée avec 6 points synthétiques. Aucun changement de points historiques.
Voir `JARVIS_2_PHASE5_A1_RESULTS.md` et `JARVIS_2_PHASE5_A2_RESULTS.md`.

## Architecture conservée

Gemini Live et Jarvis conservent leur fonctionnement actuel. Le bridge et SQLite
restent sur Proxmox ; Hermes reste natif Windows, à côté d'Ollama et de la RTX.
Les accès mémoire Hermes passent par le MCP contrôlé et l'API authentifiée ;
les recherches MCP peuvent maintenant utiliser le même moteur hybride que l'API.
Aucun second stockage canonique n'est introduit.

`SQLite + FTS5 → indexeur borné → Qdrant expérimental → références → relecture SQLite/ACL/validité → MCP → Hermes`

Les propositions d'Hermes restent `inferred`. Les corrections exigent toujours une
source autorisée et la révision attendue. Une déclaration utilisateur conserve ce
statut, distinct d'une mesure vérifiée. Les expériences restent des analogies.
Les résultats en contradiction sont explicitement marqués, jamais départagés par
un score vectoriel.

## Code livré

- `memory_manager/phase5/database.py` : migration additive explicite, sauvegarde
  SQLite vérifiée avant migration, manifeste SHA256 privé, visibilité logique et
  journal réversible. Aucun effacement de fait ou de révision.
- `vector.py` : identité du pipeline d'embeddings, découpage borné, index versionné,
  accusés persistants, réindexation explicite et récupération hybride.
- `api.py` : extension facultative des routes mémoire/MCP existantes.
- `embedding_endpoint.py` et patch `semantic/service.py` : endpoint brut déployé sur CT205 après accord,
  réutilisation de l'instance existante, identité distincte, activation désactivée
  par défaut et protection du démarrage historique.
- `import_plan.py` : planificateur pur d'import à blanc, maximum 500 propositions
  structurées par lot ; aucune écriture ni extraction implicite de conversations.
- `skills.py` : évaluation élargie et manifeste de version prêt à relire, sans
  publication ni autorisation d'exécution.
- `jarvis-hermes-experimental.mjs` : adaptateur Node 18 inerte par défaut, sans
  import de backend de production. Aucun agent dans le traitement HTTP.
- `lab.py` : initialisation explicite et runner d'index/API exclusivement dans
  `data/phase5`. Aucun provisionnement Qdrant ni démarrage Windows.

## Inventaire réel et import à blanc

L'inventaire des bases existantes a été effectué via SQLite en lecture seule,
avec `query_only`, sans importer les modules applicatifs qui pourraient migrer
les bases. Seuls schémas, nombres et plages de dates ont été exportés.
Voir `JARVIS_2_PHASE5_IMPORT_INVENTORY_REAL.json`.

| Source | Volume observé | Interprétation |
|---|---:|---|
| brain.docs | 1 287 | 627 ChatGPT, 347 Codex, 176 Jarvis, 137 Mémoire |
| conversation_sessions / conversation_turns | 84 / 176 | historique local, pas une liste de faits validés |
| voice-memory.facts | 2 | faits actuels à revoir selon leur provenance |
| voice-memory.correction_events | 0 | aucune correction enregistrée dans cette table à l'inventaire |
| semantic-index.indexed | 1 289 | registre d'indexation, aucune autorité factuelle |
| Qdrant historique | 41 407 points | fragments, pas 41 407 faits indépendants |

Aucun doublon de fingerprint dans un même espace n'a été observé. Cela ne démontre
pas l'absence de doublons sémantiques. Une ancienne version déjà écrasée et absente
des historiques ne peut pas être reconstituée avec certitude.

Le rapport personnel à blanc à produire après autorisation doit suivre ces étapes :

1. Choisir une seule personne, un projet et au plus 20 sources ; établir une
   correspondance d'identité côté serveur. Les anciens noms d'espace sont des
   étiquettes, pas des ACL.
2. Ouvrir un snapshot cohérent privé de chaque base concernée. Conserver base,
   table, clé, révision/empreinte, horodatage original et rôle de l'auteur.
3. Structurer des propositions dans un fichier privé de laboratoire. Le
   planificateur n'interprète pas arbitrairement le corps d'une conversation.
   Une extraction par modèle nécessitera l'autorisation d'utiliser ces textes.
4. Dédupliquer dans le même propriétaire/périmètre. Ne jamais fusionner entre
   utilisateurs sur la seule similarité. Conserver toutes les références.
5. Signaler valeurs incompatibles, dates manquantes et remplacements revendiqués.
   `replaces_claim` reste une indication à vérifier, jamais une correction active.
6. Produire nombres, références privées et décisions attendues. Tout candidat
   reste `inferred`, même si l'ancienne base le qualifiait de « fait ».
7. Faire relire le rapport avant toute ingestion. L'importeur d'écriture massif
   n'est volontairement pas activé ni livré comme action automatique.

À ce stade, seul ce plan et l'inventaire agrégé sont réels ; le planificateur de
contenu est testé sur des lignes synthétiques. Aucun rapport ne prétend avoir
analysé les conversations personnelles.

## Démonstration préparée

Créer une nouvelle base de laboratoire exclusivement synthétique, ingérer une
ancienne configuration puis sa correction, indexer uniquement la révision active,
rechercher par paraphrase via les vrais embeddings et Qdrant expérimental, faire
lire les sources à Hermes, enregistrer une expérience puis proposer une compétence.
L'évaluer sans publication, arrêter complètement les processus du laboratoire,
relancer une nouvelle mission avec une nouvelle clé et retrouver la même version,
son empreinte et ses sources. Ne jamais relancer une ancienne mission ambiguë.

L'essai local actuel utilise une vraie SQLite, l'API HTTP locale et les registres,
mais un émulateur d'agent et des vecteurs constants. Il vérifie la mécanique et
les droits, pas la pertinence sémantique ni l'apprentissage d'un modèle réel.

## Ordre de validation

1. Revue du patch et autorisation CT205 ; sauvegarde et restauration isolée.
2. Endpoint d'embeddings et collection expérimentale ; essais synthétiques sans
   Windows, vérification des empreintes, reprise et reconstruction de l'index.
3. Fenêtre Windows bornée autorisée ; reproduction du cycle complet avec Hermes
   épinglé et le modèle déjà présent, aucun téléchargement.
4. Autorisation séparée pour un échantillon personnel et rapport à blanc privé.
5. Revue d'identité/ACL et patch gateway séparé avant toute activation Jarvis.

Les autorisations précises, risques et retours arrière sont regroupés dans
`JARVIS_2_PHASE5_REPORT.md`.

## État après A2

Les étapes 1 et 2 sont réellement réussies, dont une paraphrase sans résultat FTS,
correction canonique et reconstruction sans doublon. L'ancien inventaire de
41 407 points reste un relevé daté ; le compteur historique avant/après A1/A2 est
41 428. Pas de nouvelle analyse de contenu personnel.

Le pilote `native_lab.py` et `scripts/pilot_phase5_windows.py` prépare l'étape 3 :
base neuve, budget partagé, trois missions et arrêt des seuls runtimes possédés.
Aucun démarrage Windows effectué. Voir `JARVIS_2_PHASE5_B_TRIAL_PLAN.md`.

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
