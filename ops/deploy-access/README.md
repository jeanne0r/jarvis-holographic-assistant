# Accès de déploiement limité (VM103) — accord User du 18.11.2026

Clé SSH dédiée de jarvis-dev (192.0.2.165) vers le compte `jarvis-deploy` de la VM103.
La clé ne peut que : `put-bundle`, `pull`, `run <phase>` (liste fermée, mot de confirmation
transmis comme si on le tapait ; jamais YES=1), `status`, `journal pilot|supervisor [min]`,
`hash <fichiers Jarvis/Hermes>`. Tout le reste est refusé et journalisé (`journalctl -t jarvis-deploy`).

Hors périmètre (restent à User) : install, arm/disarm, real-reset, sources-config/-network,
rollback, reconcile --close, Windows, Home Assistant, Proxmox, autres VM, secrets, redémarrage gateway.

Limite honnête : déployer du code = l'exécuter. Un bundle poussé puis `run` fait tourner ce code
en root sur la VM103 (comme quand User lance sudo). Garde-fous : fast-forward seulement sur la
branche, historique git auditable, chaque action journalisée, retrait immédiat :
`sudo bash install.sh --remove`.
