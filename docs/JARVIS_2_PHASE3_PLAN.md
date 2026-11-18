# Phase 3 — protocole réel et prochain pilote

## État des autorisations

A (Ollama temporaire), B (qwen3.5:4b) et C (nouvelle VM Hermes isolée) ont été
accordés. La réduction RAM initiale a échoué et a été annulée. L'exclusion
temporaire de l'auto-ballooning des deux VM a ensuite été autorisée pour une
fenêtre de 30 minutes. Cette fenêtre est **terminée** ; aucun prolongement implicite.
D (CT205/embeddings/Qdrant) et raccordement gateway restent non autorisés.

## Ce qui a été exécuté

1. Image Ubuntu officielle téléchargée sur HDD Proxmox, SHA256 vérifié :
   [SHA256SUMS Noble](https://cloud-images.ubuntu.com/noble/current/SHA256SUMS),
   noble-server-cloudimg-amd64.img, empreinte
   04e8f2461a16a44e78a370284471f29616cdd9baf1893df25807b71f985b6c94.
2. Préparation de sauvegardes des VM103/201, lancement d'un gardien indépendant
   via unité systemd transitoire sur PVE, puis shares=0 et cibles 2816/1024 Mio.
   Le script gardien et ExecStopPost restaurent les paramètres ; RuntimeMaxSec=1800.
3. Contrôle frais d'au moins 5 Gio disponibles avant création et avant démarrage.
   VM102 : jarvis-lab, 4 Gio fixes, 2 vCPU, disque 24 Gio sur hdd, onboot=0,
   tag codex-phase3-20261114t074643z, IP241 après inventaire et trois sondes ARP.
4. Instantané preinstall. Copie du code et source Hermes épinglé, installation
   Ubuntu des dépendances et uv sync contrôlé. La préparation cloud-init a
   effectué une mise à jour de cette nouvelle VM uniquement.
5. Compte hermeslab sans sudo, sources en lecture seule, nftables dans cette
   VM seulement. Identité SSH vérifiée par QEMU Guest Agent avant l'agent.
6. Tunnel contrôleur → Windows Ollama loopback ; contrôleur → VM102 avec forwards
   privés 8792/11436 vers mémoire/relais et 8643 vers API Hermes. Aucun port public.
7. Missions synthétiques, collecte des traces natives, budget et télémétrie GPU.
8. À l'échéance : arrêt VM102, restauration exacte des configurations 103/201,
   arrêt d'Ollama et des tunnels. Sources, disques, traces et preuves conservés.

## Paramètres actuels des essais

Mémoire : contexte 4096, extraction structurée ; corpus comparatif 21 cas.
Hermes : contexte **64000 réel**, think=false, keep_alive=0, température 0, seed7,
sortie 768, six appels maximum, 180 s par mission, quota local 98304, coût distant0.
Le compte réserve 64000 avant chaque appel et règle l'usage réel. Si une réserve
ne tient plus dans le solde, l'appel est refusé ; aucun fallback ou retry payant.

Les anciens profils 8192/16384 ne satisfont pas le minimum du runtime épinglé.
La VRAM 10 Gio a effectivement servi le 4B au contexte 64000 : pic total 6862 Mio.
Cette preuve porte sur un petit nombre de requêtes, pas une garantie pour toute
mission ou tout remplissage du contexte. Observer toute évolution de charge/minage.

## Commandes et code

- ops/phase3-held-ram.py : prepare/watch/apply/cleanup approuvés sur PVE ; source
  déployée sous /mnt/hdd/jarvis-phase3/ops-held-20261114T074631Z.
- Sauvegardes : /mnt/hdd/jarvis-phase3/ram-held-20261114T074643Z, root-only.
- ops/phase3-install-hermes.sh : installé sur la nouvelle VM, ne pas réinstaller.
- ops/phase3-isolate-lab.sh : règles de cette VM et permissions ; refuse une
  table existante. Les règles ne sont pas présumées persistantes au redémarrage.
- ops/phase3-hermes-run.py : lanceur sous compte sans privilèges et limites OS.
- scripts/pilot_existing_ollama.py --approved --no-thinking --native-hermes
  --model qwen3.5:4b --digest d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04
  --output docs/NOUVELLE_PREUVE.json ; --skill-only pour le second scénario seul.
  Ces commandes réelles restent soumises à une nouvelle fenêtre autorisée.
- python3 scripts/evaluate_memory.py --phase3 : banc local synthétique.
- python3 scripts/validate_phase3_real.py --check : réanalyse des preuves réelles,
  sans démarrage, écriture de données ou inférence.

## Prochaine fenêtre, à préparer avant accord

Réutiliser VM102 et l'installation, sans clone ni nouveau téléchargement de modèle.
Le mode prepare refuse une identité déjà occupée sans --reuse-lab. Le mode de
reprise implémenté attend le chemin de l’ancien dossier gardien vérifié, puis
contrôle tag, état arrêté, stockage HDD, 4 Gio et onboot=0. Il est testé
localement mais n’a pas été exécuté sur PVE.
Conserver l'arrêt indépendant et les sauvegardes fraîches.

Préparer les contrôles de permission source avant démarrage, puis vérifier le
boot_id et le hash du pare-feu vivant. Relever les sorties réelles de la mission
compétence interrompue pour diagnostiquer les propositions refusées ; ne pas
rejouer aveuglément son run_id. Tester création candidate, source confirmée,
absence de publication, refus de droits excessifs et redémarrage natif.

Une nouvelle fenêtre doit préciser même hôte, cibles, durée, marges et restauration.
Aucun arrêt de Kryptex, aucun changement de pare-feu Windows ni action physique.
Après cette preuve seulement, préparer D : modèle d'embeddings identifié par
empreinte et dimension384, collection jarvis_knowledge_experimental_v1 uniquement,
revalidation SQLite de chaque résultat. Aucun prune ni écrasement de collection.

## Reprise compétence préparée

Le plan courant est [JARVIS_2_PHASE3_SKILL_RETRY_PLAN.md](JARVIS_2_PHASE3_SKILL_RETRY_PLAN.md).
Il remplace le scénario second run isolé par création/évaluation puis relecture
après redémarrage natif dans un HOME neuf, sans reprendre une ancienne mission.
Il demande explicitement une nouvelle fenêtre A/B de30min ; aucun accord ancien
n'est considéré comme renouvelé. CT205 reste une étape distincte à autoriser.
