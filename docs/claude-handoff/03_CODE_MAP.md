# Cartographie : chemins absolus et précautions

`O` = présence observée pendant la passation ; `H` = installation/rôle historique référencé, contenu non relu. Les chemins privés ne donnent aucune autorisation d'en lire les secrets.

| Chemin | Niveau / rôle / précaution |
|---|---|
| `/home/user/workspace/jarvis` | O — dépôt principal `main`, HEAD2d40cc2 ; importé par gateway, donc potentiellement production |
| `/home/user/workspace/jarvis-2-memory` | O — worktree dédié, branche codex/jarvis-2-memory-20261113 ; code futur et documentation |
| `/home/user/gateway` | O — répertoire opérationnel **sans dépôt Git propre** ; ne pas confondre rollback Git et restauration de fichiers |
| `/home/user/gateway/server.js` | O — entrée active, relais Hermes et boucle S9 ; modification/restart sous accord séparé |
| `/home/user/workspace/jarvis/backend.mjs` | O — vrai backend importé, routes mémoire/voix/capacités ; ne pas tester par import aveugle (sync planifiée) |
| `/home/user/gateway/public/jarvis/` | O — frontend servi, hologramme/voix/missions ; pas le public du worktree de développement |
| `/home/user/gateway/public/jarvis/hermes-embedded.js` | O — panneau Big Boss, saisie, historique, résultat et confirmation |
| `/home/user/gateway/hermes-embedded-relay.mjs` | O — relais même origine vers service privé ; secrets jamais transmis au frontend |
| `/home/user/.config/systemd/user/codex-gateway.service` | O — unité gateway ; ne pas redémarrer pendant la prise de connaissance |
| `/opt/jarvis-hermes-pilot` | O — release privée root, JS + modulesPython ; le manifeste de déploiement contient63 entrées |
| `/var/lib/jarvis-hermes-pilot` | O — état privé700 UID jarvis-pilot ; SQLite/config/identités, ne pas copier dans Git |
| `/var/lib/jarvis-hermes-pilot/memory.sqlite` | H — SQLite synthétique canonique, pas ouverte pendant passation |
| `/opt/jarvis-hermes-supervisor` | O — code root/groupe superviseur750, inaccessible à user ; provisionnement partiel |
| `/etc/jarvis-hermes-supervisor` | O — configuration privée ; ne pas exporter config.json ni identités |
| `/var/lib/jarvis-hermes-supervisor` | O — état 700 UID dédié, HOME/SSH/receipts ; jamais copier un HOME personnel |
| `/etc/systemd/system/jarvis-hermes-pilot-system.service` | O — service privé loopback/BPF |
| `/etc/systemd/system/jarvis-hermes-supervisor.service` | O — superviseur non privilégié, actuellement failed |
| `/etc/systemd/system/jarvis-hermes-confinement.service` | O — attestation root indépendante, actuellement failed |
| `/var/backups/jarvis-hermes` | H — sauvegardes root ; chemins détaillés dans les scripts/résultats opérateur |
| `C:\JarvisHermesLab` | O via SSH — dossier natif Windows ; fichiers précis sous chemins des bindings H, ne pas les supposer interchangeables |

## Modules sous `/home/user/workspace/jarvis-2-memory/`

| Fichier ou répertoire absolu | Rôle et précaution |
|---|---|
| `/home/user/workspace/jarvis-2-memory/memory_manager/store.py`, `/home/user/workspace/jarvis-2-memory/memory_manager/schema.sql` | Source canonique, révisions, droits, migrations additives ; ne pas lancer contre base personnelle |
| `/home/user/workspace/jarvis-2-memory/memory_manager/api.py`, `/home/user/workspace/jarvis-2-memory/memory_manager/hermes_mcp.py`, `/home/user/workspace/jarvis-2-memory/memory_manager/mcp_utf8.py` | API mémoire, intégration MCP et frontière UTF-8 |
| `/home/user/workspace/jarvis-2-memory/memory_manager/missions.py`, `/home/user/workspace/jarvis-2-memory/memory_manager/skills.py`, `/home/user/workspace/jarvis-2-memory/memory_manager/consolidate.py`, `/home/user/workspace/jarvis-2-memory/memory_manager/indexer.py` | Missions, candidates, consolidation, index reconstructible |
| `/home/user/workspace/jarvis-2-memory/memory_manager/phase2/` | bridge.py/http_bridge.py, budgets, local_model.py, mcp.py, memory_tools.py ; contrats existants |
| `/home/user/workspace/jarvis-2-memory/memory_manager/phase3/` | Adaptateur runtime natif, quotas et MCP contrôlé |
| `/home/user/workspace/jarvis-2-memory/memory_manager/phase4/windows.py` | Cycle Windows/Jobs/tunnels/arrêt propriétaire ; empreintes strictes, aucune adoption de processus |
| `/home/user/workspace/jarvis-2-memory/memory_manager/phase5/` | Recherche hybride, embeddings/index expérimental et évaluations |
| `/home/user/workspace/jarvis-2-memory/memory_manager/phase5c/` | Préparation/validation sémantique et import borné ; données privées hors Git |
| `/home/user/workspace/jarvis-2-memory/memory_manager/phase6/demand_queue.py`, `/home/user/workspace/jarvis-2-memory/memory_manager/phase6/demand_service.py` | Ordonnancement sur registre existant, idempotence/leases/quarantaine |
| `/home/user/workspace/jarvis-2-memory/memory_manager/phase6/memory_audit.py` | Audit lecture seule, pas de consolidation/promotions automatiques |
| `/home/user/workspace/jarvis-2-memory/memory_manager/production/` | Connecteurs persistants préparés ; pas preuve d'un montage global actif |
| `/home/user/workspace/jarvis-2-memory/scripts/demand_supervisor.py` | Exécuteur orchestration fixe ; correctif 128 Kio fe589cc, dépendances épinglées |
| `/home/user/workspace/jarvis-2-memory/ops/demand/commission.py` | Installation/reprise **avec effets root et activation possible** ; pas une commande de découverte |
| `/home/user/workspace/jarvis-2-memory/ops/demand/*.service.in`, `/home/user/workspace/jarvis-2-memory/ops/demand/supervisor-egress.nft.in` | Modèles UID/réseau/probe indépendants ; pas d'installation pendant reprise documentaire |
| `/home/user/workspace/jarvis-2-memory/ops/demand/attest-confinement.py`, `/home/user/workspace/jarvis-2-memory/ops/demand/start-private-queue.py` | Preuve root / démarrage privé sous contrôles |
| `/home/user/workspace/jarvis-2-memory/ops/pilot-network/` | Installation/R/G, BPF, restauration, anciens essais bornés ; ne pas relancer les anciennes fenêtres |
| `/home/user/workspace/jarvis-2-memory/scripts/text_mission_window.py` | Validateur historique de provenance inchangé ; pas un outil à lancer pour lire un rapport |
| `/home/user/workspace/jarvis-2-memory/jarvis-session-auth.mjs`, `/home/user/workspace/jarvis-2-memory/hermes-human-mount.mjs` | Sessions communes et composition préparée ; SSO non activé |
| `/home/user/workspace/jarvis-2-memory/gateway-route-policy.mjs`, `/home/user/workspace/jarvis-2-memory/gateway-business.mjs`, `/home/user/workspace/jarvis-2-memory/gateway-production-entry.mjs` | Garde et adaptateurs futurs ; ne pas remplacer server.js globalement |
| `/home/user/workspace/jarvis-2-memory/codex-broker-client.mjs`, `/home/user/workspace/jarvis-2-memory/codex-tools-broker.mjs` | Séparation broker/exécutant préparée, pas confinement réel de toute production |
| `/home/user/workspace/jarvis-2-memory/s9-power-service.mjs`, `/home/user/workspace/jarvis-2-memory/s9-power-main.mjs` | Séparation future boucle S9 ; ne jamais démarrer en parallèle du contrôle actif |
| `/home/user/workspace/jarvis-2-memory/security/phase6d/`, `/home/user/workspace/jarvis-2-memory/security/production/` | Matrices, contrats, politiques et unités préparatoires |
| `/home/user/workspace/jarvis-2-memory/data/hermes-demand/deliverable/` | Paquet de livraison immuable ; références sources avant correctifs commissioning |
| `/home/user/workspace/jarvis-2-memory/docs/HERMES_ON_DEMAND_MANIFEST.json` | Empreintes et tests du paquet ; ne pas régénérer pour masquer une dérive |
| `/home/user/workspace/jarvis-2-memory/docs/HERMES_OPERATIONAL_RECONCILED_MANIFEST.json` | Réconciliation Windows antérieure sans changement de permissions |
| `/home/user/workspace/jarvis-2-memory/memory_manager/tests/`, `/home/user/workspace/jarvis-2-memory/memory_manager/phase*/test_*.py`, `/home/user/workspace/jarvis-2-memory/test_*.mjs` | Tests par portée ; ne pas exécuter un runner non inspecté contre services réels |

Tous les noms du tableau ont été contrôlés pour leur présence locale. L'installation Windows interne, les sauvegardes root et les bases ne sont pas recopiées. Les sources Hermes de référence se trouvent dans `/home/user/workspace/jarvis-2-hermes-reference` (présence observée), pas dans un nouveau clone à installer.
