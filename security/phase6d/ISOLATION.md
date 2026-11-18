# Contrat de séparation OS — modèles de revue, non installés

Aucune de ces identités n'existe du seul fait de ce document. Aucun service ne doit être démarré depuis ces modèles. Ne pas leur attribuer les secrets du compte `user`.

| Processus | Identité OS proposée | Écritures | Réseau indispensable | Secrets accessibles |
|---|---|---|---|---|
| Gateway | jarvis-gateway | son journal et sessions ; pas les dépôts du worker | navigateur LAN/Tailscale ; fournisseurs vocaux actuels via sortie contrôlée | identité bridge bornée, voix existante selon accord |
| Bridge/Memory API | jarvis-memory | SQLite et journaux propres | loopback authentifié seulement | ses identités API ; pas les secrets HA/Google/Codex |
| Contrôleur missions | jarvis-controller | état de contrôle restreint via API | bridge + tunnel SSH privé Windows | identité worker et clé SSH bornée ; pas de shell exposé au modèle |
| Exécutant Codex | jarvis-code-exec | worktree de mission jetable | aucune sortie directe ; éventuel proxy API approuvé distinct | aucun secret gateway/HA/mémoire |
| Hermes Windows | compte laboratoire existant | dossiers laboratoire autorisés | Ollama loopback + MCP via tunnel authentifié | identité outils restreinte ; aucun secret de production |

L'actuel worker Codex est une bibliothèque du processus de la gateway avec même UID/HOME et des chemins absolus. Une unité systemd ajoutée à côté ne sépare pas magiquement ce worker : il faut sortir l'exécution vers un broker distinct et supprimer le lancement direct de shell dans le processus gateway. Tant que ce chemin existe et que les outils n'imposent pas une identité/ACL fiable, les permissions `conversation` et `runs.create` ne sont pas suffisantes pour autoriser le service en production.

Les modèles `.service.in` sont des restrictions à examiner, sans installation ni activation. `PrivateNetwork=yes` coupe aussi les fournisseurs Codex : ce profil peut exécuter des outils déterministes locaux, pas le CLI distant tel quel. Un proxy approuvé et un protocole limité seront nécessaires pour Codex. Aucun contournement via réseau hôte, shell gateway ou identifiant maître n'est prévu.

L'API mémoire garde SQLite canonique et n'a pas besoin de recevoir les clés Google, de Qdrant historique ou de Home Assistant. L'indexeur futur aura une identité et une collection expérimentale séparées. Aucune migration de données réelles n'est incluse ici.

Les contrôles réseau systemd dépendent de l'hôte et de ses possibilités de filtrage. Ils ne sont pas présentés comme testés sur les services actifs. Les chemins de release, propriétaires et règles LAN/Tailscale doivent être approuvés avant création de comptes. Les sécurités physiques restent indépendantes des agents.
