# Archive de l'étude RAM interrompue — remplacée par la phase4 Windows

Ces travaux locaux sont conservés conformément à la décision de changement
d'architecture. Aucun redimensionnement ni démarrage de VM102 n'a été exécuté.
Les scénarios2/3Gio et l'observateur mémoire sont des outils préparatoires non
déployés ; ils ne constituent pas une autorisation et ne sont plus la stratégie active.

L'historique RRD Proxmox a été lu en MAX, pas le RSS propre à Hermes. Les compteurs
natifs RSS/OOM du premier runtime ne sont pas présents dans les rapports conservés.
La définition installée de memhost est memory.current moins memory.stat[file]
pour le cgroup QEMU ; aucune conclusion de pic RSS Hermes n'en découle.
Le JSON RAM_SIZING_REAL contient uniquement les observations en lecture seule.
Les9 tests synthétiques ajoutés passent avec les40 tests de préparation existants.
Aucun de ces scripts n'a modifié les allocations, balloon, shares ou services.

La suite active est JARVIS_2_PHASE4_WINDOWS_PLAN.md. VM102 reste arrêtée,
son disque et ses données sont préservés comme référence et retour arrière.
