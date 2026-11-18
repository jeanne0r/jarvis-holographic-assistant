# Missions Hermes dans le Jarvis existant — patch à revoir, non déployé

## Résultat proposé

Un bouton **Missions Hermes** dans l’en-tête holographique actuel, ouvrant le panneau existant. Historique, états, résultats, provenance disponible et annulation uniquement. Le rendu conserve le texte du modèle, avec avertissement non vérifié ; les métadonnées absentes restent signalées comme telles. Aucun iframe, deuxième page Jarvis, admission, approbation, voix Hermes, Windows, modèle ou action physique.

Le panneau réutilise le client de connexion, le panneau et le formateur existants via une génération contrôlée (`scripts/prepare_embedded_panel.py`). Aucun changement des sources historiques de ces composants. Espaces et événements de session sont propres aux missions ; le sélecteur visuel et les fonctions audio ne sont pas modifiés. La connexion reste humaine, avec le code opérateur existant saisi au besoin ; aucun code ou secret n’est inclus dans les fichiers livrés au navigateur, ni conservé en localStorage.

## Chaîne d’autorisation

```text
Jarvis actuel (HTTPS, même origine)
  → /api/jarvis/hermes-panel/*, relais strict de la gateway
  → 127.0.0.1:8796, API privée sous jarvis-pilot
  → session humaine + rôle read/cancel + espace lié côté serveur
  → bridge existant 127.0.0.1:8797
  → registre et SQLite synthétiques existants
```

Le relais est sans clé de bridge, sans clé de modèle et sans identité affirmée par le navigateur. Il ne transmet que le cookie dédié, l’origine validée et les données de la requête autorisée. Aucune confiance dans un profil, un header de rôle/utilisateur ou un objectif libre. Le marqueur d’origine du relais n’est **pas** une authentification ; la session humaine est toujours vérifiée par le service privé.

Le service réutilise `sessionRegistry`, `experimentalHermes` et `bridgeClient`. Session `HttpOnly`, `SameSite=Strict`, `Secure` en HTTPS, cookie dédié `JarvisHermesSession` limité à `/api/jarvis/hermes-panel`. Durée 30 minutes, expiration et révocation de la politique contrôlées à chaque requête. Il s’agit du compte humain `pilot-operator` déjà existant, lié explicitement au laboratoire synthétique user ; aucun propriétaire personnel n’est attribué aux missions. Les contrôles de propriétaire restent ceux du bridge/SQLite (`phase3-synthetic`). Aucune donnée personnelle n’est accessible par ce raccordement.

L’exécution utilise l’identité OS `jarvis-pilot`. **Attention aux copies historiques des secrets :** l’installateur initial a conservé les originaux du laboratoire sous le compte user et copié leurs valeurs dans le nouvel état. Le simple changement d’UID ne prouve donc pas l’exclusivité actuelle des identifiants. Leurs valeurs privées n’ont pas été relues pour ce développement. Avant activation, une vérification administrateur et, si ces valeurs sont encore communes, une rotation du jeton bridge et du code humain sont nécessaires dans l’état privé root/jarvis-pilot ; les anciennes copies restent conservées mais deviennent inopérantes. Le nouveau code humain doit être remis par un canal privé à l’utilisateur, jamais inclus dans le patch ou un fichier lisible par le worker Codex. Le rôle et l’espace restent identiques, sans élargissement de permissions. Le relais n’importe ni backend Jarvis, ni worker Codex, ni fournisseur. Les limites et l’isolation réseau du service installé sont conservées. Le wrapper privé supprime la page et les assets du deuxième frontend ; seules les API internes existantes (compatibilité des contrôles de démarrage) et la nouvelle API restent disponibles sur loopback.

La liste, les détails et les résultats sont contrôlés avant appel au bridge ; une mission d’un autre propriétaire est refusée. Annulation : rôle dédié, origine exacte, objet JSON vide. Création, approbation et routes inconnues sont refusées même avec une session valide. Aucun replay ou fallback payant.

## Patch exact et fichiers

Le dossier `docs/hermes-embedded/` contient les diffs, les assets compilés, les manifestes et les résultats. La release complète de préparation reste dans `data/embedded-preparation/review-final/` ; elle se reconstruit avec le script, qui refuse les sources dérivées ou un dossier déjà existant.

| Cible | Modifications |
|---|---|
| Gateway `/home/user/gateway/server.js` | 3 insertions : import, construction du relais, branche avant `/api/jarvis/*`. Aucun remplacement du backend ou des fonctions existantes. |
| Gateway | Ajout `hermes-embedded-relay.mjs`, `hermes-embedded-contract.mjs`. |
| Frontend servi | `/home/user/gateway/public/jarvis/index.html` : deux balises ajoutées ; ajout `hermes-embedded.js`, `hermes-embedded.css`. |
| Source frontend | Même insertion et mêmes assets dans `/home/user/workspace/jarvis/public/`, pour éviter leur perte à une copie ultérieure. Aucun changement de backend. |
| Pilote `/opt/jarvis-hermes-pilot` | Une substitution de chemin du lanceur Node dans `memory_manager/phase6/interactive.py` ; ajout API/contrat/wrapper. Manifeste dérivé et inventaire de release mis à jour sur la copie uniquement. |
| Pilote, sécurité | Gardiens réseau et unité système conservés byte pour byte dans la release. Pas de changement de compte, quota, réseau ou pare-feu. |
| Configuration privée | Ajout de `embeddedPanel: {enabled: true, origin: ORIGINE_HTTPS_CONFIRMÉE}` à la configuration existante, sans afficher ou remplacer ses secrets. Empreinte calculée par l’administrateur sur place, jamais contenu copié dans Git. |

Le manifeste d’origine et les preuves historiques ne sont pas remplacés. Les empreintes des 40 fichiers de code installés ont été vérifiées en lecture seule : aucun écart. Aucune lecture de l’état privé `/var/lib` n’a été nécessaire.

## Flag et origine

Par défaut : `JARVIS_HERMES_PANEL` absent/off. Pour armer ultérieurement :

- `JARVIS_HERMES_PANEL=1` ;
- `JARVIS_HERMES_PANEL_ORIGIN=https://…` : origine exacte réellement utilisée, à confirmer ; `https://192.0.2.16:8788` est une proposition, pas une origine observée du navigateur de l’utilisateur ;
- `JARVIS_HERMES_PANEL_SWITCH=/chemin/privé/hermes-panel-switch.json`, fichier propriétaire gateway, 0600, non symlink, contenant seulement `{"enabled":false}` au premier chargement.

Le flag privé est lu sur les seules routes du panneau. Manquant, invalide ou non privé : refus. Le passage à false désactive immédiatement le relais sans redémarrer Jarvis. Aucun cookie ou code opérateur n’est placé dans ce fichier. Les origines HTTP LAN sont refusées ; les tests utilisent uniquement l’exception loopback locale. Aucun nouveau port LAN/public, certificat, firewall ou accès Windows.

## Compatibilité et limites réelles

`/ask`, backend hybride, Codex, Gemini, microphone, streaming, Home Assistant et boucle S9 restent inchangés dans le diff. Leurs handlers historiques ne reçoivent aucune session ou permission issue du panneau. Leur sécurité globale n’est **pas** réputée corrigée par ce patch : les lacunes anciennes restent hors de cette façade. Le confinement global du worker Codex historique n’est pas certifié par ce patch : s’il peut modifier les fichiers de la gateway/du frontend sous le même UID, il peut compromettre la connexion humaine malgré les ACL réseau. Ce patch ne copie pas de nouveau secret sous cet UID ; les copies historiques exigent la vérification/rotation décrite plus haut. Cette limite doit être acceptée pour le laboratoire synthétique read/cancel ou traitée avant une extension. Un XSS dans le frontend partagé reste un risque pour une session humaine ouverte ; la portée reste limitée au laboratoire read/cancel. Aucune publication automatique ou permission physique.

Les tests vérifient le passage inchangé d’une requête `/ask` vers un handler simulé, pas une conversation Gemini/Codex réelle. Aucun fournisseur réel n’a été invoqué. Les résultats affichés sont des événements de fixture synthétiques, pas de nouveaux résultats calculés par Hermes. Le navigateur mobile testé est Chromium (390 px), pas un iPhone/Safari physique. L’indisponibilité du service privé rend le panneau indisponible, sans empêcher le handler conversationnel simulé. L’état PC Gamer reste explicitement non mesuré et l’exécution désactivée ; ce patch n’active ni heartbeat ni worker Windows.

## Sauvegarde, installation et retour arrière proposés

1. **Avant accord :** vérifier les hashes de toutes les sources, du code installé, du HTML servi et de sa source. Les diffs doivent s’appliquer sans forçage. Tests isolés et restauration de copies prévus/réalisés dans `scripts/check_embedded_patch.py` ; aucun backup de production n’est prétendu déjà créé pour ce changement.
2. **Lot privé, accord root distinct :** arrêter uniquement le service pilote pendant une fenêtre approuvée ; sauvegarder release, unité et configuration privées ; snapshot SQLite + restauration séparée comparée ; conserver tous les originaux, backups en 0700/0600. Installer la copie dérivée et mettre à jour ses seuls manifestes/configuration. Vérifier sous root les identifiants hérités et renouveler ceux encore partagés avec le compte Codex : jeton bridge privé et code humain/humanHash/operator.token cohérents, sans imprimer de valeur, sous les permissions du compte applicatif. Conserver les anciennes sauvegardes mais ne plus accepter leurs anciens identifiants. Cette rotation doit être expressément autorisée ; aucun identifiant nouveau n’a été créé ici. Reprendre via le coordinateur `install-system-pilot.py --start-approved` déjà installé/préparé, conservant la barrière du cgroup définitif. L’unité, le compte et le réseau ne changent pas. Vérifier aussi l’API intégrée via session humaine et le header de relais fixe (sans afficher le code). Le frontend privé doit alors répondre 404.
3. **Lot gateway/frontend, accord distinct :** sauvegarde vérifiée des six fichiers/cibles gateway concernés (et des trois copies source frontend), des métadonnées de service et des flags existants. Refuser une cible nouvelle déjà présente ou un hash divergent. Poser relais/contrat/assets, appliquer les deux petites insertions et préparer le switch à false. Vérifier syntaxe Node 18 et hashes. Ne modifier aucun secret dans `.env`.
4. **Redémarrage contrôlé, autorisation explicite :** le code chargé exige un redémarrage de `codex-gateway.service`. Il interrompt les sessions vocales ouvertes et recharge la boucle S9 ; `S9_CONTROL_ENABLED=true` est déclaré dans sa configuration actuelle. Ce redémarrage ne peut donc pas être traité comme une opération sans effet sur les services/équipements. Il faut un créneau et une autorisation spécifiques, sans changer ses réglages pour contourner ce risque. Aucun redémarrage n’est autorisé ou exécuté ici.
5. **Acceptation flag false :** health, ressources UI, routage hybride historique et sessions usuelles ; panneau non accessible, pas d’appel bridge. Les contrôles de fonctions sensibles se font sans commande physique. Toute vérification réelle supplémentaire nécessitant un fournisseur reste soumise au budget/accord distinct.
6. **Activation limitée, accord sur le switch :** activer seulement read/cancel synthétique. Connexion humaine, liste, résultat existant, refus anonyme/hors espace/admission/approbation, origine TLS et cookies. Ni mission GPU ni essai vocal requis pour cette activation UI.
7. **Retour arrière immédiat :** switch false (effet immédiat, sans couper l’audio) ; aucun replay. Pour revenir aux octets initiaux, restaurer les fichiers sauvegardés et supprimer seulement les ajouts identifiés, puis redémarrage gateway à nouveau autorisé. Restaurer séparément release et paramètres privés sous root et vérifier leurs hashes avant reprise supervisée. Après une rotation de sécurité, conserver les identifiants frais : ne jamais réactiver automatiquement des secrets anciennement partagés avec le compte Codex. Conserver SQLite et ses événements, sans restaurer une vieille base sur des annulations plus récentes. Ne jamais démarrer l’ancienne unité utilisateur en secours automatique.

## Verdict

**GO laboratoire et revue du patch ; NO-GO activation à ce stade.** Les choix restant à approuver sont l’origine HTTPS exacte, la vérification/rotation des identifiants copiés historiquement et le lot privé sous root, le patch gateway/frontend et le créneau de redémarrage (audio/S9), puis l’ouverture du switch read/cancel. Aucun nouveau modèle, compte, import, service permanent ou pilote GPU nécessaire. La délégation vocale est seulement réservée dans l’architecture ; ses routes restent refusées.

## Résultats effectivement exécutés

- 20 tests mémoire historiques + test interactif existant + intégration embarquée : **22 réussis**.
- Dernier contrôle de l’intégration embarquée après finition du rendu : **réussi**, Chromium bureau 1440 px et mobile 390 px, vrai bridge/SQLite synthétique, arrêt/reprise de la copie.
- **42 assertions HTTP réussies**, dont refus, sessions, révocation, rôle lecture seule, mauvaise origine/Host et switch de coupure.
- Quatre patches appliqués sur copies et restauration vérifiée octet pour octet ; empreintes des artefacts et manifeste dérivé vérifiés. Syntaxe Node 18 validée ; le serveur est vérifié comme ESM sans l’importer/exécuter.
- Gateway PID 2033987 et pilote PID 2488260 inchangés ; aucun restart, modèle, import ou action physique. Détail et limites : `hermes-embedded/test-results.json`.

## Complément avant intervention

Origine désormais confirmée par l’utilisateur : `https://192.0.2.16:8788`. Le [préflight ciblé](JARVIS_2_HERMES_EMBEDDED_PREFLIGHT.md) précise la première lecture S9 sans commande, les conséquences du restart, la rotation et les deux accords R/G à obtenir. Le modèle de drop-in arme le transport avec un switch effectif false, afin d’éviter un second redémarrage pour une activation ultérieure autorisée. Rien n’est installé par ces préparatifs.
