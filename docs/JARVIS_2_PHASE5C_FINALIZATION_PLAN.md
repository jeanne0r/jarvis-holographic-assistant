# Phase 5C — Terminer C1 et débloquer C2

## Diagnostic établi sans nouvel appel au modèle

Le deuxième essai reste **`passed=false`**, et B2 aussi. La preuve réelle de
recherche sémantique par Hermes avec zéro hit FTS et revalidation SQLite est
conservée sans modification.

La consultation **en lecture seule du seul état synthétique** Windows, session
`run_69674fdee77a401c885f6bcae6da8e71`, a retrouvé les arguments des appels :

1. `jarvis_memory_knowledge(q="masse nominale identique")`.
2. `jarvis_memory_history(memory_id="synthetic://doselab/old")`.

Ils appartiennent au même lot `pilot-51b76925-2838-495e-bc0a-b2e559db5371`.
L'historique a donc été demandé avant de pouvoir exploiter le résultat de recherche,
avec une référence de source au lieu du `memory_id` stable. La base canonique
recherche cet identifiant dans `mm_memories.id` ; la référence fournie n'y existe
pas. Ce chemin de refus est reproduit hors ligne, sans élargir l'ACL.
La preuve SSE originale ne suffisait pas à attribuer cette cause ; la nouvelle
extraction ciblée la complète : `JARVIS_2_PHASE5C_C1_HISTORY_TRACE.json`.
Aucun log général, secret ou conversation personnelle n'a été extrait.

La réponse finale utilisait par ailleurs des UUID au lieu de
`synthetic://doselab/correction`, pourtant présent dans le résultat de l'outil.
Le champ n'était pas absent : il a été mal interprété par le modèle.

## Correctif minimal préparé, non déployé

- Consigne : attendre la recherche, utiliser son `memory_id` pour l'historique,
  citer littéralement `source.ref` dans la réponse finale. Pas d'appels dépendants
  dans le même lot. Aucun identifiant attendu injecté comme réponse.
- Contrats MCP : descriptions explicites de ces champs et de cet ordre dans la
  découverte des deux outils. Aucun changement des schémas de validation,
  permissions, ACL, résultats ou liste des capacités.
- Observation du pilote : tracer le `memory_id` reçu par l'historique, lié à la
  mission active, et l'acceptation par le même lecteur canonique. Aucun mécanisme
  de conversion automatique d'une URI ou d'une révision en identifiant stable.
- Succès global : critères précédents inchangés **et** identifiant stable attendu
  démontré dans l'appel historique réussi, avec les sources ancienne et actuelle.
  Les citations manquantes restent un échec ; aucun ajout de source par le bridge.

Un LLM ne garantit pas une citation par simple consigne. La garantie indépendante
est de **refuser le succès** si la citation exacte manque ; une validation du
correctif en conditions réelles reste nécessaire.

Tests hors ligne : MCP réel en mémoire, backend SQLite synthétique, faux vecteurs,
appel de recherche puis historique ; refus de source.ref et révision ; conservation
des révisions remplacées ; citation UUID seule rejetée ; chaînes de preuve et
permissions existantes maintenues. Ces tests ne constituent pas un troisième essai RTX.

## C1 — Troisième essai proposé, nouvel accord requis

| Opération | Machine / effet | Arrêt et retour arrière |
|---|---|---|
| Vérifier les empreintes et sauvegarder, puis modifier **un fichier** `memory_manager/phase2/mcp.py` | Laboratoire Windows `C:/JarvisHermesLab/app`, descriptions des outils seulement ; manifeste `JARVIS_2_PHASE5C_C1_THIRD_PATCH_MANIFEST.json` | Sauvegarde vérifiée avant remplacement ; arrêter les seuls Jobs possédés puis restaurer cette sauvegarde si nécessaire ; préserver les preuves |
| Un nouveau scénario strict synthétique | Contrôleur isolé Proxmox → Hermes Windows → Ollama local/RTX → MCP → SQLite labo et Qdrant expérimental | Nouvelle mission, aucun rejeu ambigu ; fenêtre 5 min, 6 appels, 98 304 tokens partagés, budget distant 0 CHF ; fermeture fenêtre/Jobs/tunnels |
| Contrôles de fin | Proxmox et Windows, traces synthétiques, ports, VRAM, compteurs | Vérifier ports fermés et ressources rendues ; conserver l'échec si un critère manque ; aucune relance automatique |

Même modèle installé, même digest, contexte 64 000 ; aucun téléchargement,
installation, compte, ACL Windows, pare-feu, RAM Proxmox ou service permanent.
Gardiens GPU/Kryptex inchangés : différer si minage actif ou ressources inadéquates,
ne jamais interrompre Kryptex. Aucune publication de compétence. Collection
historique `jarvis_memory_v1` et gateway de production inchangées.
Les nouveaux points synthétiques restent limités à la collection expérimentale.

Commandes préparées, **non exécutées** (elles exigent cet accord nouveau) :

```bash
python3 -m scripts.apply_phase5c_windows_patch --approved-c1 --retry-contract
python3 -m scripts.pilot_phase5c_semantic --approved-c1 \
  --private-state /var/lib/jarvis-memory/phase5-a2/20261114T184704Z-65701471 \
  --artifact 06b237c33b5ff8824befda657bc3c210751771a4138c3af54b12367ae8ba4c7f
```

Le premier opérateur refuse une empreinte inattendue et conserve un reçu distinct.
Le second vérifie les cinq fichiers déployés avant de lancer un nouveau runtime.
Ne pas utiliser l'ancien mode de patch : son manifeste décrit le déploiement passé.

## C2 — Reprise proposée sans nouvelle lecture personnelle

L'erreur passée ne peut pas être annulée : dix-huit documents multi-tours ne
prouvent pas le respect de vingt tours. Le rapport et sa réserve restent **bloqués**,
aucune réécriture ne le rend rétroactivement conforme.

Proposition de nouveau périmètre à approuver séparément :

1. Sélectionner au plus vingt références explicites `(session_id, turn, revision)`
   dans les tours normalisés, sans aspirer les documents de conversation. Une source
   est un couple utilisateur/assistant à une révision déterminée, définition à
   confirmer avec le nouveau lot autorisé. Une nouvelle sélection n'est pas couverte
   par l'ancien accord C2 ; aucun contenu supplémentaire lu ici.
2. Réserver durablement cette **unique liste approuvée** avant lecture, sous un
   identifiant d'autorisation distinct ; compteur maximal vingt pour ce lot, essais
   interrompus et sources écartées compris. Ne jamais créer un nouveau lot pour
   reconstituer artificiellement un quota. L'ancienne réserve reste conservée.
3. Le lecteur préparé refuse 21 références, doublons de tour même à révisions
   différentes, référence périmée, propriétaire étranger ou ligne ambiguë. Il vérifie
   **toutes les références par métadonnées avant toute projection des corps**,
   dans une transaction de lecture cohérente `mode=ro/query_only`.
4. Lire seulement ces tours, conserver sources, dates et rôles séparés ; un tour
   écarté compte et n'est jamais remplacé. Rapport local privé 0700/0600, sources
   originales inchangées, aucune transmission Windows/modèle ni index privé.
5. En cas d'arrêt après lecture partielle : conserver la réserve, arrêter ; aucune
   sélection supplémentaire automatique. La reprise du lot doit utiliser les mêmes
   références et son autorisation, jamais remettre le compteur à zéro.

Les contrôles du lecteur et les tests sont implémentés ; le nouveau lot et son
orchestration d'approbation/réservation ne sont **pas activés**. L'ancienne commande
C2 reste réservée/épuisée, pas de réutilisation automatique de son rapport.
Le lecteur de tours normalisés ne résout pas à lui seul les exports ChatGPT stockés
comme documents : leur découpage exigerait un périmètre et un accord distincts,
pas une analyse complète implicite de ces exports.

Tests synthétiques : vingt sources dont une écartée sans remplacement ; vingt-et-une
refusées avant ouverture ; révision manquante en fin de liste sans lecture des corps
précédents ; doublons et accès inter-utilisateurs refusés ; empreinte de la base
source inchangée. Aucune nouvelle donnée personnelle examinée.

## Accords distincts à donner

- **C1 troisième essai** : autoriser le patch minimal de contrat Windows et
  exactement un essai synthétique selon les bornes ci-dessus.
- **C2 nouvelle sélection** : définir et autoriser une liste précise de vingt tours
  maximum, ou d'abord un inventaire privé de métadonnées pour proposer cette liste.
  Cet inventaire n'est pas effectué maintenant ; pas d'accès aux corps par défaut.
- Transmission personnelle, index privé, gateway et transfert de sauvegardes restent
  exclus. C5 reste reporté.

## Validation locale exécutée

`python3 scripts/evaluate_memory.py --phase5c` : **17 commandes réussies**,
dont **19 tests phase 5C**. Aucune régression observée sur ce banc synthétique.
Résultats : `JARVIS_2_PHASE5C_TEST_RESULTS.json`. Compilation de l’opérateur
de patch vérifiée. Aucun troisième essai réel ou changement de production.
