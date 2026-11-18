# JARVIS 2 — Évaluations et résultats

## Phase 2

`python3 scripts/evaluate_memory.py --phase2` conserve les 20 tests ci-dessous,
les régressions sélectionnées et ajoute 29 tests dans
`memory_manager.phase2.test_integration`, puis le benchmark simulé. Rapport :
`JARVIS_2_PHASE2_TEST_RESULTS.json`. Les appels HTTP sont réels sur endpoints
locaux simulant Ollama et Hermes ; aucun runtime réel de ces produits n’est
testé. La sandbox OS est réellement exécutée. Les cas GPU concernent le gate
sur télémétrie synthétique, pas une mesure d’inférence RTX. Le pilote GPU autorisé a depuis exécuté 14 inférences réelles séparément ;
voir [résultats et limites](JARVIS_2_PHASE2_GPU_PILOT.md). Voir le
[rapport phase 2](JARVIS_2_PHASE2_REPORT.md) pour le détail des scénarios et limites.

## Exécution reproductible

`python3 scripts/evaluate_memory.py` exécute le banc du prototype puis des
régressions ciblées existantes. Rapport machine : `JARVIS_2_TEST_RESULTS.json`,
commandes, codes de sortie et sorties exactes. L’environnement enfant a un HOME
temporaire et ne reçoit pas les clés de fournisseurs. Aucun appel réel de modèle,
aucune injection dans la mémoire réelle, aucun service HA piloté.

## Sept scénarios obligatoires

| Scénario | Preuve automatisée et portée |
|---|---|
| 1 — Correction | 4 capacités différentes puis 4 × 1 kg ; une seule mémoire active, historique antérieur intact, source utilisateur attribuée, journal de correction |
| 2 — Contradiction | 2 sources acceptées incompatibles : deux valeurs retournées disputed avec références croisées, aucune résolution inventée, pas d’export validé |
| 3 — Projet | Décision polling puis events au même identifiant ; requête projet retourne le plan actuel, historique conserve l’ancien |
| 4 — Expérience | Épisode technique et leçon liée ; recherche d’épisode le qualifie analogy_only ; relation vise une version précise |
| 5 — Compétence | v1 échoue sur des capacités différentes ; v2 passe les 3 cas et conserve les cas précédemment passants ; downgrade/reviewer absent refusés |
| 6 — Redémarrage | Processus enfant tué via os._exit après écriture non commitée ; réouverture SQLite et reprise, curseur atomique, aucune proposition doublée ; registre mission conservé après réouverture |
| 7 — Sécurité | Texte externe impératif reste inferred ; vérification/correction refusées, fait validé conservé ; aucun outil HA dans le MCP ; tests ACL et approbations complémentaires |

Un test combiné démontre en laboratoire : observer une configuration → corriger
sans perte → consolider → vérifier via une mesure synthétique de confiance →
redémarrer → retrouver avec provenance → appliquer la procédure → évaluer
l’échec historique → produire le manifeste de la version améliorée.
Ce cycle est démontré par des composants déterministes et des fixtures, pas
par une mission autonome réelle de Gemini/Hermes.

## Tests complémentaires du socle

Le banc comporte **20 tests** : atomicité d’un lot invalide, rejeu identique et
collision de clé, corrections concurrentes, annulation compensatrice, triggers
de révisions immuables, validité temporelle, refus de vérification par source
modèle, ACL privées/partagées et relations, vector hits périmés, schéma additif
répétable, refus d’une autre base canonique, rejet de secrets, backup WAL avec
empreinte et restauration consultable, pause/reprise, budget d’échecs, statistiques
hebdomadaires, refus de capacités physiques de mission, blocage de l’approbation
y compris via pause, indexeur injecté idempotent et collection réservée refusée.

L’API HTTP est réellement démarrée sur un port loopback temporaire : 401 sans
authentification valide, 403 sur tentative de promotion, proposition idempotente.
Le pont MCP est exécuté dans un processus neuf ; handshake, liste des outils
et recherche traversent réellement stdio → HTTP → SQLite. Le token synthétique
n’apparaît pas dans sa sortie.

## Régressions existantes sélectionnées

- `test_store.py`, `test_spaces.py` : import, déduplication et séparation logique.
- `test_conversations.py`, `test_voice_memory.py` : 7 tests sur bases temporaires.
- `semantic/test_search.py` : 6 tests de recherche avec transport sémantique simulé.
- `test_codex_worker.mjs` : app-server simulé, threads, interruption sans rejeu.
- `test_user_corrections.mjs` : preuve de correction actuelle, portée et persistance.
- `test_home_assistant.mjs` : réseau entièrement simulé, restrictions et readback.
- `test_hybrid_brain.mjs` : deux canaux, délégation, preflight avant effets.

Leur succès ne prouve pas que les faiblesses historiques ont été corrigées en
production : notamment le test d’oubli existant confirme la suppression de son
ancien journal. Le nouveau stockage ne réutilise pas ce comportement.

## Vérifications avant déploiement

Restent : vrai embedding et Qdrant sur collection dédiée, mesure qualité/rappel
sur corpus autorisé, charge mémoire/CPU, isolation réseau/OS, authentification
des profils, vérification immuable des sources, runtime Hermes épinglé,
broker d’approbation et arrêt d’exécutions, export/import de données réelles,
restauration de sauvegardes réelles, SSE et reconnexion, puis navigateur/iPhone
pour voix continue, barge-in et mute. Aucun de ces contrôles n’est déclaré passé
par ce banc local. Aucune publication ou installation ne résulte des tests.

## Résultat phase 3 observé le 14 novembre 2026

Un premier cycle Hermes officiel + Qwen4B sur RTX3080 + mémoire canonique a
réussi en laboratoire. Le runtime épinglé exige 64000 tokens ; le profil
préparatoire8192 n’est pas compatible. Sources, mesures, limites et procédure
de reprise sont dans [JARVIS_2_PHASE3_REPORT.md](JARVIS_2_PHASE3_REPORT.md).
La VM102 est arrêtée et les allocations des invités existants sont restaurées.
La mission compétence est inachevée, Qdrant réel et gateway restent différés.

## Suivi compétence phase3

Le banc phase3 comporte désormais40 tests : persistance évaluation/compétence
après réouverture, consultation MCP, isolation propriétaire, publication refusée,
schéma fermé, appels physiques/shell non annoncés, grants hôte indépendants,
comptabilisation des refus, HOME natifs distincts, VRAM invalide et précontrôle
Qdrant sans écriture. Les tests du nouveau cycle sont locaux/simulés ; la preuve
native correspondante est attendue après autorisation A/B du plan de reprise.
