# JARVIS 2.0 — Phase 5C : correctifs et pilote personnel préparés

14 novembre 2026. Worktree `jarvis-2-memory`, branche
`codex/jarvis-2-memory-20261113`, base `136730f` conservée.
**Travaux locaux et audit disque seulement. Aucun nouveau lancement Windows/GPU,
aucune conversation privée lue, aucune donnée personnelle indexée ou transmise.**
Les preuves B2 restent inchangées, notamment le verdict historique `passed=false`.

## 1. Diagnostic Unicode et correction à la frontière

Constat réel B2 : `expérience` apparaît sous la forme `expÃ©rience` dans certains
arguments d'outils. Cette forme est compatible avec des octets UTF-8 lus comme
Windows-1252, pas avec une correction du contenu par le modèle.

Chemin observé dans le code épinglé :

1. `ops/phase4-run-hermes-windows.py` impose UTF-8 au processus Hermes parent.
2. Hermes `_build_safe_env`, dans `tools/mcp_tool_config.py`, filtre l'environnement
   des enfants MCP. Ses listes sûres n'incluent ni `PYTHONUTF8` ni
   `PYTHONIOENCODING` ; les valeurs explicitement déclarées dans le profil sont,
   elles, réinjectées.
3. Notre profil MCP ne déclarait que `PYTHONPATH`. Le serveur lit `sys.stdin`
   comme texte sans fixer son encodage. La configuration du parent ne garantit
   donc pas celle de ce flux enfant sous Windows.
4. Le transport Hermes utilise en outre `encoding_error_handler=replace` pour
   sa lecture des sorties ; cela n'impose pas l'encodage de stdin à notre serveur.

La chaîne statique est identifiée et sa corruption est reproduite hors ligne
avec un vrai flux d'octets JSON-RPC et un TextIOWrapper Windows-1252. La locale
exacte du processus MCP B2 n'avait pas été instrumentée : cette cause est fortement
étayée, pas présentée comme un nouveau relevé matériel Windows.

Correctifs locaux :

- `phase4/windows.py` déclare explicitement `PYTHONUTF8=1` et
  `PYTHONIOENCODING=utf-8:strict` dans l'environnement MCP.
- `mcp_utf8.configure_stdio()` reconfigure les trois flux UTF-8 strictement avant
  de lire le protocole dans `phase3/mcp.main`, également utilisé par phase 4.
- Des octets invalides sont refusés, sans remplacement silencieux. Les données
  historiques ne sont ni réencodées ni normalisées pour masquer la corruption.

Tests : accents français, « citations », guillemets et apostrophes, S19 XP Hydro,
HX711, Ø12 mm, °C, µS/cm, Ω, chinois, emoji et accents combinants conservés exactement.
Test bout en bout MCP/HTTP simulé depuis un flux CP1252, aller-retour des chaînes,
ainsi qu'un refus d'UTF-8 invalide. Ce ne sont pas des tests matériels Windows.
Le patch **n'est pas déployé** sur le PC ; son application exige l'accord C1.

## 2. Validation sémantique réellement déclenchée par Hermes

Un nouveau lecteur `jarvis_memory_knowledge` est préparé : `q` est son seul argument.
Il appelle `memory.knowledge`, qui impose `memory_type=knowledge` côté serveur.
Aucun choix de propriétaire, de permission ou de statut n'est accepté du modèle.
L'authentification, les ACL et la relecture SQLite sont celles du Memory Manager.
Le lecteur existe aussi en fallback FTS ; un tel résultat ne valide pas le scénario
sémantique, qui exige explicitement le chemin vectoriel disponible.

Scénario initial exclusivement synthétique, avant toute donnée personnelle :

1. Nouvelle base et nouveau run, ancien fait/correction déjà éprouvés réutilisés.
2. Avant lancement : vérifier hors modèle que la requête fixe
   **« masse nominale identique »**, avec filtre knowledge, possède zéro hit FTS.
   Tout chevauchement invalide la fixture ; ne pas choisir une requête après les
   résultats du modèle pour transformer un échec en succès.
3. Objectif explicite : appeler `jarvis_memory_knowledge` avec cette chaîne exacte,
   sans y ajouter « DoseLab X4 », puis citer `synthetic://doselab/correction`.
4. Le searcher lié au run observe la requête réelle, le filtre, les hits FTS,
   les références retournées et leurs révisions canoniques. Le MCP ne permet pas
   au modèle de fournir ou modifier ces preuves.
5. Exiger un événement outil réussi du vrai runtime, un run completed, zéro FTS,
   un résultat par le chemin vectoriel et une correspondance SQLite actuelle,
   révision/source exactes et source citée dans la réponse.
6. Un contrôle hôte direct, une sortie narrative du modèle, un résultat FTS dégradé,
   une autre mission, un ancien vecteur ou une absence d'appel d'outil échouent.

`phase5c/semantic.py` fournit l'objectif, l'observation et le vérificateur indépendant.
Tests locaux via le vrai dispatch MCP et SQLite, avec vecteurs simulés : ils
valident ces contrats, **pas la pertinence sémantique ou une nouvelle mission Hermes**.
Le lanceur préparé `scripts/pilot_phase5c_semantic.py` injecte cette observation
dans le searcher API de son unique mission active, puis fournit ses événements
natifs au vérificateur. Il refuse de démarrer si les cinq modules Windows ne
correspondent pas aux empreintes locales revues. Cette liaison est testée avec
un runtime simulé et n'est pas activée dans le lanceur B2 historique.
Le manifeste `JARVIS_2_PHASE5C_PATCH_MANIFEST.json` décrit les cinq fichiers exacts,
leurs empreintes de base Git et nouvelles empreintes ; l'état Windows devra être
comparé avant remplacement et sauvegardé, jamais écrasé en cas d'écart inexpliqué.

Prévoir une seule mission synthétique après correctif Windows, 5 minutes maximum,
6 appels maximum, budget partagé au plus 98 304 tokens, contexte 64 000 conservé,
0 CHF. Les gardiens Jobs, minage/VRAM, délais et arrêt restent ceux de phase 4.
Pas de téléchargement ni relance destinée à améliorer artificiellement le score.
L'essai réel ne commencera qu'après revue de cette liaison et accord C1.
Commande préparée, **non exécutée** :

```
python3 -m scripts.pilot_phase5c_semantic --approved-c1 \
  --private-state /var/lib/jarvis-memory/phase5-a2/20261114T184704Z-65701471 \
  --artifact 06b237c33b5ff8824befda657bc3c210751771a4138c3af54b12367ae8ba4c7f
```

Le programme vérifie les fichiers mais ne les installe pas implicitement.

## 3. Sélection personnelle : au plus 20 sources, pas encore identifiées

Projet **proposé**, pas encore autorisé à l'extraction : refroidissement de
l'Antminer S19 XP Hydro. Aucun titre, message, payload Qdrant ou texte privé n'a
été consulté pour ce plan. Les anciens inventaires agrégés restent la seule base.
Il serait donc trompeur de fournir maintenant vingt identifiants de sources réelles.

Les emplacements suivants sont des **critères de sélection à remplir après C2**,
pas l'affirmation que ces événements/composants existent :

| Places maximales | Sources recherchées après autorisation |
|---|---|
| 01–02 | description initiale du montage et demande/objectif du projet |
| 03–04 | composants hydrauliques déclarés installés, références exactes |
| 05–06 | échange thermique, radiateur/échangeur ou pompe, si documentés |
| 07–08 | mesures datées de débit/température et conditions d'essai |
| 09–10 | comptes rendus d'essais avec résultats, y compris échecs |
| 11–12 | problème rencontré et première hypothèse de diagnostic |
| 13–14 | correction explicite de composant, valeur, calcul ou hypothèse |
| 15–16 | décision technique et raisons, avec date d'effet si connue |
| 17–18 | changement de configuration et confirmation la plus récente |
| 19–20 | expérience résolue et limites/contre-exemples de sa procédure |

Ne pas compléter artificiellement à vingt : moins de sources si insuffisantes.
Une source est un document/version ou un tour/version d'origine, pas un fragment
vectoriel. Un lien de conversation peut référencer plusieurs tours ; chaque tour
sélectionné consomme une place. Pour une clé composite : session + tour + révision.
Ne pas récupérer toute une session sous couvert d'une seule source.

Après C2, rechercher en lecture seule parmi les sources déjà inventoriées : docs
et conversations de la base brain et faits/corrections accessibles. Vérifier
l'identité et l'espace serveur avant sélection. Aucun appel à un modèle nécessaire
pour cette première sélection ; ne pas scanner la collection historique Qdrant.
La recherche sera limitée au projet ; le contenu de **vingt sources maximum**
pourra être examiné au total, y compris les sources finalement écartées. Si le
lot est insuffisant, signaler cette limite avant toute extension du périmètre.

Rapport privé attendu sous `data/phase5c/<nouvel-id>/import-review.json`, dossier
0700/fichier 0600, ignoré par Git. Contenu : références exactes, citations nécessaires,
dates d'origine, auteur, hypothèse/mesure/déclaration, candidats structurés,
doublons/contradictions, remplacements revendiqués et questions de validation.
Les citations et références personnelles ne paraîtront pas dans les rapports publics.

`phase5c/personal.py` prépare le rapport uniquement depuis des lignes explicitement
sélectionnées, sans ouvrir les anciennes bases : 1 projet, 20 sources distinctes,
500 propositions maximum, 512 Ko maximum. Il refuse une référence non sélectionnée,
un autre projet, une identité non mappée et un fichier destination existant.
Ces bornes sont des garanties du planificateur, pas une autorisation de lire des sources.

## 4. Consolidation réelle proposée

`Sources originales en lecture → sélection privée → propositions structurées →
déduplication → contradictions/remplacements à revoir → rapport privé → décision
humaine → ingestion additive du seul lot accepté → index privé autorisé séparément`.

Chaque proposition conserve source/base/table/clé/version, date originale, auteur,
propriétaire/périmètre et empreinte. Les extraits originaux sont préservés dans la
copie privée ; toute rédaction expurgée est une version distincte liée à l'original.
Une date d'export ne remplace jamais une date d'observation manquante : celle-ci
bloque la promotion. Les unités et conditions de mesure doivent rester explicites.

Tous les candidats importés commencent `inferred`, y compris une ancienne ligne
appelée « fait ». Une déclaration utilisateur pourra être confirmée comme déclaration
par l'autorité appropriée ; un résultat de mesure exige un relevé original daté.
Une réponse assistant demeure une hypothèse, même répétée dans plusieurs fragments.
Un changement de valeur n'est pas automatiquement une contradiction ou correction :
conserver validité et contexte, puis décision explicite. Les divergences détectées
par le planificateur sont des signaux à examiner, pas des conclusions automatiques.

Aucune écriture dans les bases sources. Toute future ingestion canonique nécessitera
un lot explicitement relu, sauvegarde SQLite vérifiée, clé idempotente et journal de
révisions. Qdrant n'est qu'un index reconstructible : vecteur → relecture SQLite,
ACL, validité, révision et provenance. La collection historique n'est jamais cible.

## 5. Apprentissage utile, après revue privée

Choisir une seule difficulté réellement attestée, sans supposer dès maintenant
une erreur de pompe, de débit ou de température. Hermes devra retrouver ses sources,
expliquer le montage actuel et les anciennes configurations, puis proposer une
procédure **de diagnostic et de rapport**, sans effet physique.

Compétence candidate liée aux identifiants/révisions des preuves originales et à
l'expérience résolue. Tests indépendants écrits à partir de ces preuves et relus par
l'humain : donnée absente/périmée, unités différentes, contradiction, ancienne
configuration, hypothèse présentée comme mesure et cas analogue hors périmètre.
Les résultats attendus ne seront pas produits par Hermes.

Ne pas réutiliser le DSL flow/freshness comme s'il couvrait déjà toute la physique
d'un S19 Hydro. Réutiliser son registre, ses empreintes et ses refus de publication ;
la procédure exacte et ses tests seront définis après examen des preuves.
Aucune version active ni publication native avant validation indépendante.
Arrêter puis recréer le runtime et demander à une nouvelle mission de retrouver
la même candidate, son empreinte, ses sources actuelles et ses limites d'emploi.
La revue humaine des enseignements ne sera pas confondue avec leur simple retour
par l'outil de recherche.

## 6. Sauvegarde hors CT205 — disque réellement observé

Audit en lecture seule après indication de l'utilisateur :
`JARVIS_2_PHASE5C_STORAGE_AUDIT_REAL.json`.

- `/dev/sda` : 1 000 204 886 016 octets, partition ext4 montée `/mnt/hdd`.
- Libre relevé : **778 220 515 328 octets**, environ 724,8 Gio.
- CT205 : `local-lvm:vm-205-disk-0`, 8 Gio, sous le **NVMe** de 256 Go.
- Cible proposée : `/mnt/hdd/jarvis-backups/qdrant/<nouvel-id>/`, à créer après C5.
  Autre disque physique et hors CT ; **même hôte**, donc aucune protection contre
  perte/compromission totale du serveur. Chiffrement au repos non démontré.
- La VM Codex a seulement **1 460 101 120 octets libres** sur /, occupé à 96 % :
  ne pas y faire transiter ou restaurer l'archive complète.

Source A1 conservée : 168 229 376 octets, SHA256
`92f138189be20e3256d150b744f15cb12ee46240aae4b29e1f3935c09b1d0a9f`.
Ce snapshot contient **toute la mémoire historique**, pas seulement le projet S19.
L'accord au projet personnel ne vaut pas accord à copier cette archive.

`phase5c/backup.py` prépare uniquement le plan et le contrôle de capacité : archive
+ deux copies estimées de restauration + 1 Gio de marge, soit 1 856 631 358 octets.
Prévoir aussi la place du binaire/runtime de vérification si une autre machine est
retenue. L'espace HDD suffit au relevé ; revérifier avant intervention.

Après accord C5 : revérifier SHA/taille source ; copier directement du CT vers le
HDD via les outils PVE locaux et le canal d'administration SSH vérifié, sans contenu
sur stdout ni transit Codex ; répertoire 0700, fichier partiel exclusif 0600 ; fsync,
taille/SHA destination puis renommage vers un nom neuf. Ne rien écraser ni supprimer.
Un chiffrement au repos est recommandé avant usage durable ; aucun logiciel/clé
ne sera installé ou généré sans une procédure approuvée et une clé hors du backup.

Restauration proposée en réutilisant le vérificateur A1 éprouvé : recopier l'archive
**depuis le HDD** dans un nouveau répertoire privé CT205, vérifier à nouveau le SHA,
puis restaurer dans une nouvelle instance Qdrant 1.20.0 isolée, jamais la principale.
Même sandbox A1 : namespace réseau privé, clé dédiée, 256 Mio/50 % CPU/10 min,
prévol CT au moins 512 Mio disponibles, arrêt du seul vérificateur sous 256 Mio.
Le plafond A1 avait été sollicité : aucune marge garantie ; échec → arrêt, pas de
hausse RAM automatique. Vérifier 41 428 points du snapshot, schéma/index et accès
sans payload ; arrêter et conserver toutes les copies et le reçu privé.
Ce test dépend encore du CT ; une restauration sur un autre hôte restera à prévoir
pour un véritable exercice de perte totale. Aucune modification RAM/balloon/service.

## 7. Raccordement Jarvis préparé, non monté

L'adaptateur Node 18 existant reste derrière un feature flag désactivé par défaut.
`hermes-server-auth.mjs` ajoute une authentification serveur hors ligne : jeton de
session opaque aléatoire, empreinte SHA256 côté serveur, date d'expiration obligatoire,
comparaison constante, sujet lié par registre serveur à des espaces autorisés.
Les noms de profil visuel et en-têtes client ne confèrent aucun droit. Les tokens
backend du bridge restent dans ses transports serveur, distincts de la session.

Tests : token inconnu, absence de token, expiration, faux profil admin, espace
non autorisé, accès légitime. Le registre d'exemple ne délivre aucune session :
il faut une autorité d'émission et révocation/rechargement revues avant activation.
Ce composant ne corrige pas à lui seul les routes legacy de la gateway.

Réutilisés : admission rapide avec idempotence, états persistants sur Proxmox,
événements SSE paginés et annulation ; transport borné sans boucle agent dans la
requête vocale. PC éteint : mission queued si le bridge est joignable ; erreur 503
si le bridge lui-même est absent. Les notifications sont des événements consultables,
pas une nouvelle UI/voix déployée. Journal de mission et contexte d'identité restent
sur Proxmox. Toute reconnexion ambiguë reste en revue sans rejeu aveugle.
Aucun outil shell, Home Assistant ou commande physique n'est ajouté.

## 8. Autorisations exactes, distinctes et ordonnées

Aucune opération ci-dessous n'est implicitement accordée par la demande actuelle.

| Bloc | Accord demandé avant exécution | Effets et arrêt/retour arrière |
|---|---|---|
| C1 | Déposer les modules MCP/UTF-8/profil et le nouveau lecteur dans l'app de laboratoire Windows, avec sauvegarde et SHA avant/après ; puis **un essai synthétique** Hermes/Ollama, 5 min / 6 appels / 98 304 tokens / 0 CHF | Seulement laboratoire Windows et vecteurs synthétiques ; aucune réinstallation. Gardiens inchangés, report si Kryptex/GPU indisponible ; fermer les seuls Jobs/tunnels possédés, conserver preuves ; restaurer les fichiers sauvegardés si nécessaire après arrêt |
| C2 | Lecture locale du seul projet S19 proposé, examen de **20 sources maximum au total**, y compris celles écartées, copie privée et rapport à blanc sur Proxmox | Aucun modèle ni écriture des bases sources ; arrêt à tout moment ; fichiers privés conservés pour revue, aucune suppression automatique |
| C3 | Transmission au seul modèle Windows du **lot expurgé nommé et relu**, après rapport C2 et validation Unicode/C1 | Extraits et contexte dans la RAM et potentiellement logs de laboratoire Windows ; politique de rétention à approuver avant lancement ; quotas propres à définir sur le lot, 0 CHF, pas de transmission implicite de tout le projet |
| C4 | Ingestion d'un lot candidat explicitement relu puis indexation privée expérimentale identifiée | SQLite sauvegardée, écritures additives/révisions journalisées ; pas de promotion automatique ; masquage logique de lot et arrêt indexeur, conservation de l'historique ; collection historique exclue |
| C5 | Copie de l'archive historique complète et manifeste vers le HDD Proxmox, contrôle d'intégrité puis test de restauration isolé décrit au §6 | Données personnelles historiques hors CT ; stockage root privé, pas de nettoyage ; arrêt du seul vérificateur, sauvegardes et copies conservées ; aucun redémarrage production |
| C6 | Intervention gateway, uniquement après revue séparée des ACL legacy et du montage | **Non proposée à l'exécution maintenant** ; nécessite revue/accord explicite, activation progressive du flag et procédure de retour arrière |

Un accord sur C2 ne permet ni transmission Windows (C3), ni ingestion/index privé
(C4), ni copie du snapshot complet (C5). Pour C1, le patch et la liaison du lanceur
seront figés/revus avant application ; les anciens runs B2 ne seront pas rejoués.
Aucune publication de compétence, action physique ou API distante payante dans ces blocs.

## 9. Validation livrée et limites

Commande : `python3 scripts/evaluate_memory.py --phase5c`.
**17 commandes réussies**, dont les 38 tests phase 5 conservés et **10 tests phase 5C**,
les 20 phase 1, 30 phase 2, 49 phase 3 et 17 phase 4. Tests Node additionnels pour
les sessions serveur/ACL. Preuve : `JARVIS_2_PHASE5C_TEST_RESULTS.json`.
Les tests Unicode exécutent le protocole local ; l'agent et les vecteurs restent
simulés. Aucun résultat GPU/Windows réel nouveau n'est annoncé.
L'audit disque est réel ; transfert et restauration hors CT ne sont pas exécutés.
Les vingt références personnelles et le rapport privé restent à constituer après C2.

## Exécution C1/C2 du 14 novembre — constat de fin

C1 : cinq modules Windows sauvegardés et appliqués ; test Unicode Windows réussi
avec HTTP simulé. L'unique mission réelle a été refusée avant inférence par une
liste secondaire du relais non mise à jour. Correction et régression locales prêtes,
**aucun second essai**. Validation sémantique stricte non obtenue.

C2 : le lecteur a lu dix-huit documents, dont des conversations multi-tours ; la
bornage par tours prévu ici n'était pas imposé. Rapport privé **bloqué**, résultat
non conforme, pas d'import/transmission. Bases inchangées, aucun contenu envoyé
aux modèles. Le lecteur est désormais en refus fermé pour ces documents et un
sélecteur de tours explicites est testé hors ligne. Aucune lecture supplémentaire.

C5 reste reporté ; les étapes de copie en clair décrites au §6 ne sont plus
proposées. Protection par chiffrement avant sortie de CT et clés hors serveur :
`JARVIS_2_PHASE5C_BACKUP_PROTECTION.md`. Rien de transféré.
Résultats détaillés, limites et preuves : `JARVIS_2_PHASE5C_RESULTS.md`.

## Mise à jour — deuxième essai C1 autorisé

Un nouvel accord explicite a permis un essai réel distinct (20:35:58–20:36:51 UTC).
Hermes a bien appelé le lecteur filtré, obtenu zéro correspondance FTS et une
connaissance vectorielle actuelle revalidée dans SQLite. Il n'a pas cité sa
source exacte et son accès à l'historique a échoué : **`passed=false` maintenu**.
Deux appels, 7 604 tokens, aucun coût distant, laboratoire arrêté et ports fermés.
Correctif de consigne et régression préparés hors ligne, sans troisième essai.
C2 bloqué, C5 reporté, aucune nouvelle lecture personnelle ou action production.
Voir `JARVIS_2_PHASE5C_C1_RETRY_RESULTS.md`. B2 historique inchangé.

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
