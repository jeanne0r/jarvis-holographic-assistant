# Passation Codex → Claude Code

Vérification : **16 novembre 2026, UTC**. Dossier autonome de reprise ; aucune installation Claude effectuée. Périmètre documentaire seulement, sans changement de services ni de configuration.

## Lire dans cet ordre

1. [État actuel](02_CURRENT_STATE.md) : ce qui tourne réellement et la panne de commissionnement.
2. [Sécurité](05_SECURITY_RULES.md) : frontières et interdictions.
3. [Architecture](01_ARCHITECTURE.md), [cartographie](03_CODE_MAP.md).
4. [Problèmes](08_KNOWN_ISSUES.md), [développement](06_DEVELOPMENT_GUIDE.md), [suite](07_ROADMAP.md).
5. [Historique](04_HISTORY_DECISIONS.md), [manifeste](09_HANDOFF_MANIFEST.md).

Prompt directement réutilisable : [FIRST_PROMPT_FOR_CLAUDE.md](FIRST_PROMPT_FOR_CLAUDE.md).

## Résumé de reprise

Jarvis est fonctionnel sur sa gateway existante, en mode **hybrid**, avec son frontend holographique unique et son panneau Big Boss/Missions Hermes. Les cycles Hermes natif Windows → Qwen/RTX → MCP → mémoire ont déjà réussi sur données synthétiques. Ne pas les reconstruire ni les répéter pour la passation.

L'enregistrement persistant de missions a été installé et validé par l'opérateur. Son dernier résultat administratif indique `accepting=true`, `executionEnabled=false`. Le superviseur accord 3 a ensuite été **provisionné partiellement**, mais son démarrage a échoué. Observation actuelle : service privé actif, superviseur et attestation en échec ; aucun processus superviseur. L'autorisation n'est donc pas une preuve de mise en service.

Le dernier diagnostic root fourni par l'utilisateur refuse la lecture de configuration. Le correctif `fe589cc` relève uniquement le plafond du fichier principal de configuration de 16 à 128 Kio : la carte des 213 empreintes dépasse à elle seule 22 Ko. Les lecteurs d'identifiants conservent 16 Kio et leurs permissions. **42 tests ciblés repassés pendant la passation ; application root du correctif non confirmée.**

Prochain travail : vérifier le checkpoint exact et présenter la reprise ciblée existante, sans nouvelle installation générale, sans mission créée par l'agent et sans activation GPU implicite. Les secrets/configurations root sont volontairement inaccessibles au compte de développement ; les états privés actuels ne sont pas déduits d'un ancien rapport.

## Origine des preuves

« Observé » signifie interrogé pendant cette passation ; « historique » renvoie à un rapport/commit existant ; « opérateur » à un résultat administratif fourni dans la conversation. Les trois niveaux ne sont pas interchangeables. Aucune conversation personnelle ni base historique n'a été ouverte pour ce dossier.

Le rapport `HERMES_ON_DEMAND.md` décrit une **livraison avant installation**. Ses mentions « non installé » ne sont pas l'état actuel : suivre la chronologie de [02_CURRENT_STATE.md](02_CURRENT_STATE.md).
