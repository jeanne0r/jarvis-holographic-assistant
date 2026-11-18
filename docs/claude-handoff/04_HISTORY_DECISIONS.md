# Histoire technique et décisions

Les commits cités existent localement. Les comptes-rendus sont historiques : leurs dates et verdicts restent inchangés. Un rapport de livraison peut précéder plusieurs installations ; suivre la chronologie.

| Étape | Résultats, difficultés et limites | Commits / références |
|---|---|---|
| Interface initiale | Hologramme, états micro/audio, caméra et interface iPhone ; base du frontend actuel | 9c1de2b, 26db944, 17bcb4a, 79216af |
| Phase 1 : mémoire | SQLite canonique, propositions, révisions, corrections, MCP, missions et compétences ; 20 tests initiaux | 5ce566d ; JARVIS_2_AUDIT.md et rapports architecture/tests/déploiement |
| Phase 2 : autonomie locale | Adaptateurs modèle, bridge asynchrone, budgets, consolidation et simulateurs ; simulation distincte du GPU | 658043f ; JARVIS_2_PHASE2_REPORT.md |
| Phase 3 : RTX et Hermes Linux | Premier cycle mémoire réel réussi ; contexte 64 000 nécessaire. Mission de compétence inachevée, RAM Proxmox insuffisante et rollback vérifié | ab0576e, d85b9e6, f92fa15 ; JARVIS_2_PHASE3_REPORT.md |
| Pivot Windows | Installation native isolée ; trois missions réelles, candidate doselab_freshness retrouvée après redémarrage des processus. VM102 conservée arrêtée | f1f2ec6, 1ae8401, 1ad6047 ; JARVIS_2_PHASE4_REPORT.md |
| Phase 5 : Qdrant | Snapshot restauré sur instance isolée, embeddings 384 dimensions réels, collection expérimentale et revalidation SQLite ; aucun prune historique | 2f593d0, b9431b6 ; A1/A2_RESULTS |
| B2 | Trois missions réelles et compétence évaluée ; le critère zéro FTS choisi par Hermes manque : **passed=false** | 136730f ; JARVIS_2_PHASE5_B2_RESULTS.md |
| Phase 5C | UTF-8 Windows corrigé, contrats memory_id/source.ref clarifiés ; C1 essais 1 et 2 échoués, essai 3 strict réussi : 3 appels, 12 853 tokens, 56 s | 6831cc0, 3f1d548, d156ee2, 7bba548 ; C1_THIRD_RESULTS |
| C2 personnel | Ancien lecteur comptait des documents au lieu de tours : non-conformité conservée, rapport privé bloqué. Nouvel inventaire limité aux métadonnées de trois documents, sans import | 4f35034, 6831cc0, 47e5b0a ; PHASE5_FINAL_REPORT et C2_SEGMENTATION_PLAN |
| Phase 6 : hybride | P6-L1 panneau réel puis P6-L2 véritable /ask hybride → Windows → résultat. Préproduction, pas activation vocale sur Jarvis actif | d9d3136, c21e915 ; P6_L1/L2_RESULTS |
| Phase 6C/6D globale | Matrice de 101 couples route/méthode, sessions, ACL, adaptateurs et broker testés avec fixtures ; **NO-GO remplacement global** | 6bb7c4e, 520c2b6, 7847655 ; PHASE6D_FINAL_REPORT et PRODUCTION_DECISION |
| Pilote privé et BPF | Unité utilisateur insuffisante ; unité système avec UID non privilégié et vrais contrôles réseau positifs/négatifs indépendants | 2680592, 30304fd, 5d1a7c2 |
| Interface unique | Panneau intégré, relais privé, rotation lot R, lot G avec un seul redémarrage gateway ; pas de remplacement global | 50fb561, 5064813, 5d249e0 |
| Installation opérationnelle | Installation reprise après refus ; flags désactivés, BPF/ACL/persistance vérifiés par opérateur. Fenêtre initiale refusée puis récupération | de41f4d, 89b637d, 90ed01b |
| Mission de récupération | Mission utilisateur completed : 3 appels, 15 027 tokens, 0 CHF ; rapport strict faux, diagnostic séparé du contrôle de préfixe | 2909dc9, a1b967c ; preuve 200950Z |
| Big Boss A/B/C | A déployé ; B SSO testé mais non activé ; C texte déployé, mission réelle completed : 3 appels, 19 838 tokens, 0 CHF, sans source.ref finale donc verdict faux | b15ebc6, f545107, 7592702, 2b24a92 ; preuve 214641Z |
| Citations | Références présentes dans les révisions/reçus, omises par le modèle ; descriptions MCP et contrat serveur homogénéisés, validateur inchangé | d14a2d5 ; HERMES_TEXT_CITATION_ANALYSIS.md |
| À la demande | File additive, audit en lecture seule, idempotence, quotas et expiration ; livraison : 48 tests Python et intégration HTTP/navigateur. Acceptation installée après attente des ports | eb17c0c, 3835fdf, f41b612 ; HERMES_ON_DEMAND.md |
| Accord 3 | Provisionnement réel partiel puis refus. Entrée stdin avant SSH corrigée, dossiers sous umask 077 corrigés, diagnostic de configuration affiné ; aucune mise en service démontrée | 25ba7a9, 6049401, cd3bc03, 496aef5 |
| Dernier correctif | Configuration trop grande pour 16 Kio ; plafond principal 128 Kio, identifiants toujours 16 Kio. 42 tests actuels ; application root non confirmée | fe589cc |

Une mission `completed` peut conserver un verdict de provenance faux. Aucun ancien `passed=false` ne devient vrai dans cette passation. Un redémarrage de processus Hermes ne vaut pas redémarrage du PC ou de CT205.

## Décisions à conserver

- Un frontend, voix hybride conservée ; pas de retour à une VM Hermes sur Proxmox.
- Hermes sur Windows ; Codex spécialiste du développement, sans transfert de ses droits à Hermes.
- Mémoire canonique sur Proxmox et Qdrant reconstructible ; pas de mémoire factuelle concurrente Hermes.
- Le modèle ne décide ni permissions, ni validation des faits, ni publication. Deux échecs antérieurs de sécurité de Qwen 4B restent des réserves.
- Les données synthétiques des essais réels ne constituent pas un consentement à transmettre des conversations personnelles.
- Les mentions anciennes « panneau/admission non activés » sont des instantanés antérieurs aux déploiements suivants, pas des erreurs à corriger dans les preuves.
