# JARVIS 2.0 — Décision de production, phase 6

Date : 15 novembre 2026. Worktree `jarvis-2-memory`, branche `codex/jarvis-2-memory-20261113`. Socle de revue : `7fda6ae`. Les preuves Hermes et les verdicts historiques restent inchangés.

**Décision : les raccordements persistants principaux et une entrée de remplacement sont désormais codés et testés sur fixtures. L'installation globale reste NO-GO. Le montage complet des services auxiliaires/vocaux et l'authentification Codex isolée ne sont pas démontrés. Ce document ne présente pas ces travaux logiciels restants comme de simples autorisations administratives.**

Aucun fichier actif, compte, service, pare-feu, équipement ou base personnelle n'a été modifié. Aucun nouveau contenu personnel n'a été consulté. Aucun fournisseur distant, GPU, Hermes ou pilote historique n'a été lancé. Aucun changement de RAM Proxmox n'est proposé.

## 1. Ce qui est développé et vérifié

| Raccordement | Implémentation et preuve | Limite exacte |
|---|---|---|
| Documents | `Persistence` réutilise `docs`, `search` FTS5 et `g_resource_acl` ; SQL borné par les droits, index conservé dans les tables originales | Les propriétaires réels ne sont pas attribués ; aucune migration réelle |
| Faits vocaux | Tables originales `facts`, `correction_events` ; clé normalisée par la fonction historique ; métadonnées de propriétaire, statut et suppression logique dans la même base | Les propositions restent `inferred`. Les faits historiques non attribués sont refusés. Pas de reclassification comme faits vérifiés |
| Archives | Fonctions historiques `conversation_session` / `conversation_record`, appelées dans une transaction contrôlée ; même schéma, source, date et identifiant de document | Une session appartient à une identité, même dans un espace partagé. Révisions remplacées conservées dans des tables d'historique additives |
| Import | Parseurs existants JSON et ZIP ChatGPT ; mêmes identifiants, empreintes, dates et provenance ; ingestion transactionnelle avec contrôle du propriétaire avant remplacement | Fixtures seulement ; les exports personnels ou très volumineux ne sont pas validés ici |
| Synchronisation | Parseurs existants Markdown / JSONL Codex ; uniquement les chemins configurés par identité et espace ; liens symboliques refusés, pas de découverte globale de HOME | Les chemins réels nécessitent une sélection approuvée. Aucun ancien propriétaire n'est adopté |
| Import en flux | Upload privé, fragments bornés, propriétaire/espace/ordre/taille vérifiés, abandon explicite ; plafond de 3 Gio | Les uploads en cours ne sont pas repris automatiquement après redémarrage ; un fichier orphelin doit être inspecté puis traité explicitement |
| Projets et chats | Projets explicitement accordés, lecture de fichiers via le garde existant ; fichiers historiques `chats/<projet>.json`, sauvegarde vérifiée avant effacement | Le service storage doit être seul écrivain ; le raccordement des transitions complètes broker→chat n'est pas terminé |
| Runs | Registre durable existant du broker ; lecture propriétaire/projet/espace ; événements persistants, pas de rejeu incertain | Les anciens runs étaient en RAM dans la gateway : aucun propriétaire ni état n'est reconstruit à partir de logs. Fournisseur réel non activé |
| Comptes auxiliaires | Liaisons serveur et métadonnées par ressource ; connecteurs concrets des listes Mirror/tasks et frigo, formats JSON existants, filtrage avant réponse | Les hôtes complets des autres handlers restent à composer ; voir §3. Les champs d'affichage `person` ne donnent aucun droit |
| Carte mémoire | Contrat historique 384 dimensions, projection orthogonale stable, curseur ; propriétaire, espace et version du document/fait revérifiés dans SQLite avant l'extrait | Qdrant simulé ici. Le connecteur ne possède que `points/scroll`, jamais création/prune/suppression. Le compte global non autorisé n'est pas exposé |
| Entrée gateway | `productionEntry` compose sessions centrales, métier, mémoire, hybride, transport broker et façade Hermes ; aucune route Codex libre de secours | Fabrique testée, pas un remplacement installé et complet du serveur courant |
| Voix derrière IPC | Origine HTTPS attestée dans le contexte serveur privé ; propriété des sessions conservée ; proxy PCM en flux | Le service vocal complet et sa consultation de révocation doivent encore être montés, pas seulement la bibliothèque de transport |
| Authentification autonome | Bootstrap explicite du client d'authentification dans les HTML approuvés ; indépendant du panneau Hermes | Le manifeste complet des assets et des origines réelles reste à approuver |

Les parseurs Python sont chargés à partir des seules fonctions nommées du code existant ; le démarrage du module historique n'est pas exécuté. Les migrations cachées de normalisation/prune de l'ancien script vocal ne sont pas reprises. Les imports ne recopient pas les bases dans une deuxième mémoire. Les tables nouvelles contiennent des droits et de l'historique, pas une seconde vérité active.

`ops/production-storage-migrate.py` ne touche à aucune base sans `--execute-approved` et manifeste privé explicite. Il prépare des sauvegardes SQLite cohérentes avant migration ; le mapping documents/conversations/faits est explicite, vérifié et rejouable sans réattribution. Il refuse d'inventer le mapping des comptes auxiliaires. Exécution testée deux fois sur données fictives seulement. Le mode par défaut n'ouvre aucune base.

## 2. Contrat Codex et identités OS

Le CLI local observé est **0.163.0**. Seules version et aide ont été exécutées ; aucun fichier OAuth ou HOME personnel n'a été copié ou inspecté pour ce travail.

La [documentation officielle OpenAI sur l'authentification](https://learn.chatgpt.com/docs/auth?surface=cli) distingue connexion ChatGPT et clé API. Le CLI installé expose les modes de connexion usuels, dont la connexion par appareil et la lecture d'une clé sur stdin. Cela ne démontre ni les droits du compte actuel ni la compatibilité d'un proxy OAuth avec notre confinement. Le profil Responses déjà développé n'est pas un remplacement validé de cette connexion.

| Choix à trancher | Conséquence |
|---|---|
| Connexion ChatGPT dédiée | Évite de présumer un budget API. Nécessite une connexion humaine approuvée et la validation du transport/authentification sous une identité séparée. Le maintien des justificatifs hors des commandes du sandbox n'est pas résolu par une simple copie de `auth.json` : cette copie est exclue |
| Projet API dédié et proxy préparé | Chemin fournisseur déjà codé et testé avec faux endpoint. Exige une clé dédiée et un plafond positif explicitement approuvé avant tout essai ; à **0 CHF**, le broker bloque l'exécution avant le transport |
| Réutilisation du worker actuel avec HOME/réseau étendus | Exclue : contournerait précisément le confinement demandé |

**Aucun de ces choix n'est appliqué.** Le broker ne peut aujourd'hui servir une vraie réponse Codex isolée dans le budget autorisé. Activer cette entrée en remplacement global casserait donc les demandes techniques du mode hybride ; cela suffit à interdire le déploiement global.

Les profils sont fournis sous `security/production/` : gateway, storage, broker, exécutant et pont de puissance. Ce sont des modèles non installés. Le namespace exécutant reste sans réseau hôte ; seul un socket fournisseur approuvé par job peut être monté. Aucun secret HA/Hermes/gateway, HOME personnel ou workspace entier n'est monté.

Correction IPC importante : une socket `0600` n'était pas utilisable entre deux UID différents. Les démons broker/storage acceptent désormais un GID IPC explicitement configuré, vérifient l'appartenance du service, appliquent `0660`, conservent l'authentification applicative et la liaison des sujets. Le défaut demeure `0600`. L'exécutant ne doit pas appartenir aux groupes gateway/storage. **Le mécanisme a été testé sous l'UID de laboratoire ; la séparation entre comptes réels et les profils systemd ne sont pas encore certifiés.**

Les limites systemd sont des plafonds, pas des réservations ni des mesures de consommation. Elles doivent être acceptées après essais sous les identités approuvées. Aucune modification des VM ou du ballooning n'est nécessaire à ce plan.

## 3. Travaux logiciels encore bloquants — périmètre fermé

Ces points ne peuvent pas être levés par un simple « oui au déploiement » :

1. **Hôte vocal privé complet.** La bibliothèque vérifie identité, permissions et révocation via un callback obligatoire ; les sockets et le proxy en flux sont testés. Il reste à composer le serveur vocal réel, son introspection de sessions vers le registre unique, le metering et les outils autorisés. L'entrée candidate appelle `/api/internal/usage` et `/api/internal/tools` : aucun hôte de production complet pour ces contrats n'est livré. Ne pas les faire retomber sur un ancien handler non protégé.
2. **Hôtes des applications auxiliaires.** Les métadonnées et les connecteurs tasks/frigo sont concrets. Apple/iCloud, Astro, Allemand, Solana, rapports et mutations frigo nécessitent encore la composition de leurs handlers dans les services dédiés. Les anciens fichiers globaux ne deviennent pas multi-utilisateurs par l'ajout d'un header. La publication HA/Influx du frigo doit rester sous une autorité indépendante et conserver ses effets explicitement autorisés.
3. **Allemand et images.** Le code réel `allemand-en-poche/ai.mjs` lance son propre CLI et accepte des images. Notre broker textuel ne le remplace pas sans adaptation. Lui attribuer les droits de l'ancien utilisateur ou supprimer la fonction photo ne serait pas une compatibilité réussie. Le contrat multimodal et sa comptabilité restent à raccorder, sans appeler le fournisseur maintenant.
4. **Cycle complet des chats.** Les fichiers natifs et leur autorisation sont raccordés, mais les messages user/assistant mis à jour par les transitions du broker doivent encore être synchronisés de manière idempotente. Le registre durable des runs seul ne remplace pas ce comportement de l'ancienne gateway.
5. **Approbations physiques et montage final.** Le pont de puissance expose un contrat d'approbation indépendante ; le transport de consommation des reçus et le raccordement métier effectif ne sont pas composés. Dans l'entrée candidate, les actions physiques restent refusées. Ce refus est sûr mais ne permet pas de déclarer les fonctions historiques préservées.
6. **Compatibilité du repli avec les nouveaux états mémoire.** Les patchs de code sont réversibles octet pour octet sur copie. Cela ne valide pas un repli fonctionnel vers l'ancien lecteur brut après des écritures réelles : il pourrait ignorer une suppression logique ou le statut `inferred`. Avant des écritures personnelles, il faut conserver les adaptateurs autorisés dans la version de repli et tester ce cas. Ne pas restaurer une ancienne base par-dessus de nouvelles données.

Le choix d'authentification Codex est une dépendance externe supplémentaire. Le fichier `security/production/installation-contract.json` garde explicitement les entrées non composées à `null` et `commissioned=false`. Le manifeste conserve `production_activation_ready=false`.

## 4. Boucle appelée S19 dans les rapports : comportement observé du S9

Le code réellement présent dans `gateway/server.js` emploie **S9**, `/api/s9/*` et `input_number.s9_power_target`. Ce constat ne prouve pas que ces identifiants représentent le S19 XP Hydro. Aucun appareil n'a été interrogé pour trancher cette identité, et aucune valeur de secret/configuration active n'a été lue ici.

Comportement du code :

- `startBackgroundLoops()` est appelé lors de l'écoute HTTP, pas une seconde fois pour HTTPS.
- Si `S9_CONTROL_ENABLED` est vrai, il lance immédiatement un poll, puis un intervalle dont le défaut dans le code est 5 secondes.
- Le poll ne fait rien sans mot de passe ou si un appel est en cours. Il lit la consigne HA, l'arrondit ; la première lecture initialise le verrou sans commande.
- Un changement met à jour la consigne mémorisée **avant** l'appel ; authentification GraphQL du mineur puis mutation `updateAutotuning`, mode `POWER_TARGET`, `apply:true`. Bornes par défaut du code : 800–1420 W.
- En échec, le verrou demandé est déjà avancé : l'ancien code ne réessaie pas la même cible à chaque poll. Les états sont seulement en RAM et perdus au redémarrage.
- Le POST manuel applique la cible sans actualiser le verrou HA. Le statut HTTP et le rapport minier lisent les états en RAM.

Le module séparé `s9-power-service.mjs` conserve la lecture initiale sans commande, les bornes, le verrou avant l'effet et la sérialisation. Il journalise durablement l'intention et les résultats ; une interruption/erreur devient incertaine, sans rejeu automatique. Après redémarrage, la première lecture réinitialise la consigne observée sans appliquer un changement survenu pendant l'arrêt. L'arrêt attend l'opération en cours ; un arrêt durant l'approbation empêche une nouvelle intention. Réconciliation humaine uniquement, service arrêté.

Différences explicites à revoir : l'état manuel appliqué peut être enregistré ; une erreur devient visible et exige réconciliation plutôt que rester un simple log. Ce n'est pas une correction silencieuse d'une décision d'équipement.

L'entrée `s9-power-main.mjs` et le modèle d'unité sont préparés, jamais exécutés. Le service refuse un démarrage non commissionné ; son réseau doit être limité aux adresses HA/mineur vérifiées. Il n'a pas de fonction minage, shell, pompe ou mission Hermes. L'approbation manuelle doit être consommée auprès d'un service distinct, avec empreinte de la demande exacte. **Ce service d'approbation n'est pas considéré comme disponible parce que son URL figure dans la configuration.**

Le transfert exige une seule autorité d'écriture, une fenêtre et l'identification de l'équipement réel. Ne jamais démarrer le nouveau poll pendant que l'ancien tourne. Aucun arrêt/redémarrage du mineur, modification HA ou changement Kryptex n'est inclus.

## 5. Validation exécutée

Preuves nouvelles : `docs/production/test-results.json`. Les rapports et manifestes précédents ne sont pas régénérés.

- Treize commandes de vérification, fournisseurs simulés ; 39 tests Python au total après ajout des onze tests de persistance et des régressions conservées.
- Schémas SQLite des fixtures extraits des DDL des scripts réellement utilisés, sans ouverture d'une base personnelle.
- JSON/ZIP ChatGPT, Markdown/JSONL, conservation des sources/dates, idempotence, conflits de propriétaire, Commun sans droit implicite, versions d'archive et sauvegardes SQLite intègres.
- Migration préparée exécutée deux fois sur fixture : attribution explicitement fournie, document source inchangé.
- Transport Unix storage réellement exercé depuis Node vers Python/SQLite ; HTTP privé sur Unix et révocation réellement exercés, handlers fictifs.
- Entrée composée testée avec routage hybride et réponses simulées, refus anonymes et de contournement Codex ; PCM/microphone et interruption couverts par les régressions existantes avec faux fournisseur.
- Carte 384-D : faux Qdrant, vraies vérifications SQLite ; document d'un autre propriétaire et version périmée rejetés ; format de projection historique conservé.
- Pont de puissance : équipements simulés, redémarrage, absence de commande initiale, changement survenu à l'arrêt, état incertain, refus de réconciliation non approuvée.
- Tests Chromium desktop/mobile existants ; aucun iPhone matériel ni fournisseur vocal réel utilisé.

Ces tests ne valident pas les comptes OS, services installés, secrets, grands imports personnels, fournisseur Codex réel, réseau effectif ou migration physique. Une fabrique dont les dépendances sont injectées ne prouve pas que tous les démons correspondants sont montés.

## 6. Lots minimaux et ordre d'installation

Les **cinq lots, 28 fichiers** et leurs SHA-256 avant/après sont dans `docs/production/patch-manifest.json`. Le socle `7fda6ae` est une dépendance : ces deltas seuls ne constituent pas une release autonome. Les patchs s'appliquent et se retirent sur une copie avec retour exact aux préimages. Ils ciblent une nouvelle release, **pas les fichiers actifs**. Aucun patch en bloc des anciens quinze fichiers n'est demandé.

| Étape | Préconditions et impact | Acceptation et restauration | Verdict actuel |
|---|---|---|---|
| A — Release inerte | Socle épinglé + lots examinés, chemins/empreintes vérifiés ; pas de changement d'ExecStart, de base ou de listener | SHA-256 et application/retrait des cinq lots sur copie ; retrait de la seule release inerte | **GO technique pour revue/copie isolée** ; copie sur installation active non autorisée |
| B — Identités/IPC/configuration | Choix Codex, comptes et groupes distincts, politique propriétaire/espace/projet/compte, origine HTTPS, secrets dédiés | Vérifier refus croisés sous UID réels, socket 0660 et groupements ; retirer seulement les unités/répertoires nouveaux, conserver preuves et sauvegardes | **NO-GO opérationnel** : accords et essais sous UID réels manquants |
| C — Stockage canonique | Mapping approuvé, écrivains arrêtés, sauvegarde SQLite via backup API avec WAL, hash/integrity et restauration sur fichier séparé | Migration additive idempotente ; ni copie des faits vers une nouvelle vérité ni écrasement des sources ; conserver ACL/historique au repli | **NO-GO réel** : migration/mapping non autorisés ; repli logique à finaliser |
| D — Services historiques et Codex | B/C ; terminer les six raccordements §3 et valider le fournisseur choisi | Tests par famille sous identité réelle, fournisseurs fictifs d'abord ; couper admissions, conserver les jobs incertains ; pas de retour au worker large | **NO-GO technique** : hôtes et compatibilité fournisseur incomplets |
| E — Transfert puissance | Identification S9/S19, sauvegarde d'état, approbation indépendante, unicité de l'écrivain et restrictions réseau | Contrat d'état et reprise revus ; arrêt du seul nouveau service ; réconciliation humaine avant toute reprise d'un ancien contrôleur | **NO-GO** : migration physique distincte non autorisée et reçus non raccordés |
| F — Entrée/authentification/UI | B–E validés, manifeste complet des assets, clients historiques et service vocal compatibles ; flags Hermes à zéro | Basculer seulement la commande de démarrage vers la release préparée ; tests HTTP/sessions/espaces/voix autorisés avant ouverture d'admission | **NO-GO global** : ne pas installer une auth qui rend les fonctions existantes inutilisables |
| G — Hermes progressif | F et bridge validés ; historique séparé de l'admission ; template DoseLab synthétique seul | Activer d'abord consultation/panneau, ensuite admission, puis hybride ; couper immédiatement admission/hybrid au moindre incident | **GO laboratoire conservé / NO-GO production** ; aucun nouveau pilote Hermes nécessaire |
| H — Voix réelle | G, accord d'essai distinct et budget des services existants clarifié | Une demande DoseLab, sans conversation personnelle, commande physique ou mission libre ; aucune publication de compétence | **NO-GO** tant que les étapes antérieures ne sont pas acceptées |

Une installation future utilise la release immuable et les modèles de service ; elle ne lance pas l'ancien `server.js` en parallèle sur les mêmes ports. Le nouveau fichier d'entrée est fourni, mais **n'est pas déclaré prêt à basculer**. Aucun service Windows permanent n'est nécessaire ni proposé.

### Sauvegarde et repli

1. Avant modification autorisée : préimages des unités, configurations, assets et codes ; permissions conservées, empreintes vérifiées. Les secrets restent dans une archive privée séparée, jamais dans Git.
2. Sauvegardes SQLite cohérentes pendant la fenêtre exclusive ; `integrity_check` puis restauration dans une autre destination. Aucun ancien snapshot supprimé. La protection au repos et la destination indépendante restent à décider avant toute copie de mémoire personnelle, conformément au report C5.
3. En incident : couper l'admission, conserver consultation/annulation et registres, marquer les opérations ambiguës ; ne pas rejouer. Le repli de code testé est réversible, le repli de données exige les adaptateurs de statut/ACL mentionnés au §3.
4. Ne pas écraser une base modifiée par une sauvegarde plus ancienne. Si l'ancienne entrée doit être rétablie, conserver le périmètre réseau approuvé et ne pas rouvrir des routes anonymes. Un contrôleur physique incertain exige réconciliation avant repli.

## 7. Décisions et autorisations réellement nécessaires

**Décisions :** choix de l'authentification Codex séparée ; mapping explicite des propriétaires/lecteurs/rédacteurs/projets/comptes à partir du rapport privé déjà produit ; origine HTTPS LAN/Tailscale et périmètre réseau ; identification de l'appareil derrière le chemin S9. Aucun rôle universel n'est proposé. Une absence d'attribution reste un refus.

**Autorisations ultérieures distinctes, non demandées pour les travaux logiciels :** créer les identités OS et groupes IPC ; provisionner les secrets dédiés sans les afficher ; sauvegarder/migrer les données canoniques selon mapping approuvé ; appliquer les restrictions réseau ; installer et tester les unités sous UID distincts ; transférer l'unique boucle de puissance ; basculer la gateway ; puis effectuer l'essai vocal spécifique. Une permission de lecture de conversations ou transmission personnelle à Windows n'est incluse dans aucun de ces blocs.

Il n'est pas utile de solliciter maintenant une autorisation globale : les points logiciels §3 restent à terminer. Aucun compte ou budget ne doit être créé pour masquer un raccordement absent. Le prochain changement doit combler ces contrats précis, puis mettre à jour ce même rapport de décision, sans nouvelle phase ni répétition de P6-L1/P6-L2.

## 8. Verdicts demandés

| Objet | Verdict motivé |
|---|---|
| Sécurité globale gateway | **NO-GO production** — politique et raccordements locaux testés, mais hôtes auxiliaires/vocaux et repli logique incomplets |
| Fonctions historiques | **GO sur les formats et parcours testés / NO-GO global** — photo Allemand, transitions chats/runs et effets externes non composés complètement |
| Isolation Codex | **GO pour les protections de laboratoire déjà prouvées / NO-GO exploitation** — UID, fournisseur et authentification distincte non validés |
| Panneau Hermes | **GO technique isolé conservé / NO-GO montage actif** — dépend de l'entrée complète et des identités |
| Bridge et missions | **GO laboratoire conservé / NO-GO admission quotidienne** — pas de nouvelle preuve synthétique requise ; configuration/exploitation non activées |
| Premier essai vocal production | **NO-GO** — dépendances ci-dessus et accord spécifique requis |

Les fonctionnalités effectivement développées sont livrées ; l'objectif d'une installation globale immédiatement applicable n'est pas encore atteint. Les blocages restants sont nommés et distingués des autorisations. Jarvis actif reste inchangé.
