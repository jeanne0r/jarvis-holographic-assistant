# JARVIS 2 — Schéma mémoire

## Extension de phase 2

Les tables mm_* ci-dessous restent le socle de phase 1. L’extension additive
`memory_manager/phase2/schema.sql` ajoute : p2_schema, p2_events, p2_outbox,
p2_approvals, p2_llm_jobs, p2_skills, p2_skill_active, p2_skill_audit, p2_budgets
et p2_usage. `phase2.database.migrate` exige un magasin Memory Manager existant,
crée d’abord une sauvegarde vérifiée, puis applique le DDL dans une transaction.
Elle a été testée uniquement sur bases synthétiques. La version mm_schema=1
est conservée ; p2_schema=1 marque séparément l’extension.

Les acteurs sont distincts des propriétaires : `Principal.name` reste le
propriétaire logique pour les ACL, `actor_id` identifie le client serveur.
Les nouvelles approbations utilisent cet acteur et un rôle human_approver.
Une action contient une empreinte, une expiration et un identifiant natif exact.
La file stocke payload figé, identifiant Hermes, tentatives et bail.
Les jobs LLM stockent entrée/provenance, sortie avant application, métriques,
réservations et état. Les enfants partagent leur budget racine.
L’ingress de confiance peut préciser observed_at par candidat (date inférieure
ou égale à celle de son lot source), afin qu’une extraction multi-événements ne
rajeunisse pas les faits anciens. Ce champ n’est pas ouvert aux propositions HTTP.

Voir [rapport de phase 2](JARVIS_2_PHASE2_REPORT.md) pour le périmètre réellement testé.

DDL exécutable : `memory_manager/schema.sql`. Version 1, dédiée à une **nouvelle**
base expérimentale. Aucun ALTER, remplacement ou ouverture en écriture des bases
réelles. `CREATE IF NOT EXISTS` est répétable. `Memory(..., create=True)` utilise
une création exclusive et refuse même un fichier existant vide. Une ouverture
normale exige le marqueur `mm_schema=1` ; aucun upgrade implicite.

## Modèle canonique

| Table | Rôle et champs essentiels |
|---|---|
| mm_events | UUID, owner, scope, event_key unique par owner/scope, empreinte du payload, source JSON, created |
| mm_memories | UUID stable, owner, scope, current_revision |
| mm_revisions | UUID de version, memory_id, parent, event_id, type, subject, predicate, content JSON, observed, valid_from/to, confidence, status, created |
| mm_relations | source/target = UUID de révisions, kind = supports, analogy, depends_on ou corrects |
| mm_fts | index FTS5 des révisions ; seuls les pointeurs actifs et accessibles sont recherchés |
| mm_audit | séquence, actor, action, memory_id, before_revision, after_revision, event_id, created |
| mm_jobs | owner/scope, kind, clé événement, état, curseur, snapshot, résultats, tentatives, limites, timestamps |
| mm_missions | identité, owner/scope, clé événement, état, définition JSON, timestamps |
| mm_mission_events | séquence, mission, état, acteur, preuve JSON, timestamp |
| mm_schema | version et date d’application |

Les dates sont des secondes UTC Unix ; les API futures peuvent offrir ISO8601
en façade. `observed` est la date de la source ; `created` est la date de stockage.
La validité métier est l’intervalle `[valid_from, valid_to)`. Les content sont
des objets JSON bornés. `subject` identifie le système/projet ; `predicate`
identifie la propriété dont deux valeurs peuvent se contredire.

`source` conserve au minimum `kind`, `ref`, `observed_at` ; les sources vérifiées
incluent `evidence`, référence à un échantillon/test conservé par l’ingress.
Le déploiement doit fixer les références immuables et leurs empreintes, et ne
pas se limiter à une page web susceptible de changer.

## Types et états

- identity : identité et préférences.
- knowledge : connaissances techniques et faits.
- episode : mission, expérience et outcome structuré.
- project : état, décision ou plan.
- skill : référence à une version Git et à son évaluation.
- lesson : erreur, correction ou leçon.

États stockés : observed, inferred, user_confirmed, verified, disputed,
superseded. `superseded` est exposé pour les anciennes versions ; l’ingress ne
peut pas créer une nouvelle connaissance déjà superseded. Une contradiction
entre valeurs acceptées produit `effective_status=disputed` sans réécrire les
versions ni choisir une source. La source utilisateur conserve le sens
« déclaration attribuée », jamais « vérification indépendante ».

L’historique n’a pas de purge. Des triggers refusent UPDATE/DELETE sur les
révisions, sources, audits et événements de mission. Le compte service qui
peut écrire le fichier SQLite n’est pas considéré comme adversaire confiné :
les permissions OS et sauvegardes restent nécessaires.

## Correction et annulation

Une correction contient `correction_of` (UUID stable) et `expected_revision`.
Même sujet, prédicat, type, propriétaire et périmètre requis. Une transaction
BEGIN IMMEDIATE ajoute la source, la révision, les relations, le FTS, l’audit
et déplace le pointeur actif. Une erreur annule tout le lot. Une clé rejouée
avec même payload renvoie les mêmes identifiants ; un payload différent avec
la même clé est refusé.

`undo` ajoute une révision compensatrice fondée sur la source précédente,
avec `undo_of`. Le journal des changements n’est pas effacé. Une branche
concurrente doit relire la nouvelle révision avant de corriger.

## Droits et recherche

`private` exige owner=principal.name. Un scope partagé n’est lisible que si le
principal serveur le possède. L’écriture/correction reste au propriétaire ;
la gouvernance de modifications collectives est à décider avant déploiement.
Les relations inter-scopes sont refusées pour éviter des liens révélant un
souvenir privé. Aucun outil modèle ne choisit son principal ou ses rôles.

FTS5 filtre ACL et révision active ; la recherche fusionne les rangs textuels
et vectoriels de type RRF. Les hits vectoriels périmés/inaccessibles sont
écartés. Une priorité par statut précède le score puis la date d’observation.
Les filtres type/sujet et validité s’appliquent aux contenus canoniques.
Le paramètre interne `at` filtre la validité des révisions actuellement actives :
ce n’est pas une requête bitemporelle historique complète. Pour l’ancien plan,
utiliser `history`, qui donne sources et révisions superseded.

## Migration et retour arrière

Pour une future version : snapshot SQLite via API backup, integrity_check,
empreinte et restauration d’essai avant DDL transactionnel additif ; insérer la
version seulement après succès. Ne pas recopier le fichier principal sans WAL.
La fonction `snapshot` crée sa destination exclusivement et fournit intégrité,
empreinte SHA256 et liste des tables. Son test rouvre la sauvegarde et recherche
un fait synthétique. Elle n’a été exécutée que sur des bases synthétiques.
Pour ce socle, le rollback applicatif consiste à ne plus appeler le nouveau
service, tout en conservant sa base et tous les anciens magasins JARVIS.
