# Phase 6D — Sécurisation de la gateway avant activation

15 novembre 2026 — worktree `jarvis-2-memory`, branche `codex/jarvis-2-memory-20261113`.

**La politique centrale et ses correctifs sont développés et testés en copie isolée. L'activation globale reste NO-GO : les adaptateurs d'autorisation sur les ressources historiques et la séparation effective du worker Codex ne sont pas encore raccordés.** Aucun rôle administrateur ni exception de jeton maître ne remplace ces contrôles. Aucun déploiement, compte, service permanent, GPU, appel Gemini, import ou action physique dans cette phase.

## 1. Périmètre observé et matrice complète

L'installation réellement servie reste `/home/user/gateway/server.js`, avec import direct de `/home/user/workspace/jarvis/backend.mjs`. Le contrôle final compare ses empreintes à celles de l'audit 6C. Les handlers importés Astro, Allemand et Solana ont également été examinés en lecture seule. Aucun module actif n'est importé par les tests : cela évite notamment le déclenchement automatique du synchroniseur du backend.

La matrice complète est dans [phase6d/ROUTE_MATRIX.md](phase6d/ROUTE_MATRIX.md). Le fichier [phase6d/route-matrix.json](phase6d/route-matrix.json) contient les 100 couples route/méthode, les effets, les permissions, les familles de clients, les conditions de routage observées avec lignes et empreintes, ainsi que les références littérales trouvées dans les sources des clients. Les appels construits dynamiquement sont signalés ; une référence statique ne prouve pas une compatibilité réelle. Les 60 conditions littérales vérifiées et les familles paramétrées sont couvertes. Toute route ou méthode future non classée est refusée.

| Ensemble | Identité et permissions | Contrôles complémentaires / effets |
|---|---|---|
| `/api/jarvis/*` | Humain identifié, droit spécifique, espace serveur | Mémoire, synchronisation/import, voix, statistiques, développement ; adaptateurs requis pour les opérations à portée multiple ou outils |
| `/api/projects`, `/api/tree` | `projects.read`, `files.read` | ACL de projet ; `/tree` peut créer un répertoire même en GET |
| `/api/chat` GET/DELETE | `chat.read`, `chat.delete` | Projet et propriétaire, lecture/suppression de conversations |
| `/api/runs` GET/POST et sorties/événements | `runs.read`, `runs.create` | Propriété/ACL des runs et projets ; POST peut lancer shell/réseau/fichiers |
| `/api/dosing-calibration/run` | `physical.dosing.calibrate` | Ressource exacte et approbation physique indépendante ; refus par défaut |
| `/api/s9/power` | `physical.s9.power` | Même exigence, permission distincte ; aucun droit Hermes |
| Mirror/iCloud/tâches/frigo/rapports | Droits spécialisés | Données personnelles, configuration, écritures et parfois appels externes payants |
| Astro/Allemand/Solana | Droits propres à l'application | Proxy/configuration, sessions d'exercice, fournisseurs IA ou archives de simulation |

### Routes publiques proposées

- `GET /api/health` retourne seulement `{ok:true}` via le garde central, sans chemins ni détails du binaire Codex.
- `GET/POST/DELETE /api/jarvis/session` constitue le protocole de session : GET exige une session, POST un justificatif valide et l'origine épinglée, DELETE l'origine épinglée. Ce n'est pas un accès public aux données métier.
- Les seuls documents/assets publics sont les chemins explicitement inventoriés dans `phase6d/public-assets-candidate.json` : pages d'application et code/assets techniques. L'inventaire est une proposition à examiner, pas une configuration activée. Aucun répertoire entier, export JSON, ZIP, PDF ou fichier caché n'est rendu public implicitement. Les anciennes URL de téléchargement ou pages absentes de cette liste doivent être classées séparément ; elles seront refusées entre-temps.

Les identités de service n'ont pas accès aux routes humaines par simple possession d'un droit homonyme. Bridge, outils mémoire et superviseur utilisent leurs contrats et identités séparés. Si un client non humain historique doit accéder à une route, il faudra l'inscrire précisément, sans accès de secours global.

## 2. Politique centrale effectivement préparée

`gateway-route-policy.mjs` porte le registre unique. `gateway-security.mjs` l'applique avant tout dispatch vers les handlers existants. `gateway-security-mount.mjs` charge les fichiers privés possédés par l'UID du service, sans suivre le lien final, avec taille bornée et permissions 0600.

Le candidat contrôle l'identité, le type humain, la permission exacte, l'espace, l'origine des mutations, puis les ACL de ressource et l'approbation physique si nécessaires. Ces deux derniers contrôles sont des fonctions serveur : aucun champ de requête ne peut affirmer qu'ils sont satisfaits. Leur valeur par défaut est **refus**. Les décisions sont préparées pour journalisation via un callback sans contenu métier. Le journal durable global et sa configuration restent à raccorder ; il ne faut pas présenter le callback par défaut comme un audit persistant déployé.

Les requêtes non classées, méthodes inattendues, espaces multiples et séparateurs/segments de traversée encodés sont refusés. Les routes S9 et iCloud du candidat ne relisent plus un jeton maître : elles vérifient le contexte établi par le garde central. Ce remplacement n'est valable que dans le lot qui installe effectivement ce garde en amont. Les anciens handlers ne doivent jamais devenir directement accessibles par un second point d'entrée.

La configuration d'identité est relue à chaque requête et pendant les flux ouverts. Une configuration absente, invalide, trop permissive sur disque ou une origine modifiée provoque un refus ; aucun retour au handler non authentifié. Un changement de topologie exige une revue. La session opaque est commune à la couche centrale ; les contextes internes utilisent des WeakMap, jamais des en-têtes d'identité fournis par le navigateur.

## 3. Sessions humaines, voix et clients

Le client `public/jarvis-auth.js` fonctionne sans panneau Hermes. Il gère connexion/déconnexion, état humain en mémoire et événements de disponibilité, sans stockage de secret, monkeypatch de fetch, microphone ou fournisseur IA. Le panneau réutilise ce client et n'émet plus lui-même l'événement de connexion, ce qui évite une boucle observée et corrigée dans la copie isolée.

Le cookie global candidat a `Path=/api`, HttpOnly, SameSite Strict, Secure en HTTPS. Connexion et déconnexion effacent aussi l'ancien cookie `Path=/api/jarvis`, afin d'éviter les doubles cookies ambigus. Cette migration est testée ; elle n'est pas appliquée. Le client voix existant reçoit seulement le mécanisme de reprise du chargement après connexion déjà préparé en 6B. Les fichiers `codex-voice.js`, `speech.mjs`, les worklets microphone et le streaming ne sont pas modifiés.

`voice-session-owner.mjs` lie la session vocale à **sujet humain + session d'authentification + espace**. Le patch minimal du backend vérifie cette liaison avant transcription ou synthèse. Un utilisateur différent du même espace, un autre espace ou une reconnexion avec un nouvel identifiant de session sont refusés avant le fournisseur. La capacité/expiration est bornée ; les sessions anciennes doivent être rouvertes après activation de la protection.

Politique de révocation :

1. Les nouvelles requêtes sont refusées dès le retrait/expiration du justificatif ou des droits.
2. Les réponses PCM/SSE déjà ouvertes sont revérifiées toutes les secondes au maximum, puis fermées si l'identité/droit/espace disparaît ou si la politique devient illisible. Un délai absolu de 45 secondes ferme aussi ces flux.
3. La fermeture réutilise le mécanisme existant d'annulation du streaming. Le test de transport existant vérifie cette propagation avec un fournisseur simulé.
4. Une mutation déjà validée et exécutée n'est pas annulée rétroactivement par la déconnexion. Les interactions non streaming déjà envoyées restent bornées par leur timeout fournisseur. Révocation et annulation d'une mission demeurent deux opérations distinctes.
5. Un redémarrage invalide les cookies émis par le processus. Déconnexion provoque le rechargement de la page pour retirer les données et états de l'ancien utilisateur de l'interface.

### Compatibilité : ce qui est acquis et ce qui manque

| Client/fonction | Vérification locale | Limite restant à lever |
|---|---|---|
| Connexion autonome desktop/mobile | Chromium, sans panneau Hermes | Origine réelle, certificats et justificatifs non provisionnés |
| Panneau de missions | Consultation seule, création désactivée, résultats/XSS/ACL d'approbation simulés | Composition avec la façade serveur de production non activée |
| Voix hybride | Corps exact du backend candidat, propriété inter-utilisateurs ; régressions PCM simulées | Essai microphone réel interdit ici, ACL du worker encore à imposer |
| Conversation ordinaire `/ask` | Dispatch préservé vers le backend simulé | Refus tant que l'adaptateur identité/outils n'est pas raccordé ; aucun fournisseur réel appelé |
| Mémoire/docs/carte | Routes classées et droits/espaces testés | Contrôles Commun, sources et propriétaires au niveau des stores/outils |
| Synchronisation/import/déplacement | Permissions distinctes, refus sans adaptateur | Synchronisation globale et cible d'un déplacement nécessitent des ACL métier précises |
| Runs/projets/chat | Contrat classé, refus sans autorisation de ressource | Anciennes listes globales et runs sans propriétaire nécessitent filtrage serveur ou refus |
| Mirror/Frigo/Astro/Allemand/Solana | Sources clients inventoriées, politique classée | Clients dynamiques, exercices partagés, portées et services externes à adapter |
| iPhone | Viewport mobile testé | Aucun essai Safari/iPhone matériel effectué |

**Ne pas activer ce garde tel quel avec des adaptateurs absents : il bloquerait notamment `/ask`, certaines lectures mémoire, la synchronisation et les runs.** Cela protège les données mais ne répond pas encore à l'exigence de continuité du Jarvis actuel. Les exemples de configuration ne contiennent aucun justificatif utilisable et n'accordent aucun rôle administrateur.

## 4. Statique, liens et CORS

Le garde ne laisse pas l'ancien serveur choisir librement un fichier. Il exige un manifeste de chemins exacts et d'empreintes SHA-256. Avant lecture : refus des fichiers cachés, segments ambigus, symlinks intermédiaires et finaux ; ouverture sans suivi du lien final ; contrôle du fichier réellement ouvert via `/proc/self/fd` dans la racine réelle, avec frontière de répertoire et taille bornée. Une empreinte différente est refusée.

Le code vise l'hôte Linux de la gateway et échoue fermé si ce contrôle n'est pas disponible. Le répertoire de release devra être non modifiable par le worker ; le manifeste ne remplace pas l'isolation OS contre un processus du même UID. Les réponses sont same-origin ; le garde supprime les en-têtes CORS permissifs des anciens `writeHead` et refuse les origines étrangères, sans OPTIONS public universel. Les variantes LAN/Tailscale devront être choisies explicitement ; pas de wildcard ni de jeton exposé dans une URL.

## 5. Mémoire canonique et disponibilité

L'extension optionnelle `memory_manager/phase6d/api.py` réutilise le serveur HTTP authentifié existant. Elle n'est pas activée par le CLI courant.

- `POST /v1/missions/:id/tools/read` : lecture via les outils mémoire existants, mission autorisée et hôte de confiance sélectionné par l'identité d'outil configurée. Le modèle ne choisit ni hôte ni auteur du reçu.
- Après lecture réussie, un reçu immuable conserve uniquement les identifiants canoniques des mémoires/révisions réellement retournées, la mission, l'outil et les acteurs.
- `GET /v1/missions/:id/canonical` : projection depuis ces reçus, revalidation SQLite et ACL, uniquement les révisions observées. Un faux reçu ou une autre mission est refusé. Cela prouve une réponse d'outil autorisée, pas la véracité du raisonnement du modèle.
- `POST /v1/workers/:id/heartbeat` : seul le rapporteur indépendant autorisé peut écrire, sous époque enregistrée par le superviseur et séquence croissante ; l'horodatage HTTP vient du serveur.
- `GET /v1/workers/:id/status` : visibilité par propriétaire, péremption par défaut 30 secondes, état inconnu et dispatch interdit si périmé. GPU occupé ou état incertain interdisent aussi le dispatch.

Le gardien `phase6d/worker.py` enveloppe le contrôleur existant : profil approuvé nécessaire, heartbeat frais puis gardiens GPU/Kryptex/budgets existants. Une soumission `unknown` n'est jamais rejouée. Le heartbeat n'autorise pas à lui seul un démarrage Windows/GPU. Son émetteur réel et sa supervision OS restent à configurer ; aucun sondage Windows n'a été effectué ici.

La migration additive est opt-in, idempotente et précédée d'une sauvegarde SQLite vérifiée. Les tests restaurent cette sauvegarde dans un autre fichier, contrôlent l'intégrité et la reprise des reçus/états après réouverture. Aucune migration réelle. Aucune seconde mémoire canonique.

Le texte du modèle reste intact et `inferred` reste `inferred`. La réserve qualité de P6-L1 sur la mauvaise date est conservée. Le formateur UTC 6C reste disponible ; son chargement et l'affichage du nouvel endpoint dans le panneau nécessitent encore un raccordement serveur/UI contrôlé. Il n'est pas licite d'utiliser une liste d'IDs suggérée par le modèle à la place des reçus.

## 6. Frontière OS et réseau

Voir `security/phase6d/ISOLATION.md` et les modèles `.service.in`, non installés. Ils séparent gateway, mémoire/bridge, contrôleur, exécutant technique et compte Hermes Windows. Les secrets HA et les données personnelles sont exclus d'Hermes et de l'exécutant.

Le worker actuel reste intégré au processus gateway avec le même UID/HOME et de larges accès shell/réseau. La séparation ne peut donc pas être obtenue par un simple fichier d'unité supplémentaire : il faut déléguer l'exécution à un broker indépendant, imposer des répertoires de mission et sorties réseau bornées, et supprimer la voie directe de lancement sous l'UID gateway. Les identités et ACL doivent être propagées jusqu'aux outils métier, pas seulement jusqu'à `/ask`.

Les profils proposés sont des contraintes de revue, pas une isolation effective validée. Le profil exécutant sans réseau permet des tests locaux déterministes ; il ne permet pas le CLI Codex distant actuel. Il faut un chemin fournisseur contrôlé distinct pour ce dernier. Rien ne réutilise ses capacités pour Hermes. Aucune modification RAM/balloon, compte, firewall, service Windows ou production Proxmox.

## 7. Lots de patch et restauration

Les empreintes exactes par fichier et préimage sont dans `phase6d/patch-manifest.json`. Les quatre lots ont été appliqués sur copie puis inversés dans l'ordre inverse, avec comparaison octet par octet. Les trois premiers ont aussi été réappliqués/inversés séparément depuis leur préimage. Le lot panneau dépend de l'HTML du lot auth ; il est réversible séparément à cette frontière. Le candidat gateway est vérifié syntaxiquement, sans être importé.

| Lot | Périmètre | Dépendances / repli |
|---|---|---|
| 01 central-security | 5 modules de politique/auth et montage global de `server.js` | Exige adaptateurs métier avant activation. Ne jamais revenir à une gateway anonyme pour contourner un refus |
| 02 independent-auth-client | Client autonome, HTML auth seul, reprise du loader voix et rafraîchissement mémoire après connexion | Inerte si l'ancienne gateway répond session 404. Retrait des assets séparé des permissions serveur |
| 03 voice-owner | Petit patch du backend **actif**, plus registre de propriété | À installer avant d'accorder la voix au garde central ; inerte sans contexte serveur fiable |
| 04 optional-hermes-panel | Assets du panneau et ajout HTML | Nécessite 02 et une façade Hermes authentifiée ; n'installe pas le bridge ni n'active l'admission |

Il n'y a ni copie du patch 15 fichiers de 6C en bloc, ni changement de moteur. Le patch minimal de propriété vocale est calculé depuis le backend actif, pas depuis l'ensemble des changements expérimentaux 6B. Les extensions mémoire et modèles OS sont des travaux séparés, hors de ces quatre lots.

Avant une opération autorisée : comparer toutes les préimages, sauvegarder code/configurations/modes/propriétaires dans un emplacement privé, vérifier une restauration sur copie. Arrêter si une empreinte diffère. Ne jamais publier les secrets dans Git. Les nouvelles tables n'exigent pas de suppression au repli : désactiver l'extension et garder les preuves. Pour une restauration de base, restaurer d'abord vers un fichier distinct et vérifier l'intégrité, sans écraser une base active.

## 8. Validation et résultats

`JARVIS_2_PHASE6D_TEST_RESULTS.json` conserve les résultats des 11 commandes de préparation et de vérification. Les tests comprennent :

- 100 couples classés, 96 couples métier protégés exercés en autorisé/refusé ; identité de service refusée sur les routes humaines, espaces, permissions, origines et méthodes inconnues.
- Copie exacte des fonctions gateway avec calibration/S9/shell remplacés par des stubs. Deux appels physiques simulés et un lancement simulé autorisés dans ce seul test ; **zéro action physique ou shell métier réel**.
- Backend minimal candidat dans une VM JavaScript, imports/timers neutralisés : refus de vol de session vocale dans le même espace avant fournisseur.
- Déconnexion, retrait de droit et panne de politique coupant un flux ouvert simulé ; expiration et révocation reprises des tests 6C.
- Symlinks, traversée et préfixe statique ; empreinte modifiée refusée ; fichier de politique trop permissif ou lien refusé.
- Connexion autonome sans panneau sur Chromium desktop/mobile, puis panneau en consultation seule avec API simulée.
- Sept tests Python : HTTP authentifié réel **en loopback éphémère sur SQLite synthétique**, reçus/provenance, refus de publication et fausse autorité, heartbeat/rejeu, gardien/reprise prudente, sauvegarde/restauration/idempotence.
- Régressions speech/PCM/interruption et bridge persistant existantes, fournisseurs simulés.

Deux erreurs du banc local ont été corrigées : absence de charset UTF-8 dans la page de test autonome ; sélection d'un fichier WAL/SHM par un glob de sauvegarde. Le test utilise désormais le chemin exact retourné par la migration. Les données de production n'ont pas été modifiées pour masquer ces erreurs. Les commandes échouées ont été revérifiées après correction ; les commandes déjà passées ont été conservées plutôt que de relancer les pilotes.

Aucune nouvelle preuve GPU, Gemini réel, Hermes, Safari matériel ou isolation OS active n'est revendiquée. Les pilotes P6-L1/P6-L2 et les verdicts historiques B2/C1 restent inchangés.

## 9. Décision par élément

| Élément | Résultat local | Verdict d'activation production |
|---|---|---|
| Sécurisation générale | **GO** registre/guard/copies testés | **NO-GO** : adaptateurs métier, audit durable et isolation worker à raccorder ; sinon fonctions historiques refusées |
| Installation panneau | **GO** client découplé et lecture seule simulée | **NO-GO** pour panneau fonctionnel : auth globale/ACL et façade composées requises ; dépôt d'assets inertes possible seulement après accord du patch |
| Service bridge | Composants existants conservés, extensions authentifiées testées | **NO-GO** service permanent : identité OS, stockage/configuration et supervision non provisionnés |
| Admission Hermes | Aucun changement de permissions ni d'activation | **NO-GO** avant les points précédents ; template synthétique seulement lors d'une future fenêtre autorisée |
| Test vocal réel | Transport simulé et propriété testés | **NO-GO** : accord spécifique, compatibilité globale et budget nécessaires ; moteur hybrid inchangé |

Les prochaines actions utiles restent locales : implémenter les adaptateurs de ressources historiques (listes filtrées/propriété/espaces et synchronisation), compléter la propagation d'identité aux outils et préparer l'extraction du worker avec son contrat d'exécution borné. Puis composer la façade Hermes avec **l'unique** registre de sessions central, sans empiler deux registres de cookies incompatibles. Relier enfin l'endpoint canonique et la disponibilité au panneau, sous ACL. Aucun nouveau pilote Hermes n'est nécessaire pour ces correctifs.

Une autorisation de production ne sera pertinente qu'après ces correctifs, sur leurs préimages exactes : sauvegarde/copie et fenêtre de redémarrage gateway ; création d'identités OS/configurations réseau ; service bridge ; activation du template ; essai vocal. Ce message ne sollicite ni compte ni démarrage. En cas de refus pendant une future activation, conserver la protection, désactiver l'admission et remettre les assets précédents ; ne pas restaurer une exception anonyme ou donner un rôle supérieur.

### SHA-256 des lots de revue

- `01-central-security.patch` : `f93a90affd87831676f864d2a0a0e49a148c9f943815796f5e9902be1e045def`
- `02-independent-auth-client.patch` : `dfd8505c413f92c927f5761829279cab04845a72d193ca60de1f415a89a72d30`
- `03-voice-owner.patch` : `56c74253557c67a8996b2e9538ec57e178d37e851c15a22df0494ad7d9c8d104`
- `04-optional-hermes-panel.patch` : `b371e2b8842e584ebdd76e2513078f2aec384ef482b5b135d8190b301ab644ae`
