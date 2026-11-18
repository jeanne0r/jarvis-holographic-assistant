# Phase 3 — résultats Hermes réels

**Premier cycle natif validé ; apprentissage de compétence encore incomplet.**
Les faits, versions, ressources et limites sont récapitulés dans
[JARVIS_2_PHASE3_REPORT.md](JARVIS_2_PHASE3_REPORT.md).

## Installation observée

- VM102 jarvis-lab, 4 Gio, 2 vCPU, 24 Gio HDD, arrêtée après la fenêtre autorisée.
- Commit 4959268e312a21a361f248e49030d5f5df3984d5 ; Python 3.14.10 ; uv 0.13.8.
- uv sync --locked --no-dev --extra mcp --extra sms --python 3.14 ; 84 distributions.
- Inventaire, binaire Python et empreinte uv.lock : HERMES_INSTALL_REAL.json,
  préfixé JARVIS_2_PHASE3_. Pas de setup wizard, daemon persistant ou fournisseur payant.
- Une première tentative bootstrap a précédé la disponibilité de python3-venv ;
  son dossier incomplet a été conservé par renommage. L'installation complète a
  ensuite réussi. L'installateur vérifie désormais ensurepip avant de créer un dossier.

## Contrat exercé

Le bridge admet la mission hors boucle vocale, puis utilise /v1/runs et son
run_id. Les états natifs et événements SSE sont réellement consultés.
Le JSON SSE porte event: tool.completed dans le payload, sans ligne SSE event:
obligatoire. Le parseur accepte les deux formes et l'évaluation brute est conservée.

Premier run : run_1c8c1807f25f4292ac2def8a6d0d92e9 ; mission bridge
05397fc0-24c9-4023-88e5-d9d5b2663134. Trois appels au modèle, une recherche et deux
historiques MCP réels ; réponse correcte avec URI de sources et anciennes valeurs.
L'épisode résultat reste inferred dans le SQLite canonique du laboratoire et est
retrouvé après réouverture. Vérification hors ligne :

```bash
python3 scripts/validate_phase3_real.py --check
```

## Profil effectivement nécessaire

Le runtime refuse 8192 : agent/agent_init.py::_enforce_minimum_context impose
64000 sur le provider custom. Le profil final, le relais et Ollama utilisent
réellement 64000, confirmé dans /api/ps. Aucun patch du code Hermes épinglé.
Le relais est limité à six appels, 180 s, sortie 768 tokens, quota local 98304
consommé réellement et réservations durables de 64000 par appel ; aucune réserve
distante possible. Après règlement d'un appel, seul son usage réel reste consommé.

Le provider est custom vers le relais privé /v1 ; l'environnement contient
seulement les variables de laboratoire nécessaires. memory_enabled et
user_profile_enabled sont false, provider mémoire none, nudge_interval 0 ;
compression, titres et background_review désactivés. Les traces de session
Hermes persistent sur le disque de sa VM et ne sont pas une mémoire canonique.

platform_toolsets.api_server/cli ne contient que mcp-jarvis ;
tools.tool_search.enabled=off désactive la façade générique de découverte.
Le relais refuse tout outil qui ne correspond pas à la liste contrôlée.
Le mode skill_candidate est choisi par le contrôleur, dans un HOME distinct.
Le raisonnement demandé par le SDK n'active pas thinking : le relais fixe think=false.

## Limites et reprise

La seconde mission a appelé le modèle quatre fois mais n'a créé aucune compétence.
Elle est interrompue à l'arrêt du laboratoire, puis conservée paused/cancel_requested,
sans nouvelle livraison automatique. L'évaluation des candidats et leur publication
humaine ne sont pas validées par ce runtime réel. Elles restent testées en simulation.

Les premières erreurs de permissions, de minimum de contexte et de port sont
conservées dans les rapports NATIVE_HERMES_REAL*.json. Le premier indicateur
runtime_tested désignait une tentative et non une API effectivement atteinte ;
les preuves d'acceptation reposent exclusivement sur les traces du run réussi.

Le lanceur attend désormais la libération TIME_WAIT pendant au plus 60 s et refuse
un listener encore actif ; le contrôleur attend au plus 75 s pour l'API. Ce
correctif et la vérification fraîche du boot_id/pare-feu sont testés localement,
pas encore rejoués sur la VM arrêtée. Reprendre cette installation existante lors
d'une autre fenêtre autorisée, après contrôle des ressources et du gardien.

## Tentative de reprise autorisée — 14 novembre2026

Admission Proxmox refusée : maximum observé4,284Gio disponibles, seuil5Gio.
VM102 et Ollama non démarrés, zéro inférence, aucun nouveau résultat Hermes.
Retour arrière RAM103/201 vérifié par SHA256, gardien arrêté.
Voir JARVIS_2_PHASE3_SKILL_ADMISSION_REAL.json et la dernière section du rapport.
