# Reprise de Jarvis 2.0

## Où l'on est : `jarvis-dev`, environnement de dev isolé

- Machine : VM `jarvis-dev` (Proxmox VMID 9100, 192.0.2.165), Debian 13, Python 3.13, Node 20 (Debian).
- Ce dépôt est un **clone** depuis `~/jarvis.bundle` (remote `origin` = le bundle). Branche de travail actuelle : `claude/reprise-20261116`, issue de `codex/jarvis-2-memory-20261113`.
- **Aucune production ici** : pas de gateway, de worktree `~/workspace/jarvis`, de `/opt|/etc|/var/lib/jarvis-*`, d'unités systemd Jarvis, de comptes `jarvis-pilot`/superviseur, ni d'accès à Windows/GPU. `data/` est ignoré par Git : le paquet `data/hermes-demand/deliverable/` n'est pas présent (3 tests de `test_commission` en dépendent).
- Libre dans cette VM : coder, tester, installer des paquets de dev.

## La production est ailleurs (VM103, hors de portée)

- Prod : VM103 `192.0.2.16`, gateway `/home/user/gateway/server.js` (Node 18, mode `hybrid`), interface unique `https://192.0.2.16:8788/jarvis/`.
- Les docs `docs/claude-handoff/` décrivent la VM103 : leurs états « observés » (PID, ports, services) **ne sont pas vérifiables d'ici**. Les traiter comme historiques/opérateur.
- Aucune action sur la VM103, Windows (192.0.2.96), Proxmox, HA ou CT205 depuis cette VM. User exécute lui-même les commandes prod ; Claude les présente avant, avec leurs effets. Les commandes de reprise root (`ops/demand/commission.py`) ne sont pas des diagnostics : elles peuvent armer l'exécution Windows/GPU.
- Superviseur à la demande : installé partiellement en prod, **pas opérationnel** au 16 novembre 2026. Correctif `fe589cc` (config 128 Kio) préparé, application en prod non confirmée. Ne pas modifier `scripts/demand_supervisor.py` sans prévenir : son hash est épinglé par `commission.py`.

## Lecture de reprise

`docs/claude-handoff/00_START_HERE.md`, puis états et règles de sécurité. (`/home/user/workspace/_memory/README.md` et `/home/user/workspace/AGENTS.md` n'existent pas sur cette VM.)

## Règles qui restent valables partout

- Aucun secret ni contenu personnel à lire/exporter : pas de `.env`, identités, cookies, clés privées ou bases personnelles. Données synthétiques seulement.
- SQLite canonique, Qdrant reconstructible ; jamais de prune de `jarvis_memory_v1`. Pas de commande physique, publication automatique, import privé implicite ni API payante : budget 0 CHF.
- Invariant : le modèle n'accède jamais directement à un actionneur (HA, équipements, shell).
- Ne pas masquer un refus, réinitialiser une preuve consommée, rejouer une mission incertaine ou réécrire un ancien `passed=false`.
- Les autorisations historiques ne valent pas permission générale pour un nouvel agent.
- Tests ciblés superviseur : `python3 -B -m unittest memory_manager.phase6.test_commission memory_manager.phase6.test_supervisor_security memory_manager.phase6.test_queue_install memory_manager.phase6.test_demand`.
