# Phase 5C — Deuxième essai C1 autorisé

14 novembre 2026, 20:35:58–20:36:51 UTC. Nouvel accord explicite « Oui »,
une nouvelle mission synthétique, sans reprise de la mission précédente.
**Verdict global : `passed=false`. Le critère strict reste non validé.**
Le verdict historique B2 et la preuve du premier C1 restent inchangés.

## Ce qui a réellement fonctionné

Hermes natif Windows, commit épinglé
`4959268e312a21a361f248e49030d5f5df3984d5`, source vérifiée (25 615 fichiers),
Qwen3.5:4b de digest
`d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`,
RTX 3080, outils MCP, embeddings et Qdrant expérimentaux réels.
Le correctif du relais a permis les appels au modèle et au nouveau lecteur.

La mission `850e8bf2-8a25-4e7f-82ee-eb1a54898ebd` a réellement appelé avec succès
`mcp__jarvis__jarvis_memory_knowledge`. La trace liée à cette mission contient :

- Requête exacte « masse nominale identique », filtre `knowledge`.
- **Zéro résultat FTS** ; résultat vectoriel obtenu via le service réel.
- Mémoire `555be721-222b-421c-99ac-b1873abec8a7`, révision actuelle
  `6c167c06-f00d-4a22-9779-bd42142c610a`, revalidée dans SQLite.
- Provenance renvoyée au lecteur : `synthetic://doselab/correction`.
- Événement natif `tool.completed`, `error=false`, puis `run.completed`.
- Résultat enregistré comme expérience ; aucune compétence publiée.

Il s'agit bien d'une recherche effectuée par Hermes, pas d'un contrôle hôte
substitué à un appel du modèle. Cette étape seule ne suffit pas au verdict strict.

## Pourquoi le verdict reste négatif

La réponse finale cite la révision et le parent comme « source », sans citer
`synthetic://doselab/correction`. Le contrôle indépendant refuse donc le succès.
L'appel `jarvis_memory_history` a aussi échoué (`MEMORY_DENIED_OR_UNAVAILABLE`).
Les événements conservés ne contiennent pas ses arguments : la cause précise de
ce refus ne peut pas être affirmée à partir de cette preuve.
La confusion d'identifiants est une hypothèse cohérente avec la réponse,
reproduite hors ligne : l'historique accepte `memory_id`, refuse la révision `id`
et la référence `source.ref`. Les ACL n'ont pas été assouplies.

Le résultat de recherche fournit déjà les trois champs ; aucune source n'était
à inventer. La consigne du prochain scénario est maintenant plus explicite :
citer `source.ref`, consulter l'historique avec `memory_id`. Ce changement reste
**hors ligne, non validé par un troisième essai réel**. Un nouveau test synthétique
vérifie la provenance, l'historique et le refus d'une citation réduite aux UUID.
Le vérificateur strict n'a pas été assoupli, aucun rapport historique réécrit.

## Ressources et arrêt

Admission bridge : 15 ms ; exécution native environ 19,4 s ; fenêtre totale 53 s.
2 appels, 7 604 tokens (7 314 entrée, 290 sortie), 0 CHF, aucun téléchargement.
Contexte servi observé : 64 000 ; résidence modèle GPU : 5 154 285 812 octets.
Pic VRAM **échantillonné** : 6 869 Mio, marge observée à cet instant 3 371 Mio ;
ce n'est pas une mesure continue du pic absolu. Puissance échantillonnée max
305,43 W, pas une mesure d'énergie intégrée.
Pic mémoire Job Hermes : 375 386 112 octets, limite 2 Gio.
Pic Job Ollama : 8 247 996 416 octets, limite 12 Gio.
Kryptex non actif aux contrôles, jamais interrompu.

Jobs Hermes/Ollama fermés, processus possédés arrêtés. VRAM finale 1 068 Mio,
9 172 Mio libres. Vérification indépendante : ports Windows 8643/11434 et
contrôleur 8792/11436/8643/11435 fermés. Fenêtre d'approbation `closed=true`,
une mission, deux appels. Aucun service permanent, changement RAM, gateway,
Home Assistant ou collection historique.

Preuves :
`JARVIS_2_PHASE5C_SEMANTIC_REAL_20261114T203558Z-d108320a.json`,
`JARVIS_2_PHASE5C_C1_RETRY_CLEANUP_REAL.json`.

## Périmètres inchangés

C2 reste bloqué après l'erreur de granularité documentée ; aucune nouvelle lecture
personnelle. C3/C4/C6 non autorisés, C5 reporté ; aucune transmission personnelle,
index privé ou transfert de sauvegarde. Un troisième essai réel nécessiterait un
nouvel accord explicite, mêmes bornes 5 min / 6 appels / 98 304 tokens / 0 CHF,
nouvelle mission et arrêt des seuls processus possédés. Aucun essai automatique.

Validation locale après correctif : `python3 scripts/evaluate_memory.py --phase5c`,
**17 commandes réussies**, dont 16 tests phase 5C. Aucun nouvel appel modèle.
Preuve : `JARVIS_2_PHASE5C_TEST_RESULTS.json`.
