# Essai compétence — préparation du 14 novembre 2026

Statut : développement local ; aucune nouvelle fenêtre réelle autorisée/exécutée.
La première mission mémoire native validée ne sera pas rejouée.

## État vérifié et diagnostic

Lecture seule PVE : VM102 jarvis-lab arrêtée, 4096 Mio, balloon=0, onboot=0,
tag codex-phase3-20261114t074643z. VM103 maximum4096, minimum balloon absent ;
VM201 maximum2048/minimum1024 ; shares absents sur les deux. Aucun gardien
phase3 chargé. Ces observations ne prouvent pas une capacité RAM disponible future.
L'installation Hermes et le pare-feu vivant seront revérifiés au prochain démarrage.

La tentative a1f8092b-f067-44a7-b499-f9f4fb167a5b / run_8a90b1e88cfc41fa8cce2771814e8253
reste paused/cancel_requested : ne jamais la réadmettre ni restaurer son HOME.
La preuve NATIVE_SKILL_REAL_2 contient quatre inférences locales, 17603 tokens,
puis Private endpoint unavailable lorsque la fenêtre matérielle expire.
Elle contient les outils annoncés, pas leurs arguments ni leurs résultats.
On ne peut donc pas attribuer les refus à une confusion memory_id/révision.
L'ancien objectif ne précisait pas ce point et les catégories de mission
omettaient memory.propose : deux incohérences corrigées, sans preuve qu'elles
expliquent les refus réels. TIME_WAIT et la contrainte native64000 ont des
causes distinctes déjà identifiées ; les correctifs existants sont conservés.

Après accord de démarrage, avant toute nouvelle mission : conserver les journaux
systemd et sauvegarder par SQLite backup les bases de sessions du HOME
hermes-home-skill. Identifier la session du run concerné dans les métadonnées
API natives, puis lire messages(session_id, role, tool_call_id, tool_calls,
tool_name, content) dans une copie ouverte mode=ro. Relier chaque argument à sa
réponse d'outil et aux identifiants canoniques synthétiques. Ne pas exporter de
jetons ou de contenu brut dans Git/chat. Publier uniquement causes démontrées,
statuts et formes de schéma ; garder les refus génériques comme indéterminés.
Si les traces ne sont pas persistées, noter cette limite ; les nouveaux refus
MCP produiront CAPABILITY_DENIED, ARGUMENT_SCHEMA_REJECTED ou
MEMORY_DENIED_OR_UNAVAILABLE. Le dernier ne distingue pas un refus ACL d'une
panne de transport ; ne pas en déduire une cause plus précise.

## Correctifs préparés

- Schéma de compétence détaillé dans MCP et validé indépendamment dans le registre.
- Outils annoncés soumis aux catégories de mission ; noms exacts, aucun suffixe ambigu.
- Réponse du modèle : quatre appels outils maximum par réponse, outils annoncés
  uniquement, arguments validés avec les schémas du serveur, sans faire confiance
  au schéma transmis par le client. Les sorties rejetées restent comptabilisées.
- Évaluation fixe persistée dans la colonne existante evaluation ; aucun DDL.
- jarvis_skill_get lit la version canonique avec sources, état candidate,
  évaluation et validité actuelle des sources ; execution_authorized=false.
- Chaque démarrage du scénario utilise un HOME natif neuf créé exclusivement.
  Cela empêche l'auto-reprise Hermes d'une ancienne mission ambiguë ; les anciens
  HOME et traces sont conservés. Le second démarrage relit la même mémoire SQLite.
- Aucun outil de publication ni rôle reviewer pour Hermes. Réussir les tests
  n'entraîne aucune publication. Le scénario vérifie le refus explicite.

## Fenêtre proposée : 30 minutes maximum

L'installation étant déjà faite, réserver 15 minutes minimum après diagnostic
pour lancer le scénario, dont 7 minutes minimum avant la seconde mission.
Si ce temps n'est plus disponible, arrêter proprement et proposer une nouvelle
fenêtre ; ne pas prolonger le gardien ni lancer une mission à l'échéance.
La vérification du temps restant est un contrôle opérateur avant admission ;
le gardien indépendant impose toujours l'arrêt final, même en cas de déconnexion.

1. Sauvegardes fraîches vérifiées des configurations103/201, reprise explicite
   du gardien connu via --reuse-lab, arrêt indépendant1800s et ExecStopPost.
   Revalider les marges, récupérer la RAM uniquement après accord détaillé ci-dessous.
2. Démarrer uniquement VM102 existante, vérifier UID1001, commit Hermes épinglé,
   Python installé, confinement systemd, règles nftables et refus réseau effectifs.
   Refaire le rapport boot_id/hash ; un rapport de l'ancien démarrage est refusé.
3. Diagnostiquer l'ancienne tentative ; sauvegarder la mémoire synthétique par
   SQLite backup, integrity_check, SHA256 et essai de réouverture.
4. Copier uniquement les correctifs du worktree dans VM102 ; comparer les profils.
   Aucun pip/installation ni téléchargement de modèle. Préserver les anciennes traces.
5. Démarrer temporairement Ollama loopback Windows et tunnels privés existants.
   Vérifier digest Qwen4B, absence de minage actif, télémétrie fraîche, VRAM libre.
6. Exécuter le pilote existant avec --native-hermes --skill-only, modèle
   qwen3.5:4b et digest d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04,
   vers un nouveau fichier de preuve. Le scénario prépare deux missions neuves :
   création candidate puis consultation après arrêt/redémarrage natif dans un HOME neuf.
   Conserver les événements, causes des refus, évaluations et empreinte retournée.
7. Critères : appel réel skill_propose, lien stable vers expérience confirmée,
   évaluation fixe réussie, active_skills=0, publication agent refusée ; après
   redémarrage natif, appel réel skill_get et même fingerprint dans la réponse.
   Le redémarrage VM complet et la sémantique Qdrant ne sont pas prouvés par cet essai.
8. Annuler uniquement les nouvelles missions si nécessaire, arrêter leur unité,
   fermer les tunnels possédés et Ollama temporaire, contrôler le retour VRAM.
   Gardien : arrêt VM102, restauration byte-à-byte des configurations103/201 et
   allocations4/2Gio, vérification SHA256, santé gateway et connectivité Tailscale.

Limites : 180s, six inférences et 98304 tokens locaux par mission ; deux missions,
soit au plus12 appels et196608 tokens. Contexte64000 réel, sortie768, concurrence1,
MemoryMax2G, CPUQuota100%, TasksMax128, RuntimeMaxSec300 par runtime.
Aucune dépense distante, aucun fournisseur de secours. Les tests fixes couvrent
uniquement une procédure déclarative de fraîcheur/débit sur données synthétiques ;
ils ne constituent pas un banc général de compétences techniques.

## Commande de scénario, uniquement après A/B et contrôles

Depuis le worktree isolé, vers un chemin de preuve encore inexistant :

```bash
python3 scripts/pilot_existing_ollama.py --approved --native-hermes --skill-only --no-thinking \
  --model qwen3.5:4b \
  --digest d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04 \
  --output docs/JARVIS_2_PHASE3_SKILL_RETRY_REAL_1.json
```

Le pilote transmet le script versionné ops/start-ollama-pilot.ps1 par SSH
PowerShell, démarre son processus temporaire et vérifie son identité avant de
l'arrêter. Aucun de ces lancements n'a été exécuté pendant cette préparation.
Le gardien PVE doit avoir été réarmé séparément, avant la commande :
prepare --reuse-lab /mnt/hdd/jarvis-phase3/ram-held-20261114T074643Z,
puis unité systemd1800s avec watch/ExecStopPost cleanup, puis apply sur le
nouveau dossier. Jamais de réutilisation du marqueur d'approbation expiré.

## Autorisations à donner explicitement

**A — Proxmox, fenêtre maximum30min** : sauvegardes et gardien actualisés ;
VM103 cible2816Mio, maximum4096 inchangé, minimum balloon temporaire2816/shares0 ;
VM201 cible1024Mio, maximum2048/minimum1024 inchangés, shares0 temporaire.
Pas de redémarrage de ces VM, mais éviction de cache et ralentissements possibles
sur Codex/gateway et Tailscale. Marges : hôte>=5Gio avant boot102, puis>=1Gio,
VM103>=1Gio disponible, VM201>=512Mio, mesures fraîches ; sinon abandon.
Démarrage de VM102 existante4Gio, copie des correctifs et renouvellement du
pare-feu uniquement dans le laboratoire. Arrêt gracieux102 puis forcé si elle ne
répond pas ; restauration exacte103/201 en fin de fenêtre ou sur seuil franchi.
Aucune installation, autre VM/CT ni allocation permanente.

**B — PC Windows + contrôleur, même fenêtre** : lancement temporaire de l'Ollama
existant en loopback, modèle Qwen4B déjà installé, tunnels SSH privés et les deux
missions synthétiques ci-dessus. Environ6,9Gio de VRAM totale observée précédemment,
jusqu'à328W carte mesurés ; valeurs futures à mesurer. Ne jamais arrêter Kryptex :
si minage, VRAM insuffisante ou charge incompatible, suspendre/abandonner l'essai.
Arrêter seulement les processus/tunnels créés et possédés par ce pilote.
Aucun port public, pare-feu Windows modifié ou modèle téléchargé.

**C — CT205/Qdrant** : NON inclus dans A/B. Voir le plan séparé de raccordement.
Aucune intervention ni écriture sans validation spécifique après inventaire et
sauvegardes vérifiées. Production Gemini/HA/gateway inchangée, budget distant0CHF.

## État après accord et tentative

Le « Oui go » a autorisé A/B pour une fenêtre. Elle a été engagée puis close
après refus d'admission RAM, sans démarrage de VM102 ni Ollama. Le plan logiciel
reste prêt mais n'a pas été exécuté matériellement. Ne pas réutiliser les anciens
marqueurs : toute nouvelle fenêtre doit être fraîche et explicitement autorisée.
Résultat et restauration : JARVIS_2_PHASE3_SKILL_ADMISSION_REAL.json.
