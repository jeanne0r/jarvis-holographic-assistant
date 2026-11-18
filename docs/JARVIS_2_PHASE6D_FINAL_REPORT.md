# JARVIS 2.0 — Finalisation de la phase 6D

Date : 15 novembre 2026. Branche : `codex/jarvis-2-memory-20261113`.

**Les adaptateurs métier, le broker privé, le confinement et la composition Hermes sont maintenant développés et testés localement. Cela ne permet pas encore un GO global de production.** La continuité complète n'est pas démontrée avec les stockages/comptes historiques et le fournisseur réel. Le manifeste indique explicitement `active_entry_patch_ready=false`. Les lots fournis sont des paquets de source examinables, pas un script d'activation du Jarvis actif. Aucun nouveau pilote Hermes n'est proposé.

## Résultats concrets

### Autorisations métier

`gateway-business.mjs` est raccordé au garde central et au registre unique de sessions dans `gateway-final-compose.mjs`. Il remplace l'ancien retour vers le handler libre pour les routes qu'il prend en charge. La matrice courante comporte **101 couples route/méthode**, dont la nouvelle route de disponibilité. La matrice antérieure et ses résultats restent inchangés.

- Projets : liste serveur filtrée par les projets explicitement autorisés. Fichiers : projet autorisé avant toute lecture, racine réelle et frontière de répertoire vérifiées ; symlinks et chemins sensibles refusés par `gateway-project-files.mjs`.
- Conversations : lecture et effacement nécessitent les droits du projet ; l'enregistrement vérifie le propriétaire et le droit d'écriture de l'espace. `/ask` conserve les enregistrements partiel/final et l'annulation liée à la fermeture de la réponse.
- Runs : admission limitée au projet autorisé ; aucune option libre d'environnement, de sandbox, de commande ou de réseau. Lecture limitée au propriétaire, événements au format SSE borné avec curseur de reprise.
- Documents : requêtes restreintes avant lecture, filtrage supplémentaire des résultats, contrôle de propriété avant et après lecture ; modification avec propriétaire et version attendus. Le déplacement exige un espace cible accessible en écriture.
- Commun : lecteurs et rédacteurs explicitement déclarés dans la politique serveur. La seule présence du profil visuel Commun, ou d'un champ `shared` fourni au modèle, ne donne aucun droit.
- Synchronisation : seules les sources configurées pour le sujet et l'espace sont transmises au service. Un chemin fourni par le navigateur est refusé. Import : flux transmis au service de stockage, borné à 3 Go ; pas de chargement complet du fichier dans la gateway ni de chemin choisi par le client.
- Familles Mirror, frigo, iCloud, Astro, Allemand et Solana : liaison serveur vers le compte ou la ressource autorisée, vérifiée avant le service correspondant. Les identifiants présents dans l'URL et le corps ne peuvent pas se contredire.
- Calibration et S19 : permissions distinctes et approbation humaine liée à l'action exacte, au sujet et à son empreinte, consommable une seule fois. Les tests n'ont appelé que des remplaçants synthétiques.

`gateway-tool-authority.mjs` vérifie les droits actuels à chaque appel d'outil, indépendamment du modèle. Il protège aussi le partage, les écritures mémoire et les actions physiques. Un ancien stockage de faits sans métadonnées de propriété ne devient pas sûr parce qu'on lui ajoute un champ `actor` : les écritures sont refusées tant que son adaptateur de propriété n'est pas disponible, et les listes sans propriétaire autorisé ne sont pas transmises au modèle.

`legacy_repository.py` fournit un raccordement SQLite concret au schéma existant `docs`/FTS5, sans duplication des connaissances. Sa table additive contient uniquement les métadonnées d'accès. Migration avec sauvegarde vérifiée ; attribution initiale explicite, jamais déduite d'un profil. L'ancienne source, les dates et le corps restent dans les tables d'origine. Lecture, création et déplacement transactionnel ont été testés sur une base synthétique au même schéma.

**Limite importante :** les connecteurs de stockage des faits vocaux, d'archives/synchronisation/import, les comptes des applications et leurs transactions doivent encore être raccordés aux services persistants réels sous leurs identités distinctes. Les tests injectent des services fictifs pour ces opérations. Le raccordement documentaire SQLite réel en laboratoire ne valide pas à lui seul tous ces autres connecteurs.

### Mode hybride et Codex

`gateway-hybrid-authorized.mjs` conserve `hybridAnswer`, son classificateur et son moteur public. Les dépendances dangereuses sont remplacées par des outils sous autorité humaine et par `codex-broker-client.mjs`. Une conversation ordinaire ne contacte pas Hermes. Une demande Hermes non prise en charge ou désactivée ne retombe pas sur le worker Codex.

Le broker est une implémentation séparée en Python standard :

- Socket Unix privée, trames et délais bornés, identité de service et sujets autorisés ; aucune écoute TCP.
- Registre SQLite des jobs techniques, clés d'idempotence par propriétaire, événements immuables et états persistants. Un job interrompu devient incertain, sans rejeu automatique.
- RPC limité à admission/consultation/annulation. Le démarrage de l'exécutant est réservé au superviseur ; aucun appel du navigateur ou d'Hermes ne peut l'activer.
- Projet et paramètres vérifiés indépendamment du prompt. Le client gateway ne lance aucun shell ni CLI et ne transmet ni environnement ni secret de production.
- `Executor` refuse de démarrer si son UID est celui de la gateway ou root. Il ne monte qu'un répertoire de mission préparé et un runtime en lecture seule, avec quotas de temps et de sortie, et résultat structuré lu sans suivre un symlink.
- Le proxy MCP par job est lié côté serveur au sujet et à l'espace. Une révocation coupe les appels d'outils ; le modèle ne choisit pas son identité.

**Confinement réellement exercé :** Bubblewrap avec namespaces de fichiers/processus/réseau, environnement vidé et racines bornées. Des sentinelles synthétiques non montées et un listener local de test sont inaccessibles ; l'écriture dans le workspace monté fonctionne. Le CLI installé exécute réellement `codex exec --help` dans ce confinement, sans inférence.

**Ce qui n'est pas prouvé :** exécution sous un nouveau compte OS distinct, compatibilité du profil systemd avec ce compte, passage complet du CLI vers un fournisseur réel, génération d'une réponse Codex réelle et exploitation des anciens outils personnels. Les modèles de service ne prouvent pas ces points. Aucun compte ni service n'a été créé.

### Réseau et coûts de l'exécutant

Le profil préparé garde le namespace réseau isolé. Un relais HTTP local→socket Unix et un proxy fournisseur externe au sandbox permettent de préparer le chemin Responses sans y monter la clé fournisseur. Le connecteur HTTPS fixe `api.openai.com:443` et `/v1/responses`, vérifie TLS, épingle une adresse publique résolue et refuse les redirections. Le profil est textuel ; les outils hébergés payants et les modalités non prévues sont refusés.

Le registre de réservations applique un plafond mensuel partagé, avec bornes de contexte/sortie et prix plafonds approuvés. Une requête incertaine n'est ni remboursée automatiquement ni rejouée. **À 0 CHF, aucun appel distant n'est autorisé et le transport n'est pas appelé.** Les tests de relais HTTP/Unix utilisent un fournisseur fictif ; aucun justificatif réel n'a été lu.

Le choix d'une authentification Codex dédiée reste à approuver. Le profil API préparé n'est pas assimilé à l'authentification actuelle du CLI ni à son éventuel abonnement. Il ne faut pas copier son HOME/OAuth personnel dans le sandbox ou créer une dépense supplémentaire pour faire fonctionner ce profil.

Cette séparation suit le principe de conserver les secrets tiers hors de l'environnement d'exécution décrit par la [documentation officielle OpenAI sur les agents persistants](https://developers.openai.com/blog/securing-persistent-agents-like-openclaw-at-openai). Les tests locaux, et non cette référence, fondent les verdicts de ce rapport. Aucun nouveau service Agents API n'est utilisé.

### Composition Hermes finalisée en laboratoire

Le même objet `sessionRegistry` est utilisé par le garde global, les adaptateurs métier et la façade Hermes : pas de seconde base de cookies, pas de jeton maître de secours.

- Consultation de l'historique indépendante de l'admission.
- Admission synthétique DoseLab seulement, avec clé stable et retour immédiat ; aucune conversation ou mémoire privée transmise.
- Approbateur humain et identité de transport d'approbation distincts.
- Annulation et résultats persistants via le bridge existant.
- Disponibilité issue du heartbeat Proxmox, avec état inconnu quand il est absent/périmé ; aucun démarrage du PC ni du GPU.
- Résultats enrichis par la projection canonique issue des reçus d'outils autorisés. Le panneau n'affiche les métadonnées que si elles sont liées à la mission et portent des reçus d'hôte. Les réponses du modèle ne sont pas réécrites.

L'interface desktop/mobile montre les références exactes et les dates UTC dans une section séparée. `inferred` reste `inferred`. La réserve P6-L1 sur la mauvaise date n'est pas effacée. La disponibilité et les notifications restent dans le panneau, sans déclenchement automatique de voix. Le panneau demeure caché lorsque le serveur ou les fonctionnalités correspondantes ne sont pas disponibles.

## Validation

Les résultats nouveaux sont exclusivement dans `phase6d/final/test-results.json` et les artefacts de ce répertoire. Le runner `scripts/evaluate_phase6d_final.py` ne lance ni les pilotes historiques, ni Hermes, ni un fournisseur réel.

- Tests d'intégration métier : listes filtrées, propriétaires, Commun, import en flux, synchronisation bornée, mutation versionnée, corps usurpant une identité refusé/ignoré comme autorité, approbation physique exacte et non rejouable.
- 53 couples de routes des familles de comptes/applications exercés avec ressources et services fictifs, en plus des routes Jarvis/projets/chat/runs/Hermes ciblées. La politique centrale couvre les 101 couples classés, y compris les refus et les méthodes inconnues.
- Routage hybride public et technique simulé, sans appel Hermes sur conversation ordinaire ; conservation de la réponse synchrone conversationnelle via attente asynchrone du résultat broker.
- Registre unique de sessions, historique avec admission coupée, provenance et heartbeat ; transport MCP Unix réel avec outil fictif et révocation.
- Onze nouveaux tests Python : broker/idempotence/redémarrage, transport Unix réel, namespace réel, aide CLI réelle, quotas de processus, raccordement au schéma SQLite historique synthétique, coût à zéro et plafond partagé, relais fournisseur fictif. Sept tests Python 6D précédents conservés dans la sélection de régression.
- Chromium desktop/mobile, connexion autonome, affichage des métadonnées canoniques et disponibilité inconnue. Pas de Safari/iPhone matériel.
- Régressions des sessions, ACL, flux PCM/interruption et du bridge existant, fournisseurs simulés.

Le mot « réel » ci-dessus désigne précisément le transport Unix, SQLite, les namespaces et l'aide CLI. Il ne désigne jamais une inférence Codex/Hermes, un compte de production ou une action physique.

## Exposition actuelle et restrictions proposées

Audit local en lecture seule : gateway HTTP 8787 et HTTPS 8788 sur `0.0.0.0`, interface LAN `192.0.2.16/24`. D'autres écouteurs existent sur toutes les interfaces, notamment 8087 et 4173 ; ils ne sont pas sécurisés par le patch gateway. SSH écoute aussi IPv6. Des services auxiliaires sont sur loopback. Aucun de ces écouteurs ne démontre une exposition Internet ; la politique WAN et le pare-feu effectif ne sont pas certifiés ici.

Proposition, non appliquée : origine HTTPS LAN/Tailscale exacte, accès API réservé aux interfaces/sources approuvées ; HTTP limité à une redirection ou à un health minimal ; bridge sur loopback authentifié ; broker/outils sur sockets privées ; exécuteur sans réseau hôte ; seul le proxy fournisseur peut joindre les destinations approuvées. Ne pas fermer SSH/Tailscale ni modifier les autres ports sans identification du service et autorisation distincte.

Le code actif contient une **boucle automatique S19** dans `startBackgroundLoops()`. Elle doit rester inchangée aujourd'hui. Une gateway débarrassée de tous les accès techniques/physiques nécessite de sortir aussi cette responsabilité vers un service indépendant, avec revue et fenêtre propres. Arrêter cette boucle en modifiant aveuglément le démarrage pourrait perturber les fonctions existantes ; aucune telle opération n'a été faite.

## Lots de revue et dépendances

`phase6d/final/patch-manifest.json` donne chaque fichier cible, source, SHA-256 avant/après et empreinte du patch. Application et retour arrière sont vérifiés sur une copie pour chaque lot. Les bibliothèques mémoire inchangées du socle `6bb7c4e` sont réutilisées via `baseline-runtime-manifest.json` ; elles ne sont pas reconstruites dans le delta.

| Lot | Préconditions et impact | Tests / sauvegarde / repli | Autorisation |
|---|---|---|---|
| 01 politique | Fichiers de configuration privés, sujets réels et origine validés ; bibliothèques inertes sans montage | Politique/refus/révocation ; préimages vérifiées, copie privée des configs ; retrait des bibliothèques avant tout montage seulement | Copie de fichiers actifs/configuration distincte |
| 02 métier | 01, attribution explicite des propriétaires, connecteurs de stockage/comptes disponibles | Tests métier et SQLite synthétique ; sauvegarde SQLite cohérente avant migration ; désactiver le montage, conserver données/ACL, ne pas revenir à des routes anonymes | Métadonnées historiques, mapping et migration réels à approuver séparément |
| 03 transport Codex | 01, socket privée, compte broker et permissions IPC | Transport Unix et propriété ; sauvegarde registre technique ; geler admissions et réconcilier les jobs incertains | Comptes, chemins et permissions nécessaires |
| 04 runtime | Release immuable du socle + delta ; UID exécutant distinct ; quota/proxy/schema/exports de projet approuvés | Namespace/CLI help/quotas et provider fictif ; copie privée des configs et backup registre ; arrêt de cette seule unité/job, aucun replay | Installation de services et éventuel test fournisseur distincts ; budget reste zéro |
| 05 composition Hermes | 01–04 et bridge mémoire existant configuré, mêmes sessions ; flags à zéro | Composition synthétique hors GPU ; sauvegarde configs ; couper admission/hybrid, garder historique/annulation | Montage gateway uniquement après revue du patch d'entrée exact |
| 06 UI | 01 ; 05 pour les missions ; chargement du formateur avant panneau | Chromium desktop/mobile ; sauvegarde assets et empreintes ; retour aux assets précédents sans retirer l'authentification | Copie/chargement frontend après accord |

**Aucun de ces lots ne modifie aujourd'hui `server.js`, les fichiers actifs ou une base réelle.** Le fichier d'entrée d'activation n'est pas déclaré prêt : il doit sélectionner les connecteurs réels validés, supprimer le lancement direct Codex et traiter explicitement le cycle de vie S19. Fournir un patch de montage qui laisserait ces points implicites reproduirait le défaut que cette finalisation vise à éliminer.

## Blocages restants et autorisations précises

1. **Propriétaires historiques.** Le script `scripts/phase6d_owner_inventory.py`, testé sur des bases fictives, a ensuite été exécuté après autorisation explicite de cet inventaire uniquement. Le périmètre autorisé est limité à `data/brain.sqlite` (docs) et `data/voice-memory.sqlite` (facts) : schéma connu, comptes agrégés par espace et vingt lignes de métadonnées maximum au total, identifiants hachés, espace, type documentaire et horodatage uniquement. Aucun titre, corps, fait, source textuelle ou conversation. Rapport 0600 sous `/home/user/workspace/_private/jarvis-2/phase6d-owner-inventory/`, hors Git et sans transmission Windows/modèle. Aucune ancienne réserve C2 réutilisée. Il faut inventorier uniquement les métadonnées nécessaires (identifiants, espaces, sources et types, pas les contenus) puis faire approuver les sujets propriétaires/lecteurs/rédacteurs et les projets. Aucun document non attribué n'est adopté automatiquement. Aucun rôle administrateur ne sera créé pour masquer des refus.
2. **Connecteurs persistants.** L'adaptateur documentaire SQLite est concret ; les transactions des faits vocaux, archives, synchronisation/import, registres de runs et comptes auxiliaires doivent encore être reliées aux services sous identité de stockage. Les doubles de test ne prouvent pas la compatibilité de ces implémentations réelles. Le patch d'entrée ne peut pas être approuvé avant ce raccordement.
3. **Identités OS et IPC.** Autoriser séparément la création de `jarvis-broker` et `jarvis-code-exec` (et l'identité stockage/proxy selon implantation), les répertoires privés, la release en lecture seule et les droits des sockets. Ensuite seulement tester le profil d'unité sous ces UID, avec sentinelles synthétiques. Aucun service permanent ni auto-start n'est demandé implicitement.
4. **Codex réel.** Choisir une authentification dédiée compatible avec le CLI actuel et valider le chemin fournisseur, sans crédit nouveau implicite. À défaut, le broker peut conserver des jobs mais ne peut pas rendre de réponse Codex réelle ; donc pas d'activation globale qui casserait le mode hybride technique. Aucun essai payant n'est autorisé par le présent travail.
5. **Gateway et S19.** Revoir le patch exact d'entrée et prévoir une fenêtre de sauvegarde/redémarrage ; migration de la boucle S19 sous responsabilité distincte uniquement avec accord spécifique, en préservant ses fonctions et sans commande d'équipement dans les essais.
6. **Réseau et voix.** Choisir l'origine HTTPS exacte et autoriser séparément toute règle de pare-feu/bind ou essai vocal. L'essai vocal ne doit venir qu'après compatibilité des connecteurs et identités, et avec ses coûts explicitement traités.

Les points 2 et le câblage final d'entrée sont encore du travail logiciel ; ils ne doivent pas être présentés comme résolus par une autorisation administrative. Les autres points comportent des décisions ou opérations de production interdites dans ce tour. Aucun nouveau pilote synthétique Hermes n'est nécessaire pour les traiter.

## Verdicts consolidés

| Critère | Ce qui est démontré | Verdict production |
|---|---|---|
| 1. Sécurité globale gateway | Politique centrale et adaptateurs sous contrats testés, fail-closed | **NO-GO** : connecteurs persistants et entrée active non finalisés ; ne pas activer une protection rendant les routes inutilisables |
| 2. Compatibilité historique | Contrats métier, hybride simulé, SSE, mémoire documentaire et mobile validés en laboratoire | **NO-GO global** : tous les connecteurs et clients réels ne sont pas validés |
| 3. Isolation réelle Codex | **GO pour le confinement local testé**, transport privé et CLI help hors réseau | **NO-GO service réel** : UID distinct, unité, authentification et fournisseur non validés |
| 4. Panneau Hermes | **GO technique en laboratoire**, provenance et disponibilité raccordées | **NO-GO montage actif** avant identité/entrée/bridge validés ; copie inerte seulement sur accord distinct |
| 5. Bridge et missions | **GO composition locale** avec registre unique et services synthétiques ; preuves Hermes antérieures conservées | **NO-GO activation quotidienne** avant identité OS, supervision et configurations réelles approuvées |
| 6. Voix en production | Régressions audio simulées et hybride conservé | **NO-GO** sans étapes précédentes et autorisation d'essai spécifique |

Le prochain travail utile porte sur les connecteurs et l'entrée réelle, pas sur une nouvelle phase ou une répétition des pilotes. Aucune clôture de sécurité globale n'est annoncée tant que ces limites restent présentes.

## Empreintes des lots

- `01-policy.patch` : `96f1ca8e19632cf41f7b1e285982c6d86ea0fa5242f820b1b210b9eb536c92f3`
- `02-business.patch` : `39c1b2a5a6f711fac51d2463f0e5bf845be222d78f73077b0cfe5fc40d6a46b6`
- `03-codex-transport.patch` : `9be3240ee2897d9a5ae1bfd92ce1d90f996d25f72e19d963c8e5a51596baf770`
- `04-runtime.patch` : `6fa1f464309e877ccc77e96c08dd6de3c6fb53fc66070d7ed14591348b92d5f1`
- `05-hermes-composition.patch` : `4a589049792f1a06c27ca9b88e104dee585b1b42350dbf7f3dfbc27e279e891d`
- `06-ui-assets.patch` : `aa0dbbfeefe305167ef010c8d696efa38f599d03c14edd785418b80ffd49b6f0`

Contrôle final : 26 chemins actifs et identité du service gateway inchangés ; preuves historiques intactes ; neuf commandes de préparation/vérification réussies. Les 37 fichiers du delta sont des sources et assets de revue, pas des modifications appliquées à la production.

### Inventaire privé autorisé — résultat

Le rapport a été créé hors Git sous `/home/user/workspace/_private/jarvis-2/phase6d-owner-inventory/inventory.json`, avec des permissions `0600`. Un contrôle local, sans restitution des métadonnées, confirme les deux sources autorisées, la limite partagée de vingt lignes, les identifiants hachés et les seuls champs autorisés. Les comptes agrégés et les lignes restent exclusivement dans le rapport privé. Aucune nouvelle lecture des bases n’a été nécessaire pour ce contrôle. Aucun propriétaire n’a été attribué ; aucun contenu personnel, titre ou valeur de fait n’a été extrait. Aucun transfert Windows/modèle, déploiement, compte ou service n’a été effectué. Cette autorisation ne couvre aucune étape supplémentaire. Les verdicts de déploiement restent inchangés.
