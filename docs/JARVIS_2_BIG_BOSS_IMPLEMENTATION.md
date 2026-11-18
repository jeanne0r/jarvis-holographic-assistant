# Jarvis : missions intégrées — réalisation

Développement isolé, 15 novembre 2026. Aucun déploiement, nouveau test RTX, fournisseur distant ou accès personnel.

## Code livré

- `scripts/prepare_human_missions.py` dérive les **deux assets existants**, avec les contrats opérationnels déjà validés. Aucun nouveau frontend, stockage ou orchestrateur.
- `public/hermes-mission-view.js` : rendu Markdown par création de nœuds DOM (titres, listes, tableaux, code, citations et liens HTTP(S)). Aucun HTML interprété, image distante, script ou URI exécutable. Les grosses réponses restent disponibles intégralement en texte.
- Cartes : missions actives prioritaires ; cinq terminées récentes ; historique des échecs/annulations ; filtre des démonstrations ; titre court ; dates locales ; durée totale seulement si deux dates cohérentes existent. Aucun pourcentage inventé. Un éventuel extrait serveur est affiché comme texte, sans appel de résumé IA.
- Résultat original conservé ; références citées en code consultables via « Source liée » ; projection SQLite, objectif intégral, copie de la réponse et événements dans des détails repliés. Les dates du modèle ne sont pas corrigées silencieusement. Un avertissement visible rappelle que sa réponse reste à vérifier.
- Disponibilité exprimée simplement ; une exécution désactivée n’est pas présentée comme une mesure réelle d’un PC éteint. Aucun démarrage déclenché par la consultation.
- Admission et formulaire actualisés selon les flags serveur ; clé idempotente conservée en cas d’incertitude. Effacement au refus 401/403 ; réponses tardives ignorées après révocation/changement de sélection. Notifications discrètes, sans audio.
- Variante **laboratoire** de connexion unique : réutilisation de `public/jarvis-auth.js` et du registre serveur existant. Aucun échange de code privé, confiance IP ou profil visuel. La variante privée habituelle conserve son authentification actuelle.
- `hermes-mission-policy.mjs` est raccordé à `hermes-embedded-api.mjs` : compilation serveur des capacités inchangées (`memory.search`, `report`), contexte vide, zéro coût distant, plafonds existants. Texte limité à 2 000 caractères et au périmètre synthétique. Toute propriété ajoutant outils, propriétaire ou historique est refusée. L’aide de classification est un **aperçu déterministe**, pas un nouveau routeur actif `/ask`.

## Validation réalisée

| Test | Résultat observé |
|---|---|
| `node test_human_missions_browser.cjs` | 104 contrôles, 1440/390 px, deux modes de connexion, API simulées ; XSS/liens dangereux inertes, données effacées malgré réponse retardée, annulation, filtres, absence de requête audio ou externe |
| `memory_manager.phase6.test_human_assets` | 3 tests : application et retour arrière réels des patches sur copie, refus des liens symboliques/écrasements, client de session partagé |
| `node test_hermes_mission_policy.mjs` | 25 assertions, capacités, injections, texte et permissions |
| `node test_hermes_operational.mjs` | 32 assertions HTTP/session réels, bridge simulé |
| `node test_hermes_embedded.mjs` | 42 assertions HTTP/auth/ACL, fournisseur simulé |
| `node test_phase6d_security.mjs` | 101 paires route/méthode, dont 97 protégées ; révocation des flux et isolation des utilisateurs ; aucune action réelle |
| `node test_phase6d_final.mjs` | 53 paires des familles auxiliaires ; registre de sessions unique et listes filtrées sur fixtures |
| `node test_production_bindings.mjs` | identité, révocation, hybride et absence de contournement Codex sur fixtures |
| `node --experimental-loader ./test_phase6_hybrid_loader.mjs test_phase6_hybrid.mjs` | vrai `/ask` et bridge/SQLite de test ; admission 34 ms ; fournisseurs simulés, zéro appel GPU/API |
| `memory_manager.tests.test_memory` | 20 tests historiques du Memory Manager réussis |
| `memory_manager.phase2.test_integration` | 30 tests : mémoire, contradictions, embeddings/revalidation, budgets, interruption/reprise et compétences candidates/publication humaine/retour arrière |
| `memory_manager.phase6.test_operational` | 11 tests : GPU/Kryptex simulés, plafonds, interdictions MCP, disponibilité et absence de rejeu |
| `memory_manager.phase6.test_operational_runtime` | 1 test : processus candidat et navigateur vers faux endpoints Hermes/Ollama, mémoire SQLite temporaire ; aucun Windows réel |

Une première commande du test hybride sans loader a été refusée par sa protection, avant import du backend ; relancée correctement avec le loader. Une invocation groupée Python s’est terminée par signal 143 sans verdict ; les trois suites concernées ont ensuite réussi séparément. Ces interruptions ne sont pas comptées comme des réussites.

## Limites assumées

Connexion unique non déployable aujourd’hui sur la gateway historique : les raccordements complets de sécurité restent incomplets, notamment services auxiliaires/vocaux et identité Codex isolée. Le panneau seul ne les corrige pas. Aucune attribution automatique de propriétaires historiques.

Le fonctionnement quotidien sans intervention n’est pas activé : le superviseur existant reste à fenêtres bornées. Ni service permanent Windows, ni nouvelle fenêtre GPU, ni admission libre. La dernière mission réelle et son `passed=false` historique restent intacts ; sa vérification ultérieure est une preuve distincte. Le contrôle historique de préfixe de provenance n’a pas été assoupli ici.

Compétences, Qdrant et mémoire réutilisent les composants existants. Aucune donnée personnelle importée ; aucune promotion de fait ou publication de compétence. Validation Safari/iPhone physique et test utilisateur de la nouvelle présentation restent à faire après accord ; Chromium mobile ne les remplace pas.

Après cette préparation, le lot A a été autorisé et installé seul : voir `JARVIS_2_BIG_BOSS_LOT_A_RESULTS.json` et l’annexe de déploiement. Authentification privée inchangée ; aucun autre lot activé.
