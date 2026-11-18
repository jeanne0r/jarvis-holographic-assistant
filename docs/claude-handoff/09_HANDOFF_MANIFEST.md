# Manifeste de passation

Date de vérification : **2026-11-16 UTC**. Sources : code Git, fichiers opérationnels non secrets, propriétés systemd sélectionnées, HTTPS local, SSH métadonnées Windows/Proxmox/CT205, rapports de tests existants et résultats opérateur cités. Aucun secret ou contenu personnel lu pour ce dossier.

## Contenu versionné

- [00_START_HERE.md](00_START_HERE.md)
- [01_ARCHITECTURE.md](01_ARCHITECTURE.md)
- [02_CURRENT_STATE.md](02_CURRENT_STATE.md)
- [03_CODE_MAP.md](03_CODE_MAP.md)
- [04_HISTORY_DECISIONS.md](04_HISTORY_DECISIONS.md)
- [05_SECURITY_RULES.md](05_SECURITY_RULES.md)
- [06_DEVELOPMENT_GUIDE.md](06_DEVELOPMENT_GUIDE.md)
- [07_ROADMAP.md](07_ROADMAP.md)
- [08_KNOWN_ISSUES.md](08_KNOWN_ISSUES.md)
- ce manifeste
- [FIRST_PROMPT_FOR_CLAUDE.md](FIRST_PROMPT_FOR_CLAUDE.md)
- [CLAUDE.md](../../CLAUDE.md) à la racine du worktree

Le commit de passation est le commit documentaire ajoutant ces fichiers ; son identifiant est remis dans la réponse finale et retrouvable avec `git log -1 --format='%h %s' -- docs/claude-handoff`. Il ne contient aucun changement de code/service et ne modifie pas les preuves.

## État Git avant passation

- Dépôt commun : `/home/user/workspace/jarvis/.git`.
- Principal : `/home/user/workspace/jarvis`, `main`, **2d40cc2**.
- Développement : `/home/user/workspace/jarvis-2-memory`, `codex/jarvis-2-memory-20261113`, **fe589cc** avant documentation.
- Autres worktrees sous `jarvis/data/evolutions/` : branches `codex/jarvis-evolution-702953ee-5589-4cdb-99c5-30c4c67a062a` à 741eed5 et `codex/jarvis-evolution-76bdf8d8-6c6e-4a29-babc-cd9f9f0966a2` à f21cac8. Non inspectés intérieurement, ne pas nettoyer.
- Principal modifié : `public/index.html` ; non suivis : `semantic/qdrant-release.json`, `semantic/requirements.lock`, `semantic/web-ui/dist-qdrant.zip`, `semantic/web-ui/extracted/`, `semantic/web-ui/release.json`. Ne pas les embarquer, réinitialiser ou supprimer.
- Développement : deux preuves non suivies préexistantes `docs/HERMES_OPERATIONAL_WINDOW_20261115T200950Z-29e0e47e.json` et `docs/HERMES_OPERATIONAL_WINDOW_20261115T214641Z-0f2a81f1.json`. Conservées telles quelles, non ajoutées au commit de passation.

## Empreintes observées des fichiers actifs (SHA256)

| Fichier absolu | SHA256 |
|---|---|
| `/home/user/gateway/server.js` | `b6e95e20db96b1074ca8ddc5adb460ba916d5f06ba34f1152868b604c88cf9bf` |
| `/home/user/workspace/jarvis/backend.mjs` | `d605e09029a9f1949d67dd1cc2689c1cc78d7e66ccdb710be3e8ddb93fe50c2c` |
| `/home/user/gateway/hermes-embedded-relay.mjs` | `dbe9f1917fc73c6ef0ffa7a5d717bbc1a91d6d216b945b5de2c331ba45422d54` |
| `/home/user/gateway/public/jarvis/hermes-embedded.js` | `da3d4290d64c5c044fc269a465f3e46c15b8d4a27e11b4076d3aca19b9ede588` |

Le JS téléchargé en HTTPS donne la même empreinte que le fichier frontend. HTML servi : SHA256 `db4cca2d3b8127d0bf5128ec6d273af280d673e2f76dfc0739dd443bcf2f6a1f`, 25 760 octets. Ces constats ne valident pas toutes les routes ni tous les clients.

## Manifestes à préserver

- [HERMES_ON_DEMAND_MANIFEST.json](../HERMES_ON_DEMAND_MANIFEST.json) : livraison eb17c0c ; paquet immuable `data/hermes-demand/deliverable/`.
- SHA256 du manifeste de paquet épinglé par commission.py : `0b96327267a67ea05437342626a16428896be94a48a3b877230feb714927154e`.
- [HERMES_OPERATIONAL_RECONCILED_MANIFEST.json](../HERMES_OPERATIONAL_RECONCILED_MANIFEST.json), [HERMES_OPERATIONAL_WINDOWS_BINDINGS.json](../HERMES_OPERATIONAL_WINDOWS_BINDINGS.json).
- Ancien exécuteur : `e33e873273eb5e53fb0dca6a10899f70100557a42d7a8e48e44a27642a95379f` ; correctif source fe589cc : `359ce68a93afce63ada3ce7cce57c63191a138705ef886e06a2049ac55461033`.
- `ops/pilot-network/install-demand-queue.py` épinglé `7902ff2367bc5c3fb9249a11a56f3ae6d5c9e403bbee9b96988cfd48724e726c`.
- Le paquet historique n'est pas régénéré pour inclure silencieusement les correctifs du commissionnement : commission.py valide explicitement les versions précédentes et nouvelles admises.

## Références historiques structurantes

[Phase 4 réelle](../JARVIS_2_PHASE4_REPORT.md), [phase 5 clôture](../JARVIS_2_PHASE5_FINAL_REPORT.md), [P6-L1](../JARVIS_2_PHASE6B_P6_L1_RESULTS.md), [P6-L2](../JARVIS_2_PHASE6B_P6_L2_RESULTS.md), [décision production](../JARVIS_2_PHASE6_PRODUCTION_DECISION.md), [SSO](../JARVIS_2_LOT_B_SSO.md), [analyse des citations](../HERMES_TEXT_CITATION_ANALYSIS.md), [livraison à la demande](../HERMES_ON_DEMAND.md).

## Qualité et portée

42 tests Python ciblés repassés : OK. Vérifications Git, liens, chemins, commits, empreintes actives, distinction historique/actuel et diff documentaire réalisées avant commit. Recherche de secrets et revue du contenu : aucun secret, conversation, base, modèle ou binaire ajouté. Cette revue n'est pas un audit de toutes les données du dépôt ; elle couvre les nouveaux documents.

Aucun restart, service, permission, pare-feu, mission, modèle ou accès personnel nouveau. Les contrôles BPF réels actuels sous root ne sont pas relancés ; les attestations restent historiques et devront être fraîches lors d'une reprise autorisée.
