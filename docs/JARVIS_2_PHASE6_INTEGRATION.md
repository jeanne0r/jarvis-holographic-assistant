# Phase 6 — Intégration de laboratoire et patch proposé

## Flux préparé

Deux entrées partagent le même bridge : panneau Jarvis et outil mission_hermes
ajouté conditionnellement aux déclarations de Gemini Live natif. L'outil rend
l'admission/id puis la conversation reprend ; status/result sont consultables à
la demande. Le contrôleur et Windows communiquent directement, pas par une chaîne
de messages Gemini. Aucun algorithme audio ou client public/live.js modifié.

La première mission est un **template synthétique fixe DoseLab**. Ni objectif
arbitraire, contexte de conversation, historique privé ni profil/permissions
fournis par le modèle ne partent vers Hermes. Extension à d'autres projets après
accord sur les données et le périmètre, pas un champ libre implicite.

La façade réutilise admission/idempotence, liste canonique bornée à 50, états,
pages SSE, annulation, résultats et approbations du bridge. Les approbations HTTP
passent par une identité machine humaine distincte ; aucun outil Gemini/Hermes
n'est capable d'approuver ou de publier une compétence.

Le worker de phase 6 enveloppe celui de phase 4 : disponibilité/GPU/minage,
début d'exécution durable, zéro rejeu des runs ambigus. Sur résultat terminal,
il enregistre une expérience **inferred** idempotente avec référence à l'événement
canonique et SHA de sortie. Il ne convertit pas les citations en faits vérifiés.
Aucun daemon de worker, cron, service Windows ou sortie physique activé ici.

## État réellement démontré

Le serveur HTTP de laboratoire appelle les vrais modules session, façade,
Live et bridge, ainsi que le backend réel sur la route docs, avec bases temporaires.
Google est simulé pour créer la session Live ; Hermes est un faux runtime déterministe.
Le callback worker conserve une expérience une seule fois malgré plusieurs ticks.
Les références synthétiques traversent retour modèle/bridge/outil puis interface.
Le rendu UI est testé sur l'interface existante dans un navigateur réel avec API
simulées. Cela n'est **pas** un nouvel essai matériel Hermes/RTX depuis Jarvis.
C1 reste clos et ses preuves sont conservées, sans relance.

## Écart avec la voix de production

Le moteur actif audité est **hybrid**, dont le routeur vocal appelle /ask via
codex-voice.js. Le parcours testé ici est **Live natif**, déjà présent mais pas
sélectionné en production. Le patch ne change ni core-engine.json ni voice-router.js.
Il ne démontre donc pas encore une délégation vocale depuis le chemin actif.

Le profil sécurisé initial refuse /ask à cause du worker Codex historique et de
ses permissions larges. **Ne pas activer ce profil sur Jarvis actif** sous prétexte
que les tests Live sont verts. Le panneau peut être démontré d'abord dans une
copie de préproduction. Choix avant intégration vocale réelle : adapter et confiner
le chemin hybride en conservant son routage, ou autoriser explicitement un pilote
Live natif en préproduction. Aucun changement de moteur implicite.

## Patch exact et préconditions

Voir `phase6/patch-manifest.json` : **16 fichiers de cible production** avec avant/après
SHA256 et indicateur de fichier nouveau. Le diff `phase6/jarvis-phase6-production.patch`
est construit depuis les fichiers réellement actifs et les sources préparées.
Le dry-run puis l'application **dans une copie temporaire locale** reconstituent
exactement les octets attendus. Aucun patch n'a été appliqué à une cible réelle.

Les fichiers Python du bridge/worker demeurent dans le worktree contrôleur isolé,
pas copiés dans le processus Node ou Windows. Liste distincte dans le manifeste.
Pas de migration réelle. API/worker futurs doivent utiliser une base synthétique
nommée et des identités contrôlées, jamais brain.sqlite de production.

Le patch gateway est une importation du mount et la substitution du seul appel
handleJarvis ; tous les autres routeurs restent identiques. Les imports de Live
n'ajoutent l'outil que si le service autorisé est disponible. Le backend résout
son store depuis son propre dossier ; JARVIS_BACKGROUND_SYNC=0 permet de l'importer
sans synchroniser les conversations personnelles dans les tests. Sa valeur par
défaut conserve le comportement existant, aucune modification de prod à ce sujet.

## Sauvegarde avant un éventuel déploiement autorisé

1. Vérifier le SHA du patch approuvé et toutes les empreintes avant du manifeste ;
   arrêter si un fichier a changé ou un nouveau fichier existe déjà.
2. Sauvegarder les anciens fichiers avec mode/propriétaire/empreinte et vérifier
   les copies. Conserver les fichiers nouveaux séparément pour un retour arrière,
   ne jamais écraser une base ou collection. Aucune copie de mémoire historique.
3. Sauvegarder séparément configuration privée et paramètres de service existants,
   sans les copier dans Git ni les imprimer. Prévoir leur protection à l'identique.
4. Tester le patch dans une copie de préproduction avec la version Node active,
   interfaces locales et données synthétiques ; examen du diff exact et de la
   compatibilité hybrid avant demande d'application au serveur actif.

Ces opérations sur les cibles actives ne sont **pas autorisées par le développement**.
Le générateur ne fait que lire les sources et appliquer dans un dossier temporaire.

## Activation à prévoir après résolution de l'écart hybride

Par défaut : JARVIS_SERVER_AUTH absent/0, JARVIS_HERMES_ENABLED absent/0, switch false.
Aucun secret/compte/fichier privé réel provisionné par cette préparation.

- Configurer une origine privée HTTPS exacte et des comptes humains distincts ;
  sessions expirantes, vrais espaces/rôles et credentials bridge minimaux.
- JARVIS_SERVER_AUTH=1 exige JARVIS_PHASE6_CONFIG et JARVIS_PHASE6_AUDIT privés.
- Armer JARVIS_HERMES_ENABLED=1 exige JARVIS_PHASE6_SWITCH privé ; le switch JSON
  `{"enabled":false}` garde les missions inactives. Ne pas modifier les rôles
  du modèle pour compenser une route refusée.
- L'opérateur pourra ensuite remplacer atomiquement le switch par
  `{"enabled":true}` sur un périmètre explicitement approuvé. Il est relu par
  requête ; aucun redémarrage nécessaire pour le désarmer.
- Le serveur bridge doit être disponible en loopback. Son API peut accepter les
  missions pendant que Windows est arrêté ; seul le worker indépendant décide
  du départ selon disponibilité, télémétrie fraîche et budget.
- N'activer ni démarrage automatique Windows ni fournisseur distant payant.

## Retour arrière et autorisations regroupées

| Bloc à approuver séparément | Effets/machine | Arrêt et restauration |
|---|---|---|
| P6-L : laboratoire réel | Nouveau lot synthétique dans une copie Jarvis de préproduction ; contrôleur local borné ; un démarrage temporaire Hermes/Ollama Windows et une mission, proposé 5 min / 6 appels / 98 304 tokens / 0 CHF, gardiens existants | Arrêter seuls Jobs/tunnels possédés, fermer la fenêtre ; laisser mission/résultat et journaux ; pas de nouvelle tentative automatique |
| P6-I : identités et configuration | Fichiers privés de comptes humains, credentials bridge/approbateur, origine, audit et switch sur Proxmox ; politique nominative à revoir | Désarmer le switch, révoquer les credentials créés ; aucune modification de données sources ou de compte Windows |
| P6-G : patch actif et interruption planifiée | Après revue de ce diff ET résolution hybrid ; copies des 16 fichiers puis redémarrage contrôlé codex-gateway.service, impact possible sur les sessions Jarvis/Codex en cours | Accord distinct sur cette interruption ; restauration vérifiée des fichiers/configs précédents et second redémarrage si nécessaire |

Aucun de ces blocs n'est exécuté ici. Aucun choix P6-L ne vaut changement du moteur
actif. Le premier pilote réel privilégiera le panneau sur une copie isolée et
l'outil Live sera testé dans un environnement native Live explicitement choisi,
pas en détournant le mode hybride de production.

Retour arrière applicatif immédiat après activation approuvée : switch false ;
les nouveaux accès Hermes sont refusés, la session Jarvis reste authentifiée.
Les runs déjà partis ne sont pas arrêtés par le switch : annulation via le bridge
et procédure de fermeture des seuls Jobs du laboratoire. Conserver SQLite et les
preuves. Ne jamais mettre JARVIS_SERVER_AUTH=0 comme simple coupe-circuit Hermes.
Une suppression complète du patch/restauration de gateway est une opération
supplémentaire avec interruption à approuver, pas une étape silencieuse.

## Identité du patch pour revue

SHA256 : `f376da2ff66ef50a3b267f1fab8ebd081754e602cc8705c1baf31075ef905f17`.

Fichiers cibles exacts :

- `/home/user/workspace/jarvis/backend.mjs`
- `/home/user/workspace/jarvis/live.mjs`
- `/home/user/workspace/jarvis/knowledge.mjs`
- `/home/user/workspace/jarvis/voice-memory.mjs`
- `/home/user/workspace/jarvis/voice-memory.py`
- `/home/user/workspace/jarvis/store.py`
- `/home/user/workspace/jarvis/phase6-gateway.mjs` (nouveau)
- `/home/user/workspace/jarvis/jarvis-session-auth.mjs` (nouveau)
- `/home/user/workspace/jarvis/hermes-server-auth.mjs` (nouveau)
- `/home/user/workspace/jarvis/hermes-voice-tools.mjs` (nouveau)
- `/home/user/workspace/jarvis/hermes-bridge-client.mjs` (nouveau)
- `/home/user/workspace/jarvis/jarvis-hermes-experimental.mjs` (nouveau)
- `/home/user/gateway/public/jarvis/index.html`
- `/home/user/gateway/public/jarvis/hermes-missions.js` (nouveau)
- `/home/user/gateway/public/jarvis/hermes-missions.css` (nouveau)
- `/home/user/gateway/server.js`
