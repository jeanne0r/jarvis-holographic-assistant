# Lot R autorisé — exécution administrateur en attente

## État

Autorisation utilisateur reçue pour R uniquement. Aucun redémarrage, rotation, sauvegarde administrative ou remplacement effectué depuis la session Codex : `sudo` exige une authentification interactive. Le code préparé ne confère aucun privilège supplémentaire. G et l'activation du switch ne sont pas autorisés.

Contrôles en lecture seule : gateway active PID 2033987, pilote système actif PID 2488260, environ 1,37 Gio disponibles sur `/` (96 % occupé). Le script recalcule la capacité nécessaire avant toute écriture ; ces observations ne remplacent pas ses contrôles root au moment de l'exécution.

## Commande à exécuter dans le terminal administrateur

```bash
sudo python3 -B /home/user/workspace/jarvis-2-memory/ops/pilot-network/deploy-private-embedded.py --lot-r-approved
```

Le résultat JSON ne contient aucun identifiant secret. Ne pas transmettre le contenu de `operator.token` dans le chat. La remise du nouveau code s'effectue exclusivement dans le terminal administrateur privé, après résultat `passed=true` :

```bash
sudo cat /var/lib/jarvis-hermes-pilot/operator.token
```

Le fichier actif reste sous le compte applicatif, en 0600, dans un dossier 0700, inaccessible à l'UID Codex. Aucun code n'est copié vers le worktree ni fourni au frontend par configuration. Le code humain expire après 30 jours ; la rotation invalide les anciens identifiants et le redémarrage les anciennes sessions.

## Périmètre de l'exécutable

Sources exactes de la revue 50fb561 et préconditions a5a5940. Manifeste épinglé : `d0ceb86f8e813928b72b8f7182fd650f7fe1de11ee9656a1e585d087a0cf00c9`. Coordinateur BPF existant épinglé : `dfb3a9e45734c8714837472274d9e3f19fe57e069a2f36529e8db2cbc8e7faa6`.

SHA-256 du nouveau lanceur `ops/pilot-network/deploy-private-embedded.py` : `b19e6274c9f316d6217593cb324f286c69a51857238a8f1b2636d709b42bcbf6`.

1. Vérifier les empreintes du code installé, du candidat et des entrées gateway, l'unité existante, les permissions privées, l'ancien pilote utilisateur arrêté et le switch effectivement désactivé. Comparer uniquement les deux couples d'accès explicitement désignés dans le préflight ; aucun inventaire de secrets.
2. Vérifier l'espace requis avec une réserve de 256 Mio, sans purge. Créer une sauvegarde root 0700 sous `/var/backups/jarvis-hermes/R-*` ; arrêter seulement le pilote système. Vérifier le périmètre synthétique avant copie de son état.
3. Sauvegarder configuration, accès privés, unité et release. Créer un snapshot SQLite et sa restauration dans un fichier distinct, vérifier intégrité et égalité logique, sans remplacer la SQLite active.
4. Poser le code candidat vérifié, conserver exactement l'unité et les gardiens, renouveler séparément les deux accès privés. Conserver quotas, ports loopback, données et interdiction de dispatch. Ajouter uniquement le profil embarqué à l'origine HTTPS confirmée.
5. Reprendre le seul pilote par le coordinateur existant : preuve BPF dans son cgroup final, témoins réseau avant/après, loopback permis et non-loopback refusé. Aucun démarrage non supervisé de secours.
6. Vérifier accès anciens rejetés, nouvelle authentification, cookie sécurisé, historique autorisé, autre espace refusé, admission et approbations interdites, ancienne page autonome absente. Aucun test d'annulation réel : ce lot doit laisser la SQLite identique, et l'annulation est déjà testée sur copie.
7. Vérifier la SQLite inchangée, les fichiers historiques d'accès intacts, les nouveaux secrets illisibles par l'UID Codex, les entrées gateway/PID inchangés et le switch toujours désactivé. Écrire uniquement des résultats non secrets dans les fichiers privés root `lot-R-result.json` et `result.json` de sauvegarde.

Le script ne crée ni compte ni unité et n'appelle pas `daemon-reload`. Aucun fichier gateway, switch ou réglage S9 n'est écrit. Aucun contact HA, Windows, GPU, fournisseur ou équipement.

## Arrêt et retour arrière

Une précondition échouée interdit l'installation. Après arrêt initial, tout échec laisse le pilote arrêté et les sauvegardes conservées ; aucun réessai ou retrait de protection automatique. Un marqueur d'exécution empêche une seconde rotation aveugle. Un échec exige lecture du résultat privé et diagnostic avant nouvelle intervention.

Le retour de code utilise `R-*/release` avec vérification des empreintes, conserve les identifiants frais et la SQLite la plus récente ; il ne réactive jamais les identifiants historiquement partagés. L'ancien profil compatible reste dans la configuration fraîche, dont seul `embeddedPanel` est ajouté. La reprise doit toujours passer par le coordinateur BPF. Aucune restauration automatique d'une ancienne SQLite ou ancienne unité utilisateur.

## Vérification locale limitée

`python3 -B -m unittest memory_manager.phase6.test_lot_r -v` : **5 tests hors ligne réussis**. Couverture : refus sans root avant opérations, renouvellement indépendant préservant quotas/topologie, écriture privée et refus de symlinks, snapshot/restauration sans écrasement, switch et arbres refusés en cas d'entrée dangereuse. Aucun essai matériel, aucun service lancé. Les vérifications root de bout en bout restent en attente de la commande administrateur ci-dessus ; ne pas les déclarer réussies à partir de ces tests.

## Lot G préparé, non lancé

Après un résultat R réussi, appliquer exclusivement le patch déjà revu dans `docs/hermes-embedded/manifest.json` : fichiers et empreintes exacts, sauvegarde privée des seuls fichiers concernés avec métadonnées et existence initiale, sans copie de `.env` ni des historiques. Utiliser les patchs et modèles existants ; pas de nouveau patch fonctionnel.

Préconditions G : accord séparé pour pose et restart de `codex-gateway.service`, fenêtre sans voix/run Codex, consigne S9 stable, acceptation explicite du risque de requête S9 déjà engagée et du non-rattrapage d'un changement pendant l'arrêt. Le préflight détaille ces risques. L'accord doit couvrir aussi un éventuel second restart pour restauration des octets sauvegardés ; aucune commande physique de vérification.

Installer le drop-in d'armement à l'origine confirmée et le switch **false**, puis vérifier santé locale, interface et compatibilité hybrid sans appel IA payant ni équipement. Tant que ces vérifications ne sont pas terminées, le panneau reste effectivement coupé. Une activation ultérieure historique/résultats/annulation seulement exige l'accord distinct prévu ; aucune admission, voix Hermes ou mission GPU n'est incluse.

Statut : **R en attente d'authentification administrateur ; G en attente d'autorisation ; activation exclue**.
