# Développer dans l'environnement existant

## Versions et accès

Observés : Node **18.19.1**, Python **3.12.3**, Git **2.43.0**, Proxmox 9.2.25. Ne pas introduire une dépendance Node 22 dans la gateway. Les modules principaux utilisent ESM `.mjs`, Python et SQLite ; il n'y a pas de package.json racine à utiliser comme unique entrée des tests.

Windows historique validé : CPython 3.14.10, uv 0.13.8 et94paquets verrouillés pour Hermes natif ; Ollama et Python 3.10 existants conservés. Ces versions n'ont pas été réinventoriées pendant la passation. PinHermes `4959268e312a21a361f248e49030d5f5df3984d5` ; ne pas installer latest.

SSH diagnostic Windows et root Proxmox ont fonctionné pour les **métadonnées en lecture seule** pendant cette passation. Cela ne donne pas un accès automatique à Claude. Sudo non interactif refusé sur VM103 ; la procédure administrative précédente passait par le terminal humain. Ne pas contourner sudo via Proxmox, agentVM, nouvelles clés ou permissions.

## Commandes d'entrée sans modification

```bash
cd /home/user/workspace/jarvis-2-memory
git status --short
git branch --show-current
git worktree list
git log -12 --oneline
git diff --stat
systemctl --user show codex-gateway.service -p ActiveState -p MainPID
systemctl show jarvis-hermes-pilot-system.service jarvis-hermes-supervisor.service jarvis-hermes-confinement.service -p Id -p ActiveState -p MainPID -p ExecMainStatus
ss -ltn
```

Ne pas utiliser `systemctl show` sans sélection de propriétés, ni afficher `Environment`, `.env`, `/proc/*/environ`, arguments complets ou logs bruts : ils peuvent contenir des secrets. Ne pas importer backend.mjs comme test : il planifie une synchronisation.

## Git et sources

Conserver le worktree isolé existant ; vérifier les modifications de l'utilisateur avant toute édition. Dernier correctif fonctionnel prépassation `fe589cc`. Ne pas rebaser/réinitialiser les historiques. Une branche `codex/…` peut servir à un chantier distinct, sans modifier le worktree principal actif ; ne pas recréer tous les composants.

Le principal `main` à2d40cc2 a des changements locaux signalés dans [le manifeste](09_HANDOFF_MANIFEST.md). Ne pas les écraser ou les incorporer automatiquement. La gateway n'a pas de dépôt Git propre : les patches sont livrés avec préimages et SHA256.

## Tests sûrs ciblés

Commande repassée pour cette passation, sans fournisseur ou service réel :

```bash
cd /home/user/workspace/jarvis-2-memory
python3 -B -m unittest memory_manager.phase6.test_commission memory_manager.phase6.test_supervisor_security memory_manager.phase6.test_queue_install memory_manager.phase6.test_demand -q
```

Résultat **42 tests OK**. Les répertoires temporaires et identités de ces tests sont des fixtures. La correction128 Kio est testée sur un paquet et une configuration synthétique complète ; ce n'est pas un démarrage réel du superviseur.

Pour les changements mémoire : `python3 -B -m unittest discover -s memory_manager/tests -q` (lire les tests avant d'étendre le périmètre). Les tests `test_hermes_embedded.mjs`, `test_hermes_single_session.mjs`, `test_phase6d_security.mjs`, `test_phase6d_final.mjs`, `test_production_bindings.mjs` documentent les contrats ; inspecter leurs prérequis avant exécution, certains modes utilisent navigateur/serveurs temporaires.

Éviter de relancer par défaut `evaluate_memory.py` avec des options historiques, les scripts `pilot_*`, `run-worker-window.py`, `commission.py` ou un script `ops/` : distinguer un runner isolé d'un outil opérationnel. Aucun nouvel essai C1/P6-L1/P6-L2 n'est nécessaire.

Avant commit : tests proportionnés, `git diff --check`, revue des fichiers ajoutés, contrôle qu'aucune fixture privée/secret/preuve historique n'est modifiée. Stage explicite, jamais `git add .` dans ce worktree avec preuves non suivies.

## Déploiement et reprise ciblée

Le script existant `ops/demand/commission.py` ne doit pas être exécuté à la découverte. Sa reprise `--resume-directory-fix-approved` est liée au backup exact du commissionnement partiel ; elle vérifie préimages/identités/cfg/SQL et sauvegarde l'ancien lecteur avant remplacement atomique. Elle peut ensuite armer l'exécution et démarrer le superviseur, donc **peut entraîner Windows/GPU pour une mission utilisateur en attente**. Aucun agent ne doit la présenter comme un diagnostic inoffensif.

Avant reprise : confronter le checkpoint, les fichiers privés et l'état des missions à la procédure, sans afficher les secrets ; confirmer les autorisations actuelles, les quotas et les gardes ; ne créer aucune demande à la place de l'humain. Si une précondition diffère, suspendre plutôt que régénérer des empreintes aveuglément.

Sauvegarder code/config et SQLite via son mécanisme existant, restaurer SQLite sur copie, comparer intégrité/contenus. Ne pas cp une base en cours d'écriture sans protocole SQLite adapté. Le rollback code/config conserve la base actuelle et les tables additives. Un résultat incertain reste bloquant, pas effacé par restauration.

Ne jamais redémarrer gateway, service privé, Windows ou équipement sans périmètre approuvé. Redémarrer la gateway touche voix/Codex et sa boucle S9, même si le changement ne vise que le panneau. Un éventuel retour arrière exige les mêmes précontrôles, pas une boucle de redémarrages.
