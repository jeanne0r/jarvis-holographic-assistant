# Phase 6B — Audit du chemin hybride actif

Audit en lecture seule le 14 novembre 2026. Source des empreintes, moteur et PID :
[JARVIS_2_PHASE6B_ACTIVE_AUDIT.json](JARVIS_2_PHASE6B_ACTIVE_AUDIT.json).
Aucune conversation, clé ou donnée personnelle consultée. Aucun service modifié.

## Chemin réellement exécuté

La gateway `/home/user/gateway/server.js` importe directement
`/home/user/workspace/jarvis/backend.mjs`. Les ressources servies sont dans
`/home/user/gateway/public/jarvis`, distinct du worktree de développement.
Le moteur lu dans la configuration active est **hybrid**, Node **18.19.1**.
Le service est resté actif, PID **2033987** à l'observation.

1. `voice-router.js` consulte `/api/jarvis/voice/status` et charge `codex-voice.js`.
2. Ce dernier ouvre `/voice/session`, transcrit par `/voice/transcribe`, puis
   appelle `window.jarvisAsk(text,{channel:'voice',archive:{id,turn},signal})`.
3. `app.js` envoie `/api/jarvis/ask?space=…` avec question actuelle, fil récent,
   canal et identifiant d'archivage. Il affiche `answer`; la voix lit `speech`.
4. `backend.mjs` archive et appelle `ai.answer`; en mode hybrid,
   `hybrid-brain.mjs` fait classer Gemini/Codex. Les réponses publiques et les
   demandes locales suivent les branches existantes.
5. La transcription et la synthèse Google sont un transport vocal distinct.
   Le chemin Live natif `/live/session → /live/tool` ne prouve pas ce chemin.

## Authentification et permissions observées

L'audit initial a constaté la délégation `/api/jarvis/` avant le contrôle de la
clé gateway des autres routes. Le contrôle Origin du backend n'authentifie pas
une personne. `space` et les profils visuels sont des sélections, pas des preuves
d'identité. Les nouvelles identités ne sont pas encore déployées.

Le wrapper de phase 6 vérifiait déjà sessions serveur, expiration, Origin épinglée,
espaces et rôles. Cependant, son interdiction explicite de `/ask` bloquait le
mode hybrid une fois l'authentification activée. C'est un défaut de compatibilité
confirmé dans le code, corrigé dans le worktree en phase 6B.

Autre défaut corrigé : le premier 401 de `voice/status` empêchait tout chargement
vocal après connexion. Le chargeur retente sur un événement de session, une seule
fois chargé; aucune modification du traitement audio. Les profils autorisés sont
réappliqués et la bibliothèque rafraîchie après connexion, même Hermes désactivé.

## Worker Codex : frontière à conserver

`codex-worker.mjs` utilise `workspace-write`, réseau autorisé, recherche web,
`approval_policy=never`, outils MCP Jarvis et racine inscriptible
`/home/user/gateway/public/jarvis`. Le chemin de secours dans `ai.mjs` possède
également des permissions étendues. Ces capacités sont adaptées au fonctionnement
historique d'un assistant personnel privilégié; elles ne constituent pas un
confinement par utilisateur ni une autorisation Hermes.

La façade Hermes n'importe et n'appelle ni ce worker, ni `ai.answer`, ni ses
outils shell. Les instructions Hermes reconnues ou refusées quittent `/ask`
**avant** l'archivage serveur, le classificateur et tout worker. Une conversation
ordinaire conserve le chemin historique, avec son risque de privilèges existant.
Le rôle `conversation` doit donc être réservé à un humain de confiance autorisé
à utiliser ce chemin historique; ce n'est pas un compte multi-utilisateur confiné.
Aucun compte de modèle ou bridge ne reçoit ce rôle.

## Périmètre de compatibilité

| Fonction | État de laboratoire |
|---|---|
| `/ask` humain et aiguillage Gemini/Codex | Handler et routeur réels, fournisseurs simulés |
| Admission Hermes par `/ask` | Bridge HTTP et SQLite réels synthétiques; aucun worker Codex |
| Session, espace, expiration, Origin | Refus testés côté serveur |
| `/voice/session`, transcription et lecture | Routes permises au rôle voice; régression transport simulée |
| Chargement vocal après login | Test navigateur avec 401 initial et moteur hybrid |
| Médias navigateur via capabilities/run | Volume local testé; cibles physiques refusées |
| Live natif | Hors pilote; montage 6B refuse son activation |
| Carte mémoire | Exige un droit Commun explicite car l'ancien backend inclut Commun |
| Import/sync et développement legacy | Restent refusés par ce wrapper de laboratoire |
| Codex historique et ACL de son OS | Permissions existantes inchangées; confinement fort non démontré |

**Ne pas activer globalement `JARVIS_SERVER_AUTH=1` sur la production actuelle.**
Ce pilote n'atteste pas une compatibilité exhaustive de toutes les fonctions
historiques. La revue des fonctions administratives, de l'usage partagé et du
worker privilégié reste nécessaire avant un déploiement global.
