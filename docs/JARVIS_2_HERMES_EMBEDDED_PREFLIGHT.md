# Préconditions avant intervention — complément au commit 50fb561

Préparation uniquement. Aucun service arrêté, aucune rotation, sauvegarde de production, commande d’équipement ou installation effectuée. Aucun test Hermes/GPU ou campagne de tests relancée.

## Origine confirmée

L’utilisateur confirme `https://192.0.2.16:8788/jarvis/`. L’origine à épingler côté relais et service est donc **`https://192.0.2.16:8788`**, sans chemin ni slash final. Une connexion cliente HTTPS à cette adresse a également été observée ; cette connexion seule n’aurait pas prouvé le Host. Le certificat existant inclut l’IP 192.0.2.16 dans ses SAN. Cela ne remplace pas la confiance du certificat sur chaque appareil. Aucun certificat, réseau, DNS ou pare-feu à changer pour le patch.

Les empreintes du serveur gateway, du HTML servi et du manifeste de la release pilote installée correspondent encore aux entrées de la revue 50fb561. Pas de nouveau diff fonctionnel ; le modèle de drop-in préparé fixe l’origine confirmée et arme seulement le transport. Le switch privé reste false, ce qui garde l’intégration effectivement désactivée, sans nécessiter un second redémarrage pour son activation ultérieure autorisée.

## Vérification et rotation préparées — à autoriser sous root

Périmètre strict : comparer, sans les afficher ni persister leurs empreintes, les champs d’accès connus de ces seuls emplacements :

- Origine historique : `data/phase6/pilot-interactive/config.json` et `operator.token` dans le worktree.
- État actif privé : `/var/lib/jarvis-hermes-pilot/config.json` et `operator.token`.

Vérifier en mémoire si les bridgeToken sont identiques, si le code humain est partagé et si son SHA-256 correspond au humanHash actif. Rapporter uniquement des booléens. Aucun inventaire global des disques et aucune lecture de conversations ou mémoire personnelle.

Prévoir des identifiants frais indépendants pour le bridge et l’opérateur dans l’état actif, sans toucher aux copies historiques conservées. Mettre à jour de façon cohérente `bridgeToken`, `humanHash`, `expiresAt` et le fichier `operator.token`, après sauvegarde, sous le même propriétaire jarvis-pilot et les mêmes permissions privées. Redémarrer le seul pilote par le coordinateur supervisé ; ses deux couches utilisent alors la nouvelle configuration. Les anciennes sessions sont invalidées par le redémarrage et les anciens identifiants ne doivent plus être acceptés. Aucune validation par affichage des valeurs ; le nouveau code humain est remis uniquement via le terminal privé de l’administrateur, pas en chat, Git ou fichier sous l’UID Codex. Aucun secret dans la gateway ou le frontend. Les données synthétiques et leurs propriétaires ne changent pas.

L’actualisation du code isolé ajoute `embeddedPanel={enabled:true,origin:"https://192.0.2.16:8788"}`. Cela ouvre seulement l’API privée protégée ; le relais public reste coupé par son switch. Le lot conserve compte, unité, gardien BPF, quotas, ports loopback et SQLite. Aucune mission créée ou exécutée. La page du deuxième frontend disparaît dans la release préparée.

## Conséquences exactes du redémarrage gateway sur S9

Constats de code : `server.js:700–724`, `2018–2029`. Configuration déclarée : contrôle activé, période 5 000 ms, entité `input_number.s9_power_target`, limites 800–1 420 W. Aucun équipement ou service Home Assistant interrogé pour ces constats.

- Le timer S9 est dans le processus gateway. Un restart interrompt la surveillance pendant l’arrêt et le démarrage ; il n’est pas un service indépendant.
- `s9LastRequestedPower`, `s9LastAppliedPower` et `s9ApplyingPower` sont uniquement en mémoire, réinitialisés au lancement. Une seule boucle est démarrée, par l’écoute HTTP ; l’écoute HTTPS n’en ajoute pas une deuxième.
- La première **lecture HA valide** au nouveau lancement mémorise la consigne puis retourne : **aucune commande S9 à cette première lecture**, même si la consigne a changé pendant l’arrêt. Il n’y a pas de comparaison avec l’état réellement appliqué du mineur ni de rattrapage automatique.
- Ensuite, chaque changement de consigne observé déclenche la mutation historique `updateAutotuning(... apply:true)`, bornée aux limites configurées. Il n’est donc pas possible de promettre zéro commande future tout en laissant fonctionner cette boucle inchangée.
- L’endpoint de lecture existant `/api/s9/control` ne publie pas `s9ApplyingPower` : il ne permet pas de démontrer un drainage. Une requête HA/S9 déjà engagée peut être interrompue au restart ; une commande distante déjà reçue ne peut pas être annulée par l’arrêt local. Aucun drainage S9 de SIGTERM n’est défini dans le serveur ; `KillMode=control-group` s’applique. Ne pas supposer qu’un restart annule une action distante ni rejouer une consigne pour « réparer ».
- Les connexions vocales et autres requêtes/runs enfants peuvent être coupées. Fenêtre sans voix ni run Codex en cours, avec consigne stable et sans changement d’automatisation programmé pendant l’intervention à confirmer avant accord. Aucun changement des réglages S9/HA, aucun arrêt du mineur, aucune commande manuelle ou test physique dans le lot.

Si une absence absolue de commande physique pendant la fenêtre est exigée malgré un changement externe de consigne, le redémarrage doit rester bloqué : aucune protection/automatisation ne sera désactivée pour contourner cette contrainte.

## Sauvegardes et retour arrière préparés

Contrôle de capacité ciblé : environ 1,38 Gio disponibles sur le système de fichiers de la VM (96 % occupé). Les sauvegardes doivent porter sur les seuls fichiers du lot et l’état synthétique, pas sur tout gateway/data ou les historiques. Recontrôler sous root leur taille effective et la marge disponible avant écriture ; en cas de marge insuffisante, arrêter sans purge ni extension de disque implicite.

Avant le lot root : sauvegarde horodatée privée 0700 sous `/var/backups/jarvis-hermes/` de la release, configuration, justificatif opérateur et unité ; fichiers secrets 0600, jamais vers le worktree/Git. Après arrêt du pilote : snapshot SQLite, contrôle d’intégrité et restauration dans **un fichier distinct** avec comparaison logique. Aucun écrasement de la base active, suppression de sauvegarde ou transfert hors machine. Le pilote ne contient que le laboratoire synthétique ; aucune mémoire historique/Qdrant/CT205 concernée.

Avant le lot gateway : sauvegarde privée des seuls fichiers modifiés ou nouveaux de la liste 50fb561, avec leur existence initiale, permissions et SHA-256 ; sauvegarde du drop-in/flag s’ils existent. Ne pas recopier `.env` : ses secrets et réglages ne sont pas modifiés. Le patch s’applique seulement si les empreintes d’entrée sont toujours identiques. La simulation de restauration sur copie est déjà validée, pas à répéter comme un pilote.

Retour arrière immédiat : switch false (il reste déjà false pendant l’installation). Si nécessaire, restaurer les octets et métadonnées gateway sauvegardés, supprimer seulement les ajouts du lot et faire un second restart explicitement couvert par l’accord de maintenance ; aucune boucle de réessais. Côté pilote, revenir à la release antérieure en conservant les identifiants frais : ne pas réactiver les secrets anciennement partagés. Garder la SQLite la plus récente et ses annulations, sans restauration automatique d’une vieille base. L’ancienne unité utilisateur ne sert pas de secours automatique.

## Autorisations distinctes à demander

**R — Lot privé root.** Comparaison des seuls accès désignés, sauvegarde/restauration vérifiée synthétique, arrêt du seul pilote, rotation des accès privés, installation de la release exacte 50fb561 et du profil à l’origine confirmée, puis reprise supervisée sous l’identité existante avec contrôles BPF, auth/ACL et ancien identifiant refusé. Aucun nouveau compte, service, port ou worker. Le switch gateway reste false.

**G — Gateway/frontend et fenêtre de restart.** Sauvegarde, pose du patch exact (relais, contrat, assets et HTML servi/source), ajout du drop-in d’armement et switch false, restart de `codex-gateway.service` en fenêtre approuvée avec acceptation explicite du risque d’interruption d’une requête S9 engagée et des conséquences audio ci-dessus. Sans cette acceptation, le restart reste bloqué ; aucune désactivation d’automatisation n’est implicite. Vérifications de santé, interface, mode hybrid et des routes existantes sans appel payant ni commande physique. Le retour arrière d’urgence peut nécessiter un second restart ; pas de répétition automatique.

**Activation exclue de R/G.** Après les vérifications de fonctionnement normal de Jarvis, présenter le résultat et obtenir l’accord séparé avant de passer le switch à true. Seulement historique/résultats/annulation synthétiques : aucune création, mission libre, voix Hermes ou GPU. En cas d’écart d’empreinte, d’échec de confinement ou d’état S9 incertain pendant la fenêtre, ne pas forcer le démarrage et signaler le blocage.
