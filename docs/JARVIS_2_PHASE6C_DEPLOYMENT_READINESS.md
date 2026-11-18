# Phase 6C — Décision de préparation au déploiement

Date : 15 novembre 2026. Branche : `codex/jarvis-2-memory-20261113`.

**Verdict : NO-GO pour activer Hermes dans la gateway actuelle. GO pour poursuivre la préparation locale.** Les pilotes P6-L1 et P6-L2 restent validés ; ils ne prouvent pas que l'ensemble des routes de production et les permissions du worker historique sont sécurisés. Aucun pilote n'a été relancé, aucun fichier actif modifié, aucun compte créé. Budget supplémentaire distant consommé : 0 CHF.

## 1. Installation réellement observée

L'audit en lecture seule est conservé dans `JARVIS_2_PHASE6C_ACTIVE_AUDIT.json` : empreintes, chemins, versions et réponses limitées à des métadonnées techniques. Aucune conversation ni configuration secrète n'a été extraite.

- Service `codex-gateway.service` actif, PID 2033987, démarré le 13 novembre à 21:29:24 UTC ; Node 18.19.1.
- Serveur exécuté depuis `/home/user/gateway/server.js`, import direct de `/home/user/workspace/jarvis/backend.mjs`. Interface servie depuis `/home/user/gateway/public/jarvis`.
- Écoute HTTP 8787 et HTTPS 8788 sur toutes les interfaces IPv4. Cela ne démontre pas une exposition Internet ; les règles réseau externes n'ont pas été modifiées ni certifiées.
- Consultation anonyme de `/api/jarvis/voice/status` : 200, moteur `hybrid`, `speechOnly=true`. `/api/jarvis/session` : 404. Aucun POST de production effectué.
- Les 15 cibles du patch préparé correspondent encore aux préimages examinées en phase 6B. Aucun élément de ce patch n'est installé.
- Aucun écouteur local observé sur les ports de laboratoire 8792, 8643, 11435 et 11436. Aucun démarrage Windows effectué ; son état courant n'est pas inféré de cette observation locale.

Le chemin vocal demeure `codex-voice.js` → `/ask` → routage hybride Gemini/Codex. Le correctif Hermes intercepte seulement une demande correspondant au template synthétique avant le worker, puis rend une admission persistante. Les autres demandes suivent le routage historique. Le pilote L2 l'a démontré pour Hermes ; ses fournisseurs conversationnels ordinaires étaient simulés. Il ne constitue pas un essai réel du microphone ni une validation de toutes les fonctionnalités historiques.

## 2. Écarts de sécurité encore ouverts

### Gateway globale : blocage prioritaire

`routeRequest` délègue `/api/jarvis/*` directement au backend. Le contrôle existant par jeton concerne certaines familles, notamment `/api/s9/*` et `/api/icloud/*`, sans authentification générale démontrée pour les autres routes.

Le wrapper préparé protège `/api/jarvis/*` seulement. Les routes sœurs `/api/projects`, `/api/tree`, `/api/chat` et `/api/runs` restent hors de ce wrapper ; les runs peuvent lancer un exécutant technique. `/api/dosing-calibration/run` atteint un déclencheur de calibration physique sans contrôle général observé dans ce chemin. Ces routes n'ont pas été invoquées. Leur protection ne peut pas être remplacée par le refus d'un outil Hermes.

Il faut une politique centrale couvrant toutes les méthodes et routes sensibles, avec une liste publique explicite et minimale, et une matrice des clients historiques. Aucun accès privilégié implicite via le jeton maître, les profils visuels, l'adresse locale ou une instruction du modèle. Les services non humains auront des identités distinctes et des permissions bornées. L'accès aux fonctions physiques historiques reste un sujet séparé : aucun droit physique ne sera accordé à Hermes.

La vérification statique des chemins utilise un préfixe sans frontière de répertoire et ne démontre pas de confinement des liens symboliques ; CORS statique est permissif. Ce sont des points à corriger/tester dans une copie, sans annoncer un exploit vérifié ni tenter une traversée sur le serveur actif.

### Compatibilité réelle et identités

Le wrapper actuel refuse certaines anciennes fonctions : synchronisation/import, évolution, certaines capacités et carte mémoire sans droit Commun. Activer `JARVIS_SERVER_AUTH=1` maintenant risquerait donc de retirer des fonctions. Il faut déterminer pour chaque fonction un contrôle précis ; ni rôle omnipotent ni accès Commun artificiel pour contourner un refus.

Les outils du worker historique construisent encore un contexte d'espace sans identité humaine fiable. Certaines lectures incluent Commun par défaut. Le worker Codex dispose de shell, réseau, recherche et écritures étendues, sous le même utilisateur OS que la gateway. Une session éphémère n'est pas un confinement OS. Hermes conserve sa façade et ses identités séparées ; aucune délégation vers ce worker n'est autorisée.

Le cookie préparé est limité à `/api/jarvis`. Il n'authentifiera pas automatiquement les routes sœurs. Une politique cohérente de cookie/origine et une migration des clients sont requises avant extension ; ne pas élargir silencieusement son chemin. Le module de connexion est encore couplé au panneau : le client de session doit être utilisable indépendamment pour déployer l'authentification en première étape.

Les sessions audio historiques sont liées à un identifiant et un espace, sans liaison démontrée au sujet humain. La propriété doit être testée entre deux utilisateurs du même espace. La révocation est vérifiée à l'admission d'une requête ; un flux audio déjà admis, borné jusqu'à 45 secondes, n'est pas démontré interrompu immédiatement. Définir et tester cette politique avant activation, sans modifier les mécanismes microphone/interruption/PCM.

## 3. Renforcements locaux réalisés

Les composants existants sont réutilisés, sans changement du moteur hybride ni des fichiers audio.

1. **Sessions humaines distinctes** : identifiants aléatoires émis par le serveur ; seule leur empreinte est conservée. Le secret de connexion n'est plus le cookie. Déconnexion révoquant la session présentée, y compris lorsqu'un header Bearer accompagne le cookie ; les autres sessions restent valides. Durée par défaut 30 minutes, maximum une heure et bornée par l'expiration du justificatif. Cookies HttpOnly, SameSite Strict et Secure en HTTPS.
2. **Politique relue à chaque requête** : mise à jour des rôles, espaces et justificatifs, révocation sans redémarrage. Fichier privé possédé par l'utilisateur, permissions 0600, régulier et sans suivi de symlink, lecture par le même descripteur. Configuration invalide ou changement de topologie : 503, sans repli non authentifié. Les sessions sont en mémoire : un redémarrage exige une reconnexion. Retirer un justificatif puis le remettre ne ressuscite pas ses anciens cookies.
3. **Authentification indépendante du bridge arrêté** : les secrets bridge ne sont chargés que si l'admission ou la consultation sont activées.
4. **Consultation indépendante de l'admission** : `JARVIS_HERMES_HISTORY=1` avec `JARVIS_HERMES_ENABLED=0` permet lecture des missions/résultats/événements et demande d'annulation, sous ACL. Création et approbation restent refusées. Aucun appel de disponibilité Windows n'est nécessaire pour afficher l'historique. Tous ces flags valent 0 par défaut.
5. **Métadonnées canoniques séparées** : prototype SQLite borné à 20 `memory_id` et 200 révisions, contrôlant les ACL et exposant uniquement références, statuts, révisions et dates UTC. Un formateur conserve le texte du modèle intact et affiche les dates canoniques séparément.

Le dernier point reste **inactif et non raccordé** : pas de nouvelle route ni de chargement dans le panneau. Les IDs fournis par le contrôleur ne prouvent pas à eux seuls un appel outil Hermes. Avant activation, relier la projection à des observations authentifiées de la mission et au résultat autorisé ; ne jamais transformer cette projection en preuve d'utilisation par le modèle.

Les cookies vivent au maximum sur ce processus, pas dans une seconde mémoire canonique. Les secrets longs restent révocables par rotation/retrait de la politique ; déconnexion ne signifie pas destruction du secret de connexion. Les approbations restent des décisions humaines indépendantes, soumises au sujet, à l'espace et à l'action exacte. Aucun rôle modèle ne les reçoit.

## 4. Patch exact et empreintes

Le manifeste `phase6c/patch-manifest.json` énumère les **15 chemins absolus**, SHA-256 avant/après, flags et prototypes séparés. Deux lots de revue ont été générés, appliqués puis inversés dans un répertoire temporaire, avec comparaison octet par octet. Aucun backend ni pilote n'est exécuté par ce générateur.

| Lot | Contenu | SHA-256 | Décision |
|---|---|---|---|
| `01-inert-libraries.patch` | Sept nouveaux modules serveur, sans import actif | `dc4fc85ff13c0ab39118b7ac61ca862223bdb28f2c063560dcbfe1946b623dc9` | GO technique pour revue/dépôt inerte, pas d'autorisation de copie implicite |
| `02-incomplete-activation-review-NO-GO.patch` | Backend, store, voice-memory, import gateway, interface et voice-router | `06f8dccf838f32cb200c17e4c43facd48fba8657aefc4f3cc71b237f06e624f6` | NO-GO pour application/activation |

Le second lot rend les écarts actuels examinables ; ce n'est pas un patch global de sécurité achevé. **Recommandation minimale : ne pas appliquer les 15 fichiers en bloc.** Finaliser d'abord la protection globale et la compatibilité, puis régénérer les lots indépendants. Ni modification du worker Codex ni correction globale des routes sœurs n'est cachée dans ces artefacts.

Les modifications par rapport au travail 6B concernent surtout `jarvis-session-auth.mjs`, `phase6-gateway.mjs` et `public/hermes-missions.js`. Les nouveaux prototypes de métadonnées ne font pas partie du patch de production. Le fichier `index.html` proposé reste celui de 6B ; la séparation complète connexion/panneau reste à faire.

## 5. Déploiement proposé : portes indépendantes

Les verdicts suivants concernent **l'activation sur le vrai Jarvis aujourd'hui**, pas les preuves historiques réussies.

| Étape | Périmètre et préconditions | Vérification attendue | Verdict actuel |
|---|---|---|---|
| 1. Identités/sessions | Politique globale de routes et clients ; client de connexion indépendant ; propriété des sessions audio ; conservation des fonctions existantes | Anonyme refusé, expiration/révocation/usurpation, deux utilisateurs même espace, compatibilité hybrid et clients historiques | **NO-GO** : patch global et matrice de compatibilité incomplets |
| 2. Panneau | Étape 1 acceptée, assets séparés ; aucune admission ; source de lecture disponible | Desktop/iPhone, historique et erreurs sans voix imposée, PC Windows éteint, ACL | **NO-GO** production ; panneau local validé avec API simulée |
| 3. Bridge, admission désactivée | Identité serveur et OS séparée ; SQLite synthétique distincte ; service Proxmox approuvé ; flags admission/hybrid à 0 | Redémarrage, intégrité, lecture sans Windows, annulation, quotas et secrets cloisonnés | **NO-GO** activation ; API et registre existants réutilisables |
| 4. Admission hybride limitée | Étapes précédentes ; template fixe DoseLab seulement, zéro contexte privé, worker Windows temporaire explicitement autorisé | Admission rapide par `/ask`, conversation ordinaire inchangée, résultat sourcé dans panneau, annulation | **NO-GO** production en attente des étapes 1–3 ; preuve laboratoire L2 acquise |
| 5. Essai vocal réel | Accord distinct fenêtre/ressources, humain connecté, étapes précédentes acceptées | Véritable voix → admission → résultat, interruptions et audio inchangés | **NO-GO** sans autorisation spécifique ; aucun essai vocal effectué ici |

Pour chaque étape : comparer les préimages au manifeste juste avant l'opération ; si divergence, arrêter et refaire la revue. Sauvegarder les fichiers touchés avec modes/propriétaires et configuration dans un emplacement privé, hors Git ; vérifier les empreintes et une restauration sur copie. Autorisation préalable nécessaire pour ces opérations de production. Aucun changement CT205 ou collection Qdrant requis par ce déploiement.

Les nouvelles bases synthétiques doivent être sauvegardées via l'API de sauvegarde SQLite, contrôlées par `integrity_check` et restaurées dans une base de test. Ne pas copier un fichier SQLite actif en ignorant son WAL. Aucun remplacement/migration d'une ancienne mémoire. La sauvegarde historique hors CT205 reste un sujet distinct non autorisé.

## 6. Comptes, configuration et fonctionnement quotidien

Préparer sans les créer : identité humaine individuelle avec espaces et permissions approuvés ; identité serveur gateway→bridge limitée au template et aux opérations nécessaires ; identité worker distincte pour les résultats/outils ; approbateur humain séparé ; utilisateur OS de service Proxmox à privilèges minimaux. Conserver l'utilisateur Windows laboratoire déjà validé, sans nouvel auto-start. Les secrets bridge/mémoire/approbation ne doivent être ni dans le frontend, ni le contexte modèle, ni accessibles au worker Codex par partage du même UID.

Origine HTTPS LAN/Tailscale exacte, chemins privés 0600 et topologie sont à arrêter en revue, sans publier de valeur secrète. L'accès loopback seul n'est pas une identité : compléter par authentification et isolation OS. Les limites réseau doivent être imposées hors du modèle.

L'API existante démarre par `python3 -m memory_manager.api --database <base-synthetique> --clients-file <configuration-privee> --phase2 --port 8792` et écoute loopback. Cette commande n'a pas été lancée ici. Une unité de service durable, ses limites et son identité nécessitent revue et autorisation ; aucun service permanent n'est installé par cette phase.

Le worker contrôlé existant diffère les missions lorsque Windows/GPU est indisponible ; les missions restent dans SQLite. Son cycle de travail n'est pas encore un démon de production livré et supervisé. Le démarrage doit passer par cette couche de contrôle, pas par un appel direct au moteur qui pourrait appliquer une échéance depuis la création. Démarrer le compteur d'exécution après admission effective au runtime.

Une mission dont la soumission a peut-être réussi ne doit jamais être créée à nouveau automatiquement. Réconcilier son run ID et son journal ; état incertain visible, intervention humaine si nécessaire. Une annulation de mission active n'est pas une preuve d'arrêt Windows : attendre la confirmation du run possédé. Aucun arrêt de Kryptex, aucun lancement automatique du GPU.

Il reste à brancher un heartbeat horodaté et sa péremption : le texte d'indisponibilité générique du panneau n'est pas une mesure réelle de présence. PC éteint, l'historique doit rester lisible depuis Proxmox, les missions en attente visibles, sans fournisseur payant de secours. Les notifications restent dans le panneau et ne déclenchent pas systématiquement la voix.

## 7. Qualité : conserver la réserve P6-L1

L1 a réussi l'intégration mais cité une mauvaise date : « 2023-11-15 » au lieu de `2023-11-14T22:15:00Z`. Sa réserve `content_fully_verified=false` est conservée. Le succès de L2 ne réécrit pas cette observation.

Le rendu préparé conserve la réponse originale, explicitement non vérifiée, et affiche une section SQLite distincte : date UTC, `source.ref`, révision, état actuel/remplacé et statut de validation. Aucun remplacement silencieux d'une date dans le texte. Une expérience `inferred` conserve ce statut ; ni résultat réussi ni projection de métadonnées ne la promeut.

## 8. Tests et limites

Voir `JARVIS_2_PHASE6C_TEST_RESULTS.json`, produit uniquement par `scripts/evaluate_phase6c.py` : tests de sessions/politique, quatre tests SQLite de métadonnées, panneau consultation seule Chromium desktop/mobile, régressions speech et transport phase 6. Tous utilisent des données synthétiques ou fournisseurs simulés ; aucune inférence, aucun microphone, aucun transfert Windows. Les patchs ont une répétition aller/retour sur fichiers temporaires, pas un déploiement.

À terminer avant toute activation : politique globale et matrice route/méthode/identité/client, séparation OS et réseau, propriété des sessions audio, couverture des fonctions historiques refusées, client auth indépendant, liaison canonique aux résultats, heartbeat et worker quotidien, test de quotas et pannes dans cette topologie. Le coût local de relecture de politique mesuré par le test n'est pas un SLA ni une preuve de latence sur la gateway active.

Les tests hybrides ordinaires antérieurs utilisent des doubles Gemini/Codex : une validation réelle de non-régression reste nécessaire dans une fenêtre autorisée. Un essai vocal peut utiliser les fournisseurs vocaux existants ; son budget doit être explicitement approuvé. Le budget distant supplémentaire de cette préparation reste strictement 0 CHF et n'autorise aucun nouvel appel payant.

## 9. Autorisations et retour arrière

Aucune activation n'est demandée sur la base du lot incomplet. Après correction des blocages, présenter le patch exact pour approbation distincte de chaque étape : sauvegarde/copie et éventuel redémarrage gateway ; identités/configurations ; assets du panneau ; service Proxmox synthétique ; fenêtre temporaire Windows/GPU ; enfin essai vocal. Aucun accès personnel, compte Windows supplémentaire, CT205, équipement physique ou publication de compétence n'est inclus.

Repli fonctionnel privilégié : admissions et déclenchement hybride à 0, consultation à 1 si autorisée ; conserver authentification, ACL, historique et annulation. Cela n'arrête pas un run déjà actif : le contrôler par son identifiant via le gardien autorisé. Restaurer les assets UI indépendamment. Un redémarrage peut invalider les nouvelles sessions et interrompre une session vocale ; planifier une fenêtre et une reconnexion, ne pas promettre de continuité audio pendant un redémarrage.

Ne pas retirer la protection globale pour rétablir une fonction incompatible. Restaurer la version sûre précédente ; si aucune version sûre n'existe encore, suspendre le déploiement et garder l'installation inchangée. Ne supprimer ni missions ni preuves lors du retour arrière. Toutes les preuves et verdicts historiques L1/L2/C1/B2 restent intacts.

## Contrôle final local

Les cinq commandes de vérification ont réussi (dont quatre tests unitaires SQLite). Relecture de politique : moyenne locale 4,862 ms par requête dans le test, non représentative d’une charge de production. Les empreintes des fichiers actifs et l’identité du service sont inchangées après les tests. Aucun artefact historique L1/L2/C1/B2 n’a été modifié.

Pour le coupe-circuit sans redémarrage : préparer dès le lancement autorisé la consultation historique et le fichier privé `JARVIS_PHASE6_SWITCH`, puis remplacer atomiquement son contenu par `{"enabled":false}` ; les nouvelles admissions s’arrêtent à la requête suivante. Les variables d’environnement seules ne se rechargent pas à chaud. Les modifications de politique doivent également être publiées par renommage atomique d’un fichier 0600, sans changer la topologie de transport ; aucun mécanisme d’approbation ne doit accepter une configuration partielle.
