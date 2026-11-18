# Phase 5C — Résultats séparés C1 et C2

**État actuel après troisième essai autorisé : C1 strict réussi (`passed=true`),
anciens verdicts conservés. C2 : métadonnées seulement, aucun tour sélectionnable.**
Voir `JARVIS_2_PHASE5C_C1_THIRD_RESULTS.md`. Les constats de fin ci-dessous
relatifs au premier et deuxième essai sont historiques.

Mise à jour : deuxième C1 autorisé réellement exécuté, recherche vectorielle par Hermes
observée mais source exacte absente de la réponse et historique refusé : **échec strict**.
Voir `JARVIS_2_PHASE5C_C1_RETRY_RESULTS.md`. La section C1 ci-dessous conserve le
constat du premier essai ; la mention « aucun nouvel essai » y décrit cet état antérieur.

14 novembre 2026. Autorisations explicites C1/C2 reçues. C3/C4/C6 non autorisés,
C5 reporté. Verdict B2 historique inchangé (`passed=false`).

**Bilan : C1 ne valide pas la recherche sémantique réelle ; C2 est bloqué pour
erreur de granularité des sources. Aucun des deux blocs n’est annoncé pleinement réussi.**

## C1 — Patch et Unicode validés ; essai sémantique bloqué avant inférence

Les cinq modules du manifeste ont été sauvegardés, leurs empreintes vérifiées,
puis remplacés uniquement dans `C:/JarvisHermesLab/app`. Le module memory_tools
installé avait une empreinte différente de la base Git annoncée : correspondance
exacte retrouvée au commit historique `c79ebd4ff5b76e15a653e5bdc4bbb67fac1e3ef2`.
L'écart est expliqué par l'adaptateur de recherche ultérieur ; aucune version inconnue
n'a été écrasée. Empreinte réelle consignée dans le manifeste, sauvegardée avant patch.

Les trois premiers passages de l'opérateur de patch ont échoué avant lancement
Hermes/Ollama. Le nouveau helper déjà déposé a été déplacé vers les copies d'échec,
les fichiers existants restaurés et les sauvegardes conservées. Un problème de
liaison PowerShell/chemin de backup et la longueur des commandes encodées ont été
isolés : le test synthétique de remplacement à sauvegarde explicite fonctionne,
puis SFTP des sources et commandes courtes ont permis le déploiement. Les diagnostics
SSH initiaux masquaient stderr ; chaque cause n'est pas attribuée avec certitude
à chacun des trois passages. Aucune donnée utilisateur dans ces fichiers de code.

Déploiement réussi : `JARVIS_2_PHASE5C_PATCH_REAL.json`, répertoire de sauvegarde
`C:\JarvisHermesLab\staging\phase5c-20261114T201632Z-f092ced7`.
Source Hermes officiel et dépendances non réinstallés, aucune ACL ou règle réseau
Windows modifiée. Le patch est laissé installé dans le laboratoire seulement.

Test réel sous le compte Windows dédié : flux MCP initialement configuré CP1252,
octets JSON-RPC UTF-8 synthétiques, reconfiguration UTF-8 strict, arguments et
retour de texte préservés. **Réussi**. La partie HTTP est simulée, aucun modèle
appelé par ce test. Preuve : `JARVIS_2_PHASE5C_UNICODE_WINDOWS_REAL.json`.

L'unique essai autorisé a ensuite réellement démarré Hermes et Ollama :
**20:18:07–20:18:45 UTC**, une mission, une tentative auprès du relais,
**zéro appel d'inférence envoyé à Ollama, zéro token génératif**.
Le nouveau lecteur apparaît correctement dans la découverte MCP, mais une liste
secondaire du relais restait copiée en dur depuis l'ancien ensemble d'outils.
Elle a refusé `jarvis_memory_knowledge` avant l'appel au modèle.
Le message générique « API key rejected » côté Hermes correspond ici à ce refus
HTTP 403 ; ce n'est pas une preuve de jeton invalide.

Ce défaut de raccordement n'avait pas été couvert par le test simulant native_run.
Il est maintenant corrigé **dans le contrôleur isolé** : le relais utilise la même
liste READ que le MCP, avec proposition de compétence seulement en mode autorisé.
Un test de non-régression confronte la découverte MCP réelle à cette admission et
vérifie les refus shell/HA/publication/proposition hors mode autorisé.
**Aucun nouvel essai réel n'a été lancé après cette correction.**

Preuve native : `JARVIS_2_PHASE5C_SEMANTIC_REAL_20261114T201807Z-53df5fee.json`.
La validation sémantique stricte reste **non obtenue** : aucune trace de recherche
par Hermes, aucune réponse sourcée nouvelle. Aucun succès hôte ne remplace ce constat.

Arrêt confirmé par les superviseurs : Job Hermes et Job Ollama fermés, processus
possédés arrêtés ; ports Windows 8643/11434 et contrôleur 8792/11436/8643/11435 fermés.
GPU final 0 %, 9 172 Mio libres, Kryptex non actif avant/après et jamais interrompu.
Budget distant 0 CHF. Aucun modèle téléchargé, changement RAM ou service permanent.
Voir `JARVIS_2_PHASE5C_C1_CLEANUP_REAL.json`.

Une éventuelle reprise exigera une **nouvelle autorisation pour un seul nouvel essai**,
avec nouveaux identifiants et fenêtre, mêmes bornes 5 min / 6 appels / 98 304 tokens.
La mission terminale échouée ne sera pas rejouée. Aucun besoin de redéployer la
correction du relais sur Windows : elle est dans le contrôleur Proxmox isolé.

## C2 — Rapport local créé mais non conforme au découpage autorisé, bloqué

**Erreur de périmètre de l'implémentation :** le lecteur a compté **18 documents**
comme sources, dont 8 classés ChatGPT, 9 Codex et 1 Mémoire. Les documents de
conversation peuvent contenir plusieurs tours. Le plan approuvé imposait que les
tours d'une conversation consomment chacun une place et interdisait d'absorber
une session entière sous une seule source. Cette borne n'a pas été imposée.
Les seuls extraits retenus comportent déjà 50 marqueurs de locuteur ; le nombre
exact de tours lus n'est pas établi. **La conformité à la borne de vingt tours
n'est pas démontrée ; C2 ne doit pas être annoncé réussi.**

Le contenu est resté dans le programme local : aucune citation, titre, identifiant,
mesure ou date privée remonté à Codex, Windows, Hermes, Qwen ou un autre modèle.
Seuls des compteurs et chemins de rapports ont été imprimés. Les bases originales
ont été ouvertes mode=ro/query_only sans backend/migration ; aucune écriture source,
ingestion canonique, indexation ou compétence personnelle créée.

Mesures immédiates après constat :

- Aucun contenu source supplémentaire lu et aucune recherche élargie.
- Rapport marqué **bloqué pour import et transmission**, avec avertissement en
  tête ; version initiale conservée, sans masquer l'erreur ni modifier les originaux.
- Réservation C2 exclusive conservée : pas de seconde sélection automatique.
- Lecteur corrigé pour refuser les conteneurs ChatGPT/Codex/Jarvis **avant de
  projeter les corps**, au lieu de compter ces conversations comme documents simples.
- Nouveau lecteur hors ligne de références normalisées session/tour/révision,
  limité à vingt couples utilisateur/assistant, contrôle propriétaire et révision.
  Il est testé sur fixtures seulement, **pas exécuté sur les données personnelles**.

Le rapport initial contient 17 documents à relire et un signalé comme instructions
du méta-projet, 8 signaux lexicaux de correction, 106 énoncés de mesure candidats
et 4 familles d'unités aux valeurs différentes. Ces compteurs ne démontrent ni
montage actuel, ni mesures vérifiées, ni contradictions résolues. Les dates de
document sont préservées mais ne sont pas des dates de mesure ; l'auteur exact
n'est pas automatiquement déduit des conversations mixtes.

Fichiers privés, dossier 0700 / fichiers 0600, ignorés par Git :
`data/phase5c/c2-20261114T201530Z-de75ffbe/REVIEW_BLOCKED.md`,
`import-review.md`, `import-review.json`, `scope-review.json`, sélection réservée.
`import-review.initial.md` conserve la première version lisible. Les extraits
masquent les secrets détectés, sans garantie DLP exhaustive. Aucun de ces contenus
n'est copié dans ce rapport public. Résumé du constat sans contenu :
`JARVIS_2_PHASE5C_C2_SUMMARY.json` (inclut les compteurs initiaux et l'alerte).

La revue utilisateur du rapport et un choix explicite de références de tours sont
nécessaires avant une reprise. Le nouveau lecteur couvre les tours normalisés
`conversation_turns` ; les exports ChatGPT conservés dans docs exigent un découpage
et une sélection explicites avant lecture autorisée, pas un scan de sessions entières.
Aucun nouvel accord C2 n'est présumé, ni C3/C4 réactivés.

## C5 — Protection proposée, sans transfert

Voir `JARVIS_2_PHASE5C_BACKUP_PROTECTION.md` : chiffrement à clé publique **avant
sortie de CT205**, clés privées hors Proxmox/laboratoire, coffre et copie de secours
séparés, vérification SHA puis vrai déchiffrement/restauration sur un environnement
approuvé. GnuPG est présent mais non qualifié ; age est absent et resterait une
alternative soumise à installation autorisée. Ni clé, chiffrement, transfert,
reformatage ou suppression de snapshot effectués.

## Vérifications locales

`python3 scripts/evaluate_memory.py --phase5c` : **17 commandes réussies**, dont
**15 tests phase 5C** (11 préparation/chaînage et 4 revue privée synthétique).
Le test de revue vérifie la borne de vingt, les permissions privées, la redaction
de secrets synthétiques et le SHA inchangé de la base source synthétique.
Des tests supplémentaires refusent les documents de conversation avant lecture du corps
et vérifient les références explicites session/tour/révision et droits du nouveau lecteur.
Les autres phases et 38 tests phase 5 sont conservés. Les mocks n'établissent
aucun nouveau succès GPU. Diff Git vérifié, aucun rapport privé suivi.

## Préparation de finalisation C1/C2

La trace synthétique de session retrouvée en lecture seule confirme que l’appel
refusé utilisait `memory_id="synthetic://doselab/old"`. Instructions et descriptions
MCP précisées hors ligne, vérification supplémentaire de l’identifiant historique
préparée. Aucun troisième essai GPU, patch Windows ou lecture personnelle.
Plan et accords distincts : `JARVIS_2_PHASE5C_FINALIZATION_PLAN.md`.
Les verdicts réels négatifs précédents restent inchangés.

## Troisième C1 autorisé — succès réel du scénario strict

Le 14 novembre, 20:54:30–20:55:26 UTC, une seule nouvelle mission synthétique
a démontré zéro hit FTS, vecteurs réels revalidés SQLite, historique avec le bon
`memory_id`, citations exactes des deux sources, résultat durable après arrêt
des processus. **`passed=true` pour ce nouvel essai uniquement** ; anciens
verdicts B2/C1 conservés. Trois appels, 12 853 tokens, 0 CHF, ports fermés.
C2 : inventaire privé de métadonnées seulement, trois documents mais aucun tour
normalisé sélectionnable par ces métadonnées ; aucune lecture de contenu, ancien
rapport toujours bloqué. C3/C4/C5/C6 non autorisés, production inchangée.
Détail et limites : `JARVIS_2_PHASE5C_C1_THIRD_RESULTS.md`.
