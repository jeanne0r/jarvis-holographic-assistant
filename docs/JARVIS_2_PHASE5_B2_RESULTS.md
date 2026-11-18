# Phase 5 — B2 réel : apprentissage guidé réussi, critère strict partiel

14 novembre 2026. Accord explicite reçu pour 98 304 tokens partagés.
**Trois missions sur trois réussies. Le résultat global strict du lanceur reste
`passed=false`**, car aucune requête d'Hermes n'a isolé le vecteur avec zéro hit FTS.
Cette preuve originale n'est pas requalifiée après coup.

## Ce qui est démontré sur les services réels

Chaîne exécutée : bridge Proxmox → Hermes natif Windows → relais autorisé →
Ollama/Qwen3.5:4b sur RTX 3080 → MCP → Memory Manager/SQLite et Qdrant expérimental.
Nouvelle base exclusivement synthétique :
`data/phase5/windows-20261114T193617Z-8d5c9f3d/memory.sqlite`.

| Mission | Résultat observé |
|---|---|
| Configuration | Recherche hybride réelle et historique consultés ; quatre cellules identiques de 1 kg ; anciennes capacités [1,2,5,10] déclassées ; deux sources citées |
| Compétence | `doselab_freshness` v1 proposée depuis l'expérience confirmée ; évaluation hôte 3/3 puis 16/16 ; test hôte de refus de publication avec l’identité agent |
| Après redémarrage du runtime | Même compétence candidate et empreinte retrouvées ; outil d'expériences renvoyant aussi les épisodes des missions précédentes |

Empreinte de cette nouvelle compétence :
`ca26bc7b4636de9de9f381e69f56f06028b02f4e49089e1b0e5983cc665075ba`.
Elle provient d'une nouvelle base : la compétence phase 4, de même nom/version,
reste intacte dans son laboratoire précédent. Rien de publié, aucun pointeur actif.
Une relecture après l'arrêt de tous les runtimes réussit encore les 16 cas.

Il s'agit d'un **apprentissage procédural guidé**, avec un schéma et des contrôles
fournis par l'hôte, à partir d'une expérience synthétique confirmée. Cela ne prouve
ni découverte autonome d'une nouvelle procédure, ni capacité générale de Qwen à
résoudre des missions arbitraires, ni modification des poids du modèle.
L'outil a retrouvé des épisodes `mission://` ; la réponse finale résume surtout
l'expérience de départ, sans citer explicitement ces identifiants d'épisodes.

## Critère sémantique strict conservé en échec

La consigne demandait « masse nominale identique ». Hermes a réellement demandé
**« masse nominale identique DoseLab X4 »**. Cette requête a emprunté les vrais
embeddings et Qdrant mais possède aussi **2 hits textuels**, donc on ne peut pas
attribuer ce résultat au seul vecteur. La configuration courante figure dans les
références canoniques retournées. La récupération hybride fonctionne ; le critère
plus fort, préannoncé, n'est pas atteint par cette mission.

Deux contrôles hôte après arrêt sont consignés séparément, sans autre appel Hermes :

- Requête originale sans filtre : 1 hit FTS, maintenant dans un nouvel épisode de
  mission. Le contrôle strict échoue encore ; preuve conservée.
- Même requête, filtre structuré `memory_type=knowledge` : **0 hit FTS**, vraie
  recherche vectorielle, une connaissance retournée, configuration actuelle au
  rang 1 et source `synthetic://doselab/correction`. Contrôle exploratoire réussi.

Le filtre exclut les récits de mission, qui ne constituent pas des faits courants.
Ce contrôle hôte confirme l'accès sémantique sur la même base après les missions ;
il ne remplace pas un appel sémantique seul réalisé par Hermes. Aucun nouvel essai
GPU ni élargissement de quota n'a été déclenché pour changer le verdict.

Quelques arguments d'outils présentent des accents mal encodés (`expÃ©rience`).
Ils n'ont pas empêché ces missions, mais le transport Unicode Windows/MCP devra
être isolé et testé avant import personnel. La cause exacte n'est pas établie ;
aucun patch Windows n'a été appliqué pendant l'essai.

## Budget, ressources et limites des mesures

Essai : **19:36:18–19:38:27 UTC**, 129 s hors précontrôles d'intégrité.
**8 appels**, **37 918 tokens mesurés** : 36 755 en entrée et 1 163 en sortie.
Par mission : 13 790 / 14 613 / 9 515. Un seul budget partagé ; plus forte somme
« usage consommé + réserve du prochain appel » : **95 730**, sous 98 304.
Fenêtre fermée avec 3 missions et 8 appels ; aucun renouvellement. Coût distant :
**0 CHF**, aucun fallback ou téléchargement.

- Contexte effectivement relevé dans `/api/ps` : **64 000** tokens.
- Modèle : Qwen3.5:4b, digest
  `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`.
- Hermes : archive épinglée `4959268e312a21a361f248e49030d5f5df3984d5`,
  manifeste et 25 615 fichiers revérifiés. Pilote NVIDIA : **621.24**.
- 47 échantillons GPU : pic **6 869 Mio utilisés**, minimum **3 371 Mio libres**,
  pic d'utilisation **99 %**, puissance instantanée maximale **335,6 W**.
- Mémoire VRAM du modèle dans un échantillon Ollama : **5 154 285 812 octets**,
  distincte de la mémoire totale du GPU, qui inclut le bureau et d'autres allocations.
- Latence aller-retour au relais par appel : **4,499–6,689 s**. Elle inclut notamment
  chargement, traitement d'entrée, génération et transport ; aucun débit de
  décodage isolé ni temps GPU précis n'est revendiqué.
- Pic Job Hermes **378 019 840 octets**, pic processus **330 858 496** ;
  pic Job Ollama **8 248 930 304**, pic processus **8 153 329 664**. Ces mesures Windows
  ne sont pas un RSS Linux. Aucun échec mémoire observé, sans audit OOM exhaustif.

Le pic de puissance n'est pas une énergie intégrée. Pas de benchmark comparatif de
modèles, de mesure sur données personnelles ou de nouvelle évaluation d'injection.
Les métadonnées PE des exécutables interrogés ne fournissent pas de version Ollama ;
aucune version nouvelle n'est inventée à partir de ce constat.

## Arrêt et conservation

Trois Jobs Hermes distincts démarrés puis arrêtés ; Job Ollama arrêté ; les
superviseurs confirment l'arrêt de leurs processus possédés. Contrôles supplémentaires :
aucun listener Windows 8643/11434, aucun listener contrôleur 8792/11436/8643/11435.
GPU final à 0 %, 9 172 Mio libres ; Kryptex non actif avant/après, jamais interrompu.

Qdrant expérimental contient **16 points synthétiques** : 6 A2, 5 B, 5 B2.
Les épisodes restent canoniques dans SQLite et accessibles en texte ; cette fenêtre
n'a pas réindexé automatiquement les nouveaux épisodes non validés comme faits.
La sauvegarde A1 et les anciennes bases restent conservées. Aucun prune ni accès
à la collection historique par le transport du pilote ; aucun redémarrage CT205,
changement de RAM, accès physique HA, import personnel ou déploiement gateway.

Le redémarrage testé est celui des processus Hermes, **pas celui du PC Windows**.
Le PC et les services de production n'ont pas été redémarrés. Le modèle est arrêté.

## Preuves et suite

- `JARVIS_2_PHASE5_B_WINDOWS_REAL_20261114T193617Z-8d5c9f3d.json` : essai natif original,
  trois missions réussies et verdict global strict en échec.
- `JARVIS_2_PHASE5_B2_POSTCHECK_REAL.json` : contrôle hôte non filtré en échec,
  persistance et absence de listeners.
- `JARVIS_2_PHASE5_B2_KNOWLEDGE_POSTCHECK_REAL.json` : contrôle sémantique hôte filtré réussi.
- `JARVIS_2_PHASE5_B2_SOFTWARE_REAL.json` : limites du relevé de version.
- `JARVIS_2_PHASE5_B2_PREFLIGHT_REAL.json` : archive revérifiée et fenêtre finale fermée.

Pas de code exécutable modifié pendant B2. Les preuves de régression du commit
`e35fbfc` restent **15 commandes / 38 tests phase 5 réussis** ; elles n'ont pas été
relancées inutilement pour ces seuls nouveaux documents. Évaluation hors ligne de
la nouvelle candidate : 16/16 après arrêt.

Avant données personnelles : corriger/tester la chaîne Unicode, revoir les droits
et choisir un petit périmètre pour un rapport à blanc autorisé séparément. Avant
publication : revue indépendante et liaison de l'évaluation étendue à la transaction
humaine. Avant production : revue des ACL legacy et accord de déploiement.
Aucune de ces activations n'est effectuée par B2.
