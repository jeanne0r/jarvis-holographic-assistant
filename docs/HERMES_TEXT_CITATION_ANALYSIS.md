# Texte libre — analyse hors ligne des citations

Mission : `a573c225-1879-4458-9ca0-89407cb2cc5f`, fenêtre `20261115T214641Z-0f2a81f1`.

## Conclusion

**Omission dans la réponse finale, pas incompatibilité de format avec le validateur.** La réponse exacte cite des `memory_id` et UUID d'épisodes, mais aucune des cinq références originales. Elle ne contient aucune occurrence de `synthetic://` ou `mission://`.

Les six reçus immuables attestent les révisions renvoyées par un appel `memory.knowledge`, un appel `memory.search`, puis quatre appels `memory.history`. Les cinq révisions distinctes correspondent aux sources :

- `synthetic://doselab/correction`
- `synthetic://doselab/old`
- `synthetic://doselab/experience`
- deux expériences `mission://…` issues des missions synthétiques précédentes.

La recherche a renvoyé la configuration actuelle, la leçon diagnostique et les deux rapports précédents ; l'historique a également renvoyé l'ancienne configuration. Les rapports antérieurs contiennent eux-mêmes les références synthétiques dans leur résumé. Le chemin MCP conserve le JSON et son champ `source.ref`, sans transformation en UUID seul.

La description de `memory.knowledge` demandait déjà une citation explicite. En revanche, `memory.search` et les outils d'historique n'avaient pas cette consigne homogène ; le payload de mission textuelle ne comportait pas de contrat de restitution. Cette faiblesse de guidage est corrigée, mais ne prouve pas pourquoi le modèle a ignoré la première consigne.

**Limite des traces :** les reçus conservent les identifiants des révisions renvoyées, pas les arguments des outils ni les requêtes complètes envoyées au modèle. Les lignes SQLite exportées sont des révisions canoniques, pas une capture des octets MCP. Il est donc impossible de certifier hors ligne la présentation finale de chaque message dans le contexte Hermes, ou d'exclure une transformation interne non journalisée. Aucune prétendue trace modèle n'a été reconstituée comme preuve réelle.

## Contrôle final

`scripts/text_mission_window.py::result_provenance` vérifie d'abord la provenance canonique et les références autorisées, puis cherche littéralement une référence synthétique rendue dans la réponse. Il n'exige ni URL cliquable, ni JSON, ni marqueur particulier : texte simple, code Markdown et lien contenant l'URI exacte sont acceptés. Le texte enregistré n'en contient aucune ; `model_cites_source_ref=false` et `passed=false` sont donc justifiés.

Le contrôle existant reste **inchangé**. C'est un critère minimal de présence d'une citation, pas une preuve de couverture de toutes les affirmations ni de justesse du raisonnement. Les nouvelles consignes demandent de citer chaque conclusion dérivée de la mémoire ; les tests ne prétendent pas démontrer l'obéissance future du modèle.

## Correctif préparé, non déployé

1. `memory_manager/phase2/mcp.py` : consigne identique pour tous les outils de lecture mémoire. Citer `source.ref` exactement à côté de la conclusion et dans une section Sources ; distinguer cet identifiant de `memory_id` et de l'identifiant de révision. Schémas, contenu des résultats et permissions inchangés.
2. `memory_manager/phase2/bridge.py` : contrat de restitution fixe, choisi par le serveur, dans les **nouveaux** payloads autorisant recherche et rapport. L'objectif utilisateur, les outils, le contexte mémoire, les budgets et le protocole natif restent inchangés. Le texte utilisateur ne peut pas fournir ou remplacer ce contrat. Aucune insertion automatique de citation dans une réponse du modèle.
3. Le contrat rappelle les statuts `inferred`/non vérifiés, les versions remplacées et la conservation des originaux. La réponse historique proposait une suppression et qualifiait deux épisodes d'identiques alors que leurs textes et empreintes diffèrent ; ce sont des réserves de qualité, pas des actions réalisées. Aucune consolidation ou suppression n'est exécutée.

Une admission idempotente d'une mission déjà enregistrée conserve son ancien payload. Les événements, réponses et reçus historiques ne sont jamais réécrits.

## Preuves conservées

Extraction locale privée, hors Git : `data/operational/window-20261115T214641Z-0f2a81f1/citation-evidence.json`.

- SHA-256 de l'extraction : `2ec0cc391398b113eb35ba37628a394693271591663c578b2ab6a58e565cafc6`.
- SHA-256 du texte final exact : `508c9049b939ef6eadff5d5ded0d0aae20074fbc776c7df9836aa5cab0c2068f`.
- Les deux empreintes historiques contenues dans l'extraction ont été revérifiées après lecture. Le bilan historique reste `passed=false`.

L'extracteur ciblé `ops/pilot-network/export-text-citation-evidence.py` utilise SQLite en lecture seule et `query_only`. Il ne lit ni configuration ni identifiants, n'effectue aucune requête réseau et n'écrase aucun export existant. Seul son code est versionné, pas la réponse complète ni l'extraction.

## Validation et suite

Tests synthétiques ciblés : contrat jusqu'à l'entrée native simulée, maintien des quotas/outils/objectifs, refus du shell, impossibilité de remplacer le contrat, idempotence des anciens payloads, outils MCP et références inchangés, UUID seuls et références inventées refusés, différents rendus lisibles d'une URI exacte acceptés, provenance forgée refusée. Régressions MCP Unicode/historique et bridge asynchrone/annulation exécutées sur fixtures.

Commandes exécutées :

- `python3 -B -m unittest memory_manager.phase6.test_citation_contract memory_manager.phase5c.test_preparation memory_manager.phase6.test_text_window memory_manager.phase2.test_integration.Integration.test_bridge_async_native_contract_progress_restart_result memory_manager.phase2.test_integration.Integration.test_native_admission_idempotency_header_and_cancel -q` : **24 tests réussis**.
- `python3 -B -m unittest memory_manager.phase6.test_operational -q` : **11 tests réussis**.
- Empreintes des preuves historiques et du validateur strict revérifiées, inchangées.

Aucun déploiement, changement de manifeste d'activation, redémarrage, appel Windows/GPU ou fournisseur payant. Le correctif nécessitera une revue des nouvelles empreintes et l'autorisation de mise à jour des copies privées/Windows avant un futur essai. Les lanceurs épinglés existants doivent continuer à refuser toute copie modifiée non approuvée ; aucun reçu consommé n'est réinitialisé.
