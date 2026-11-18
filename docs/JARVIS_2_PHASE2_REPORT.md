# JARVIS 2 — Rapport de phase 2

Développement poursuivi dans `jarvis-2-memory`, branche
`codex/jarvis-2-memory-20261113`, à partir de `c6dda50`. Le checkout servi par la
gateway, Gemini/voix, les bases réelles, Home Assistant et les services de
production restent inchangés. Rien n’a été installé sur les machines.
Commit du socle et des tests de phase 2 : `5ce566d`.

## Résultat concret

Le laboratoire relie maintenant admission d’une mission, interface native Hermes
simulée, contexte mémoire, inférence locale compatible simulée, propositions
attribuées, expérience, consolidation et retour de résultat. Les composants
existent en code et passent leurs tests. **Ollama a maintenant été exécuté
réellement sur la RTX**, après accord : 14 inférences abouties, banc final 6/7,
avec échec de sécurité sur une instruction physique externe. Hermes reste simulé.
Le serveur temporaire et le tunnel sont arrêtés. Voir le
[pilote GPU réel](JARVIS_2_PHASE2_GPU_PILOT.md) pour mesures, échecs et preuves.

## Composants développés et preuves

| Composant | Réalisation | Vérification / limite |
|---|---|---|
| Inférence | phase2/local_model.py : Ollama native /api/chat et /v1/chat/completions, digest installé imposé, JSON strict, limites contexte/sortie/timeout, gate GPU, aucun pull ni fallback | Faux endpoints pour les deux protocoles ; native JSON également testée sur Ollama 0.35.1 / RTX réelle |
| Mission | phase2/bridge.py + http_bridge.py : réutilisation mm_missions, outbox durable, bail worker, admission 202 sans appel agent, suivi, résultat, annulation | Simulateur Jarvis et faux Hermes HTTP ; reprise par nouvelle connexion SQLite |
| Hermes | phase2/hermes.py : /v1/runs, status, stop, request_id et once/deny pour approval, Idempotency-Key stable | Contrat vérifié statiquement sur commit officiel épinglé, tests du client sur faux serveur |
| Événements | Journal durable et SSE avec Last-Event-ID | Pages SSE finies, reconnexion nécessaire ; pas de push permanent ni notification iPhone branchée |
| Approbation | Identité humaine distincte, propriétaire/espace, empreinte exacte, expiration, refus always/session et auto-approbation | Pas de droits accordés au modèle ; une approbation ne peut étendre la liste d’outils |
| Mémoire | phase2/memory_tools.py et mcp.py : recherche, sources/historique, projet, analogies, contradictions, propositions, compétence, résultat de mission lié par l’hôte | Pas de voie de promotion dans ces outils ; les rapports restent inferred |
| Consolidation | phase2/pipeline.py : cadences immédiate/nocturne/hebdomadaire, citations exactes, checkpoint de sortie avant application, rejeu idempotent | Pas d’import réel ni scheduler installé ; pas de fusion ou correction active autonome |
| Ressources | phase2/budgets.py : réservation atomique partagée, enfants sur le même budget, suivi mensuel Zurich, coûts distants 0 par défaut, configurable jusqu’à 10 CHF/mois | Budget local partagé effectivement raccordé au pipeline ; runtime Hermes réel doit passer par le même broker avant activation |
| Compétences | phase2/skill_registry.py et skill diagnostic-refroidissement-s19 : versions immuables, références à révisions, tests fixes, publication reviewer indépendant, rollback réévalué | Publication dans le registre de laboratoire ; aucun skill installé dans Hermes |
| Qdrant | phase2/vector.py : collection expérimentale exacte, 384D cosine, modèle et empreinte artefact d’embedding, upserts sans prune/delete, revalidation SQLite | Transport/embeddings injectés ; vrai Qdrant non modifié et nouveau endpoint embeddings non déployé |
| Exécutant | phase2/sandbox.py : bubblewrap, HOME vide, pas de réseau/secret, ressources et sortie bornées ; proposition Codex distincte | Sandbox réellement exécutée sur fixture ; aucune invocation Codex payante ni délégation de développement réelle |

Migration `phase2/database.py` : tables p2_* additives, **sur base de laboratoire
seulement**, après sauvegarde SQLite vérifiée et manifeste. La répétition est sans
effet. Le schéma mm_* de phase 1 et ses garanties sont conservés.

## Hermes officiel : découverte importante

Référence retenue : `4959268e312a21a361f248e49030d5f5df3984d5`, récupérée depuis le
dépôt officiel, sans installer ses dépendances ni importer son runtime.
`JARVIS_2_PHASE2_HERMES_PIN.json` conserve les empreintes des fichiers inspectés.
Le serveur officiel a effectivement une API de runs, SSE et approbations ;
le pont n’invente donc pas un protocole de commandes shell pour les missions.

[Code des routes](https://github.com/NousResearch/hermes-agent/blob/4959268e312a21a361f248e49030d5f5df3984d5/gateway/platforms/api_server.py),
[admission et contrôles](https://github.com/NousResearch/hermes-agent/blob/4959268e312a21a361f248e49030d5f5df3984d5/gateway/platforms/api_server_runs.py),
[interface programmatique AIAgent](https://github.com/NousResearch/hermes-agent/blob/4959268e312a21a361f248e49030d5f5df3984d5/run_agent.py).
L’interface AIAgent accepte notamment base_url/provider/api_mode et des limites ;
run_conversation fournit une alternative au serveur. L’API native est retenue
pour découpler les processus. Les sous-agents, skills, mémoires natives et cron
ont été relus ; aucune intégration mémoire Qdrant native n’est requise ni supposée.

Le profil JARVIS devra désactiver les mémoires natives, limiter ses outils au
MCP contrôlé et monter les compétences publiées en lecture seule. Ne pas recopier
les souvenirs dans MEMORY.md/USER.md. Le registre JARVIS reste le contrat métier ;
l’identifiant du run Hermes est une référence d’exécution, pas une seconde mémoire.

## Tests exécutés

```bash
python3 scripts/evaluate_memory.py --phase2
```

Rapport exact : `JARVIS_2_PHASE2_TEST_RESULTS.json`. Les **20 tests de phase 1**
sont conservés ; **29 tests d’intégration de phase 2** sont ajoutés, avec les
régressions SQLite, espaces, conversations, recherche, worker, corrections, HA
simulé et routage hybride déjà sélectionnées. Le banc de benchmark simulé passe.
Le skill a aussi passé le validateur de structure Skill Creator.
Le script Windows a ensuite été exécuté pendant le pilote explicitement autorisé.
Les tests locaux restent entièrement synthétiques ; les mesures RTX séparées
sont détaillées dans JARVIS_2_PHASE2_GPU_PILOT.md.

Les nouveaux cas couvrent : HTTP native/compatible, JSON malformé et champs
de privilèges rejetés, modèle absent, timeout, contexte, digest, minage/VRAM,
source malveillante, citations inventées, budget global avant inférence,
reprise après checkpoint sans deuxième inférence, livraison ambiguë fermée,
admission immédiate, annulation, état inconnu, deadline, approbation exacte
par acteur distinct, expiration, isolation utilisateurs, skill régressif refusé,
publication/rollback et permissions excessives, embeddings incompatibles,
hits périmés, sandbox OS et cycle synthétique bout en bout.
Les derniers cas vérifient aussi déduplication exacte, avertissement de
contradiction, pause/reprise et conservation du vrai modèle source après
redémarrage, même si le modèle configuré a changé. Chaque candidat garde
la date de l’événement qu’il cite, plutôt que celle d’un événement voisin.

La procédure synthétique de refroidissement progresse de 2/3 à 3/3 cas réussis
en ajoutant le contrôle de fraîcheur. C’est une mesure sur fixtures, **pas**
une amélioration démontrée du refroidissement physique du S19.

## Sécurité, performances et consommation

L’admission HTTP est vérifiée inférieure à 1 s en laboratoire et ne lance aucun
travail agent. Cela ne constitue pas un SLA de production. Le modèle est borné
par contexte, sortie, tentatives, réservation et timeout ; une télémétrie absente
ou occupée suspend le traitement. Aucune bascule vers une API distante n’existe.
Les mesures GPU incluent désormais le pilote réel : médiane 4,36 s au banc final,
pic VRAM échantillonné 7 198 MiB, 172,32 W observés. Ce modèle échoue au test
d’instruction physique malveillante et ne doit pas recevoir de pouvoirs sensibles.

Les anciennes faiblesses de la gateway, des profils et du worker conversationnel
ne sont **pas corrigées en production par cette branche**. Elles bloquent encore
l’activation autonome : authentification JARVIS, mapping d’ACL, profil OS Hermes,
réseau sortant limité au proxy local et outils physiques absents. Les booléens
de revue du worker ne remplacent pas ces barrières OS.

Risques restant ouverts : l’arrêt HTTP ne prouve pas l’arrêt de calcul GPU distant ;
le vrai serveur doit être testé pour interruption/quotas. Un timeout de livraison
ou un run unknown n’est pas rejoué : réconciliation humaine nécessaire.
Les approbations à réponse perdue demandent aussi une réconciliation avant retry.
Les mesures de tokens déclarées par le serveur doivent être rapprochées des
limites du broker ; tous les appels et sous-agents du vrai Hermes devront y passer.
La fenêtre GPU mesurée n’est pas du temps CUDA ; les pics du pilote sont
échantillonnés, sans garantie de capturer le maximum continu. Les sources référencées sont attribuées, sans certification automatique
de leur vérité. Les propositions de skills sont déclaratives, pas du code arbitraire.

## Accords nécessaires et prochaines actions

1. **Pilote Ollama autorisé et effectué** : aucun téléchargement, 6/7 au banc
   clarifié, échec de permissions reproduit. Arrêt du serveur et du tunnel vérifié.
   Cet accord temporaire ne vaut pas installation ni activation permanente.
2. **Téléchargements de modèles** : choisir le premier comparatif compact après
   estimation mémoire/disque ; chaque installation reste à autoriser. Choix
   provisoire expliqué dans `JARVIS_2_PHASE2_GPU.md`.
3. **Hermes** : approuver son installation épinglée dans une préproduction
   dédiée et le profil réseau/outils. Budget distant initial maintenu à 0 CHF.
4. **Embeddings/Qdrant** : revue et déploiement séparé du endpoint d’embeddings
   attesté et de la collection expérimentale, sauvegardes et restauration d’essai
   avant tout changement réel. Aucun appel au prune de jarvis_memory_v1.
5. **Raccordement JARVIS** : seulement après revue du patch exact d’identité/ACL,
   tests runtime réels, limites globales et essais voix/iPhone ; la session vocale
   ne doit faire qu’une admission asynchrone et consulter les résultats.

Le laboratoire est prêt pour ces validations ; il n’est pas annoncé comme une
installation Hermes/RTX opérationnelle en production.
