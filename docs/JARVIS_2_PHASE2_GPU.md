# Phase 2 — RTX 3080 et choix du modèle

## Mise à jour : pilote autorisé terminé

Ollama 0.35.1 a été exécuté temporairement sur loopback Windows via tunnel SSH.
Le modèle existant sert du Q4_K_M, produit du JSON et obtient 6/7 au banc clarifié,
avec un échec de sécurité reproduit. Serveur et tunnel arrêtés après les tests.
Voir [résultats réels, mesures et limites](JARVIS_2_PHASE2_GPU_PILOT.md).
Les sections suivantes conservent les observations et propositions avant pilote.

## Matériel réellement observé

Audit du 13 novembre 2026 à 23:11 heure de Zurich, via l’accès SSH existant,
commandes de diagnostic uniquement. Preuve machine :
`JARVIS_2_PHASE2_GPU_OBSERVATION.json`.

| Élément | Observation |
|---|---|
| Machine | PC Gamer, gamer.fritz.box, 192.0.2.96 ; accès depuis la VM Codex confirmé |
| OS | Microsoft Windows 11 Professionnel |
| GPU | NVIDIA GeForce RTX 3080, **10 240 MiB**, donc version 10 Go |
| Pilote | 621.24 selon nvidia-smi |
| VRAM utilisée | 1 061 MiB au relevé, soit environ 9 179 MiB libres |
| Charge / consommation | 0 %, 8,31 W, environ 28 °C ; relevé au repos, pas un benchmark |
| Minage | Kryptex et KryptexService présents ; aucun processus miner détecté à ce relevé |
| Ollama | Exécutable existant sous le profil Windows winuser ; version non établie par métadonnées du binaire |
| API | Aucun listener TCP11434 ; GET /api/version, /api/tags et /api/ps indisponibles depuis la VM, API loopback Windows indisponible aussi |
| Modèles sur disque | Un manifeste communautaire Qwen3.5-9B-Uncensored…:latest ; pas de modèle officiel compact comparatif observé |

La présence d’un manifeste ne prouve ni la complétude des poids, ni la capacité
de charger le modèle. Il faut les vérifier après autorisation de démarrage.
Aucun service, minage, pilote, firewall ou paramètre Windows n’a été modifié.
L’accès depuis les autres invités Proxmox n’a pas été testé. L’état au repos
ne garantit pas que Kryptex restera inactif : les contrôleurs existants peuvent
le relancer. Toute inférence exige donc une télémétrie fraîche et échoue fermée
si le minage, la charge ou la mémoire disponible ne conviennent pas.

## Architecture retenue pour le pilote

`Memory Manager / Hermes isolé sur Proxmox → tunnel SSH privé → Ollama loopback Windows → RTX`.

Le SSH existant fonctionne ; cela permet d’éviter d’ouvrir un port public ou
d’ajouter une règle LAN large. Le pilote proposé démarre Ollama seulement sur
127.0.0.1 Windows, puis expose un port loopback sur la VM via SSH. Authentification
du tunnel par la clé déjà installée, vérification de la clé hôte obligatoire.
L’API mémoire et le bridge ont leurs propres tokens, séparés de la gateway.
Un accès LAN/Tailscale avec proxy authentifié peut être envisagé ultérieurement,
sans présumer qu’Ollama vérifie une clé Bearer : son API locale peut l’ignorer.
[Documentation Ollama compatible OpenAI](https://docs.ollama.com/api/openai-compatibility).

## Candidats vérifiés, sélection encore conditionnelle

Tailles indiquées par les fiches officielles consultées le 13 novembre ; elles
ne sont pas des mesures de VRAM. Ajouter KV cache, buffers, contexte et affichage
Windows. Aucun de ces modèles n’a été téléchargé pendant ce travail.

| Candidat | Artefact indiqué | Intérêt du pilote / limite |
|---|---|---|
| [Qwen3.5:4b](https://ollama.com/library/qwen3.5:4b) | Environ 4,0 GB ; outils annoncés | Premier candidat proposé pour extraction française et petit agent ; qualité à mesurer |
| [Gemma3:4b](https://ollama.com/library/gemma3:4b) | Q4_K_M, environ 3,4 GB | Comparatif extraction/résumé ; le support natif des outils n’est pas établi par cette fiche, pas retenu d’office pour l’agent complet |
| [Qwen3:8b](https://ollama.com/library/qwen3:8b) | Q4_K_M, environ 5,2 GB ; outils annoncés | Comparatif capacité/latence avec davantage de marge qu’un gros modèle |
| [Ministral-3:8b](https://ollama.com/library/ministral-3:8b) | Q4_K_M, environ 6,0 GB ; outils annoncés | Alternative multilingue et outils ; vérifier version Ollama et mémoire au contexte choisi |

Le manifeste communautaire 9B existant peut servir de baseline **si autorisé**,
mais son nom NVFP4 ne suffit pas à prouver la quantification réellement servie.
Vérifier digest, /api/show, complétude locale et charge GPU avant de le retenir.
Le choix définitif est fondé sur le benchmark, pas sur le nom ou la popularité.

Le guide Hermes recommande un contexte important pour l’agent avec outils ;
un pilote d’extraction borné à 8K n’est pas une validation du fonctionnement de
l’agent complet. Le profil, ses prompts et le KV cache devront être mesurés sur
10 Go, plutôt que d’imposer aveuglément 64K.
[Guide officiel Hermes/Ollama](https://hermes-agent.nousresearch.com/docs/guides/local-ollama-setup).

## Benchmark livré

```bash
python3 scripts/benchmark_local_models.py --simulate
```

Sept cas français : faits, JSON strict, type de souvenir, contradiction non
résolue, décision projet actuelle, sélection d’outil, raisonnement et tentative
d’instruction physique malveillante (plusieurs propriétés sont testées ensemble).
Le mode simulé vérifie le banc avec des réponses oracle ; il **ne classe aucun
modèle** et ne publie aucune latence, aucun débit ni pic VRAM supposé du GPU.

Le mode réel est explicite : `--live-config chemin-prive.json`. Configuration :
base_url à IP privée, model={model,digest,protocol,context_tokens,max_output_tokens,
timeout_seconds,min_free_mib}, telemetry_file. Il faut un modèle déjà installé,
le digest exact de /api/tags et une télémétrie JSON actualisée pendant le banc
(observed_at Unix, miner_running bool, utilization, free_mib, used_mib).
Il n’existe aucun téléchargement automatique ni endpoint de pull dans l’adaptateur.

Le rapport réel recueille tokens, latence, débit déclaré par le serveur et VRAM
avant/après. Ces snapshots ne sont pas un pic échantillonné. `gpu_window_seconds`
est le temps de requête observé, pas une mesure CUDA ; le coût électrique nécessite
un relevé de puissance dans le temps. Aucun de ces résultats réels n’est disponible
tant que le serveur d’inférence n’est pas démarré avec accord.
