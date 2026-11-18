# Pilote interactif privé — correction des deux blocages

Les sept différences sont retracées dans `pilot-interactive/manifest.json`, avec l'ancienne empreinte, le commit contenant exactement ces octets, l'empreinte actuelle et les commits explicatifs. Aucun fichier existant n'a été remplacé. Le manifeste P6-L et ses verdicts ne sont pas modifiés.

| Source conservée | Origine de l'écart |
|---|---|
| `jarvis-session-auth.mjs` | `eefa9a2`, `6bb7c4e` : handles de sessions, révocation, droits actualisés, portée du cookie |
| `hermes-bridge-client.mjs` | `520c2b6` : provenance canonique et transport borné du heartbeat |
| `jarvis-hermes-experimental.mjs` | `520c2b6` : métadonnées canoniques distinctes du texte du modèle |
| `phase6-gateway.mjs` | `eefa9a2` : historique indépendant de l'admission, topologie épinglée et révocation |
| `backend.mjs` | `6bb7c4e`, `7847655` : propriété des sessions vocales et origine du proxy privé ; **non importé** dans ce pilote |
| `public/index.html` | `6bb7c4e`, `520c2b6` : chargement auth indépendante et formateur canonique ; la page Jarvis complète n'est pas servie ici |
| `public/hermes-missions.js` | `eefa9a2`, `6bb7c4e`, `520c2b6` : auth découplée, historique, provenance, disponibilité et reprise prudente |

Le nouveau manifeste épingle 36 fichiers nécessaires, sans récupérer le backend général, le worker Codex ou un lanceur Windows. Toute divergence bloque le démarrage ; il faut une nouvelle revue, jamais recalculer les empreintes au démarrage pour accepter silencieusement du code modifié.

## Lanceur préparé

- `memory_manager.phase6.interactive` héberge le bridge existant, authentifié, sur `127.0.0.1:8797` et le panneau Node 18 sur `127.0.0.1:8796`.
- Réutilisation du panneau, de son client d'authentification et de son formateur de provenance actuels ; page d'accueil réduite aux seules missions synthétiques, sans scripts audio ou applications générales.
- À l'installation approuvée, copie cohérente de **la base P6-L2 existante**, jamais déplacement ou écrasement. Validation du propriétaire synthétique et des provenances ; sauvegarde et restauration sur fichier séparé vérifiées. Aucun accès aux bases personnelles.
- Compte applicatif `pilot-operator`, espace fixé côté serveur ; consultation, admission DoseLab et annulation uniquement. Pas d'approbation, outil physique, import, proposition libre ou route `/ask`.
- Aucun navigateur automatique dans le service. Aucun lancement de mission au démarrage. Aucun code de dispatch/SSH/Ollama/Hermes Windows. Les missions restent en file ; un worker supervisé nécessitera une activation distincte avec les gardiens GPU/Kryptex existants. Une mission ancienne n'est jamais rejouée.
- Une seule mission non terminale ; idempotence conservée. Les budgets existants restent à 240 secondes, 98 304 tokens, une tentative et 0 coût distant. La limite du futur exécuteur reste six appels ; aucun appel n'est possible dans ce service sans worker. Une admission supplémentaire est refusée (le bridge rend 409, la façade existante masque ce refus en 503).
- Pas de fenêtre de cinq minutes pour le service. Sessions humaines de 30 minutes ; justificatif d'opérateur renouvelable, initialement 30 jours, sans conséquence sur la durée du processus. Sa valeur reste dans `data/phase6/pilot-interactive/operator.token` en 0600, jamais imprimée.
- Unité utilisateur séparée, environnement vidé, chemins gateway/SSH/Codex/production rendus inaccessibles, écritures limitées à l'état du pilote, réseau loopback et plafond mémoire 384 Mio. Aucun changement d'allocation Proxmox. Modèle préparé et syntaxe systemd vérifiée ; confinement de l'unité réelle à vérifier lors de l'installation autorisée, sans retirer une protection en cas d'échec.
- Aucun `enable`, timer, redémarrage automatique ou lancement Windows permanent. La file reste durable après arrêt ; le redémarrage du service est manuel.

## Vérifications réalisées, sans installation

Un test d'intégration local utilise le vrai navigateur, les vrais serveurs Node/Python et une SQLite synthétique temporaire : démarrage sans admission automatique, connexion, création DoseLab, refus anonyme/hors espace/mission libre/deuxième mission/approbation, persistance après arrêt et redémarrage, annulation, révocation et zéro usage modèle. Les processus de test sont arrêtés.

La base P6-L2 réelle **synthétique** a aussi été copiée dans un répertoire temporaire, sauvegardée puis restaurée séparément : dumps SQLite identiques, permissions 0600, source inchangée. Les fichiers temporaires ont été supprimés. Copie/retrait du fichier d'unité vérifiés sur copie. `systemd-analyze --user verify` réussit sans diagnostic. Aucun service installé, aucun test GPU/Hermes et aucun appel payant. Résumé : `pilot-interactive/checks.json`.

## Activation proposée — accord préalable obligatoire

Depuis `/home/user/workspace/jarvis-2-memory`, après autorisation explicite :

```bash
python3 -m scripts.prepare_interactive_pilot --install-approved
```

Le script vérifie le manifeste et les ports libres, refuse tout état ou unité préexistant, prépare la copie privée et les sauvegardes, installe **uniquement** `jarvis-hermes-pilot.service` puis démarre cette unité. Il contrôle le health loopback. En échec, il arrête/retire cette seule unité, recharge le gestionnaire et conserve les données privées pour inspection ; aucun nouvel essai implicite et aucun changement de la gateway.

Accès prévu après activation : `http://127.0.0.1:8796/`, depuis le serveur ou avec un transfert SSH privé du même port. Aucun bind LAN, pare-feu, proxy public ou paramètre SSH modifié. Pour un autre appareil : `ssh -N -L 8796:127.0.0.1:8796 user@192.0.2.16`, avec vérification normale de la clé hôte, puis ouverture de l'URL loopback sur cet appareil. Aucun accès iPhone direct/HTTPS LAN n'est prétendu validé.

Arrêt et retrait, seulement sur accord :

```bash
systemctl --user stop jarvis-hermes-pilot.service
rm ~/.config/systemd/user/jarvis-hermes-pilot.service
systemctl --user daemon-reload
```

Conserver le répertoire privé, ses missions et sauvegardes ; aucune suppression de base. La gateway et la boucle S9 n'interviennent dans aucune de ces commandes.

**Verdict : deux blocages logiciels corrigés pour le panneau et la file durable. Installation prête à être autorisée, pas effectuée. Exécution de nouvelles missions Hermes volontairement non activée.** Les refus de sécurité ne seront pas assouplis pour obtenir un démarrage.

## Installation autorisée — 15 novembre 2026

L’unité a été installée et a passé le contrôle de disponibilité sur loopback, sans activation au démarrage. La gateway conserve son PID `2033987` et sa date de démarrage. Aucun contact Windows, mission créée ou appel modèle.

**Pilote arrêté par précaution, accès actuellement indisponible.** Le journal systemd signale un filtrage IP configuré dans une unité non root. Les droits actuels ne permettent pas de vérifier les programmes BPF effectifs ; aucune protection n’a été retirée. L’unité est conservée, inactive, et les deux ports sont fermés. Les sauvegardes et la restauration SQLite séparée sont intègres et identiques ; les données privées sont conservées. Le test d’authentification de cette installation n’a pas été poursuivi après cet arrêt ; les tests locaux antérieurs restent distincts.

Avant tout redémarrage, faire vérifier par un administrateur le filtrage effectif du cgroup du pilote. Toute correction de service ou de confinement nécessite une autorisation précise. Ne pas réexécuter l’installateur : il refuse volontairement l’état déjà existant. Preuve : `pilot-interactive/deployment.json`.

## Résolution définitive du blocage systemd/BPF

L’unité système `jarvis-hermes-pilot-system.service` est désormais installée, active, sous le compte non privilégié jarvis-pilot. Sa barrière de pré-démarrage a validé le confinement réseau dans son cgroup définitif. Le panneau et le bridge restent uniquement loopback (8796/8797), authentifiés, sans dispatch, mission automatique ou autostart. L’ancienne unité utilisateur reste arrêtée. Originaux conservés, copie sauvegardée/restaurée et tests d’accès réussis. Gateway PID/date inchangés. Preuve et portée exacte : `pilot-interactive/system-installation-result.json`.
