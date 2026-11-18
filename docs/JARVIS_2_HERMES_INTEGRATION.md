# JARVIS 2 — Hermes : observations et adaptateur expérimental

## Mise à jour de phase 2

La référence active de l’adaptateur de phase 2 est
`4959268e312a21a361f248e49030d5f5df3984d5` ; l’inspection historique ci-dessous
reste conservée comme audit initial. Contrairement à une hypothèse d’absence
d’API, les routes natives /v1/runs, status, events, approval et stop sont présentes
dans cette référence. Le client fourni les utilise, avec Idempotency-Key et
request_id exact ; seules les décisions once/deny sont transmises.

Le MCP étendu se lance avec `python3 -m memory_manager.phase2.mcp --token-file ...`.
Il conserve handshake et outils de lecture historiques et ajoute projet,
expériences, contradictions, propositions et compétences. `--mission-id` est
une liaison choisie par l’hôte, nécessaire pour exposer le résultat de mission.
Le modèle ne choisit ni son propriétaire ni son rôle ni cette liaison.

Le worker `python3 -m memory_manager.phase2.worker --config fichier-prive.json`
est un processus séparé ; il refuse l’activation par défaut. Hermes n’est pas
installé. Les tests vérifient les contrats via faux serveurs HTTP, pas par import
de modules upstream. Voir [rapport et limites](JARVIS_2_PHASE2_REPORT.md).

## Référence examinée

Code officiel cloné en lecture seule, sans installation, dépendances ou import
de ses modules. Commit observé le 13 novembre 2026 :
`491f9845833cb0a005a744aa9a81aea8d8bc2b48`.
La documentation publique peut avancer indépendamment : les observations de
code ci-dessous sont liées à ce commit, pas une garantie sur une future version.

| Capacité | Preuve de code épinglée | Conséquence pour JARVIS |
|---|---|---|
| Découverte de compétences | [tools/skills_tool.py](https://github.com/NousResearch/hermes-agent/blob/491f9845833cb0a005a744aa9a81aea8d8bc2b48/tools/skills_tool.py) : liste compacte et consultation détaillée | Charger les procédures publiées à la demande |
| Création/amélioration | [tools/skill_manager_tool.py](https://github.com/NousResearch/hermes-agent/blob/491f9845833cb0a005a744aa9a81aea8d8bc2b48/tools/skill_manager_tool.py) : gestion de SKILL.md et ressources, création et édition, verrous ; scan des créations conditionné par configuration | Ne pas confondre capacité d’écrire un skill et garantie de publication après non-régression |
| Mémoire | [tools/memory_tool.py](https://github.com/NousResearch/hermes-agent/blob/491f9845833cb0a005a744aa9a81aea8d8bc2b48/tools/memory_tool.py), memory_tool_store.py : magasins bornés, add/patch/remove, activation configurable | Garder les faits JARVIS dans le Memory Manager |
| Sessions passées | [tools/session_search_tool.py](https://github.com/NousResearch/hermes-agent/blob/491f9845833cb0a005a744aa9a81aea8d8bc2b48/tools/session_search_tool.py) : SQLite FTS5, lecture/parcours, filtres temporels ; résultats DB sans LLM dans cette version | Réutiliser des références de sessions, pas des résumés supposés vérifiés |
| Sous-agents | [tools/delegate_tool.py](https://github.com/NousResearch/hermes-agent/blob/491f9845833cb0a005a744aa9a81aea8d8bc2b48/tools/delegate_tool.py), delegate_tool_child_run.py : enfants, suivi, arrêt, limites | Budget et outils doivent être hérités et réduits par le broker JARVIS |
| Planification | [cron/scheduler.py](https://github.com/NousResearch/hermes-agent/blob/491f9845833cb0a005a744aa9a81aea8d8bc2b48/cron/scheduler.py), cron/executions.py : scheduler et journal d’exécutions persistantes | Éviter deux schedulers concurrents pour la même mission ; JARVIS conserve son identifiant métier |
| Outils externes | [tools/mcp_tool.py](https://github.com/NousResearch/hermes-agent/blob/491f9845833cb0a005a744aa9a81aea8d8bc2b48/tools/mcp_tool.py) et modules MCP dédiés | MCP est le raccordement proposé, sans patcher Hermes |

La recherche du terme Qdrant dans tools/, agent/, hermes_cli/ et pyproject.toml
renvoie notamment des références au catalogue de compétences ; elle n’établit
pas de backend mémoire Qdrant natif dans ces chemins. Le projet ne dépend donc
d’aucune intégration Qdrant native supposée.

Documentation officielle consultée : [compétences](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills),
[mémoire persistante](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory),
[MCP](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp).
Les petits magasins MEMORY.md et USER.md sont injectés au début d’une session.
Pour le profil JARVIS envisagé, désactiver les deux magasins intégrés après
validation de la configuration épinglée ; conserver les sessions Hermes comme
traces propres à l’exécutant, avec références vers les connaissances canoniques.

## Adaptateur fourni

`memory_manager/hermes_mcp.py` implémente le sous-ensemble MCP stdio initialize,
ping, tools/list, tools/call et notifications sans réponse. Deux outils seulement :

- `jarvis_memory_search(q)` : contenu actuel, provenance, statut et contradictions.
- `jarvis_memory_history(memory_id)` : versions d’un souvenir accessible.

Le token est lu depuis un fichier privé ; pas de secret dans les arguments de
ligne de commande, le prompt, la sortie stdio ou le dépôt. L’identité est fixée
côté API, jamais dans les paramètres du modèle. Le pont appelle uniquement
127.0.0.1 et désactive les proxies d’environnement. Il ne peut ni vérifier un
fait, ni corriger, ni publier, ni piloter HA. Une extension de proposition devra
rester inferred et utiliser le même contrôle d’ACL.

Exemple de bloc **à adapter et approuver**, non installé :

```yaml
memory:
  memory_enabled: false
  user_profile_enabled: false
mcp_servers:
  jarvis_memory:
    command: python3
    args:
      - -m
      - memory_manager.hermes_mcp
      - --token-file
      - /run/credentials/jarvis-memory-token
      - --port
      - "8791"
```

Lancer dans un environnement où le paquet du worktree est accessible ; ne pas
supposer que la configuration MCP fournit un cwd. Le déploiement devra fixer
interpréteur, chemin du paquet et isolation explicitement. Cet exemple n’active
aucun autre outil Hermes et ne vaut pas une configuration sécurisée complète.

## Cycle de compétence

Expérience référencée → analyse → proposition sur branche → tests définis par
le mainteneur → revue → commit publié → évaluation sur usages → nouvelle version.
La version publiée est montée en lecture seule. Hermes ne peut écrire que dans
une zone de propositions ; le broker Git/promoteur est hors de son compte.
Les tests ne sont pas modifiables par la proposition évaluée sans revue distincte.

Exemple présent : `skills/compare-load-cells/`. Le v1 synthétique suppose à tort
que les cellules sont identiques ; v2 compare toutes les capacités. Un interprète
déclaratif borné applique la procédure sans exécuter du Python fourni par agent.
L’évaluation fixe trois cas, conserve les anciens cas passants et recalcule les
résultats lors de la préparation du manifeste. Le manifeste exige reviewer et
n’installe rien. C’est un démonstrateur de boucle d’amélioration, pas un système
universel de certification ou d’apprentissage autonome.

## API missions proposée, non exposée par le prototype HTTP

| Route | Contrat minimal |
|---|---|
| POST /v1/missions | Idempotency-Key, objectif, déclencheur, priorité, références mémoire, plan, outils demandés, budget ; 202 + id |
| GET /v1/missions/{id} | État, version, limites restantes, action en attente et horodatages |
| GET /v1/missions/{id}/events | SSE ; identifiant séquentiel et Last-Event-ID pour reprise |
| POST /v1/missions/{id}/approvals | Identité humaine distincte, empreinte exacte action/patch, expiration, décision, état attendu |
| POST /v1/missions/{id}/cancel | Annulation idempotente et arrêt coopératif ; signalement des effets au résultat inconnu |
| GET /v1/missions/{id}/results | Artefacts, commits, tests, preuves et statut de validation |

Le registre Python persiste déjà définitions, états et événements ; routes,
SSE et broker d’approbation sont maintenant implémentés en laboratoire dans
l’extension de phase 2 ; le runtime Hermes reste à installer et valider en préprod.
Aucune approbation peut être créée par une chaîne de raisonnement ou un souvenir.

## Résultat phase 3 observé le 14 novembre 2026

Un premier cycle Hermes officiel + Qwen4B sur RTX3080 + mémoire canonique a
réussi en laboratoire. Le runtime épinglé exige 64000 tokens ; le profil
préparatoire8192 n’est pas compatible. Sources, mesures, limites et procédure
de reprise sont dans [JARVIS_2_PHASE3_REPORT.md](JARVIS_2_PHASE3_REPORT.md).
La VM102 est arrêtée et les allocations des invités existants sont restaurées.
La mission compétence est inachevée, Qdrant réel et gateway restent différés.

## Décision du 14 novembre2026 — phase4 Windows

L'hébergement Hermes passe au PC GAMER Windows natif ; la stratégie de récupération
RAM Proxmox et de réservation4Gio est abandonnée provisoirement. VM102 reste
arrêtée sur disque ; allocations103/201 et absence de gardien vérifiées en lecture
seule. Les anciennes preuves et composants sont conservés. Aucun nouveau
démarrage/installation autorisé par cette note. Plan courant :
[JARVIS_2_PHASE4_WINDOWS_PLAN.md](JARVIS_2_PHASE4_WINDOWS_PLAN.md).
