# Reprise hiérarchisée — ne pas exécuter pendant la passation

| Priorité | Dépendances et réutilisation | Risque | Premier pas concret |
|---|---|---|---|
| 1. Finir le commissionnement à la demande | commission.py, config 128 Kio, checkpoint root connu, attestation réelle des deux services | garde BPF / permissions manquantes, configuration partielle, mission expirée/incertaine | vérifier état et empreintes sous accès approprié puis proposer la reprise ciblée existante ; pas de réinstallation générale |
| 2. Usage normal sans sudo par mission | file persistante déjà installée, superviseur dédié, quotas et idempotence | ne pas confondre supervision disponible et autostart autorisé ; PC indisponible | après activation validée, l'humain confirme une demande synthétique dans Jarvis ; observer résultat/cleanup/persistance, sans mission créée par agent |
| 3. Audit et organisation mémoire | memory_audit.py et outils audit sous lecture, sources canoniques, correction des citations | audit n'est pas fusion/validation ; modèle peut ignorer sources | vérifier contrat des futurs résultats et présenter les propositions sans mutation ; transport Qdrant actuel non activé à revoir séparément |
| 4. Première mémoire personnelle | segmentation C2 testée, provenance/révisions/candidats, stockage canonique | exposition Windows, mauvais découpage, propriétaires non attribués | demander accès structuré limité, produire manifeste de 20 tours maximum avant lecture/import ; pas de lecture automatique des bases |
| 5. Connexion unique | code SSO B, politique/registre, preuves 5 s indépendantes | routes historiques non protégées + Codex même UID peuvent compromettre la preuve | reprendre seulement les prérequis précis de JARVIS_2_LOT_B_SSO.md ; pas de token universel ni repli anonyme |
| 6. Délégation vocale naturelle | façade hybride /ask, P6-L2 déjà validé, admission asynchrone | permissions du worker Codex, contexte privé, risque audio | après queue fiable, proposer flag/patch minimal et accord vocal ; préserver micro/interruption/streaming |
| 7. Observation HA lecture seule | HA existant, déclencheurs déterministes, autorisations distinctes | API HA peut exposer actions physiques ; métriques peuvent être personnelles | définir identité/outils de lecture bornés, tester d'abord fixtures ; aucun outil service_call ou contrôle équipement |

L'augmentation de taille de configuration n'est qu'un correctif logiciel. Ne pas conclure que tous les contrôles réels suivants passeront : UID, clés privées, règles réseau, preuve root et état des missions restent des préconditions. Si un nouveau blocage apparaît, diagnostiquer précisément hors GPU avant nouvelle exécution.

Aucune nouvelle architecture, frontend, orchestrateur, mémoire parallèle ou comparaison GPU systématique n'est nécessaire pour ces premiers pas. Les anciennes preuves sont suffisantes dans leur périmètre ; une vérification de sécurité fraîche d'un service redémarré reste obligatoire.
