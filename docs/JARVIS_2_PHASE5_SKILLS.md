# Phase 5 — Compétences candidates et évaluation

## Référence conservée

La phase 4 a réellement créé, évalué (3 cas) et retrouvé après redémarrage natif
Windows `doselab_freshness` v1, empreinte
`40286db0d673703ad9ccb9b857801bad7c143f8512c303bfa3da942fe2348273`.
Ses preuves sont conservées dans les rapports `JARVIS_2_PHASE4_*_REAL.json`.
La définition réellement enregistrée dans le snapshot synthétique phase 4 a été
relue avec SQLite `mode=ro/query_only` et évaluée hors ligne sur les **16 cas : 16/16**.
Preuve : `JARVIS_2_PHASE5_SKILL_EVALUATION_REAL_CANDIDATE.json`. Son empreinte
correspond à celle de phase 4. Aucun appel Hermes/GPU ni changement de statut ;
cela évalue la procédure et son enveloppe, pas une nouvelle mission du modèle.
Cette compétence demeure **candidate**, déclarative, sans script et sans publication
native `SKILL.md`. Aucune modification de cette base de laboratoire antérieure.

## Évaluation élargie livrée

`memory_manager/phase5/skills.py` réutilise le DSL et les contrôles du registre
existant. La suite externe contient **16 cas** : seuil nominal/limite, débit absent,
donnée totalement absente, fraîcheur absente/fausse/string, débit booléen/négatif/
non fini, sources contradictoires, révision remplacée, source non acceptée et
réutilisation hors de la procédure prévue. Aucun cas ne commande un équipement.

Le modèle n'écrit ni les résultats attendus ni les contextes de validation. Le
contexte de source est fourni par l'hôte : un texte « fresh=true » ne suffit pas à
établir la validité canonique. Les décisions restent `report_only` ou
`request_human_review`. La variante supprimant le contrôle de fraîcheur est détectée
comme une régression. Les définitions avec outils shell/physiques sont refusées par
le registre avant évaluation.

Ces cas étendent la vérification de la **procédure déclarative et de son enveloppe**.
Ils ne démontrent pas que Qwen extrait correctement des paramètres arbitraires,
ni qu'un modèle résiste seul à l'injection. Le corpus réel doit ajouter des missions
avec paraphrases et données manquantes à partir de sources synthétiques.

## Préparation de publication sans activation

`prepare_release(memory, reviewer, name, version)` exige une identité reviewer
indépendante du proposant, relit les sources canoniques et leurs révisions acceptées,
rejoue la suite étendue et produit un manifeste lié à l'empreinte de définition,
aux sources et à la suite. Champs explicites :
`state=prepared_for_review`, `publication_authorized=false`,
`execution_authorized=false`, `runtime=host-declarative-v1`.

Le manifeste ne modifie aucune table de publication ni aucun pointeur actif. Il
n'ajoute pas d'outil MCP de publication. Une correction ultérieure d'une source
invalide sa préparation. Les versions du registre sont immuables par empreinte.

Le registre historique possède déjà une publication humaine et un rollback, avec
réévaluation des trois cas initiaux. **La suite étendue de phase 5 n'est pas encore
une condition obligatoire de cette ancienne fonction** : aucun endpoint ou outil
Hermes ne l'expose, mais avant toute activation il faudra lier le manifeste étendu
à la transaction humaine de publication, comparer la version active sur le même
corpus, enregistrer l'approbation et invalider tout manifeste périmé.

Le futur paquet exécutable devra conserver : version/fingerprint immuables,
manifestes d'évaluation et d'autorisation indépendants, sources vérifiables, signature
ou empreinte de l'artefact, sélection active séparée de la définition. Le rollback
ne pourra choisir qu'une ancienne version publiée dont les sources et tests sont
encore valides. Aucun `SKILL.md` ne doit pouvoir élargir les outils autorisés.
L'export natif et le chargement automatique restent désactivés/non livrés.

## Persistance testée dans cette phase

La simulation de bout en bout utilise une nouvelle base SQLite synthétique,
l'API HTTP réelle locale, le registre réel, un agent émulé et des vecteurs constants :
admission → récupération → proposition → évaluation → résultat d'expérience →
état completed → fermeture/réouverture → nouvelle mission distincte.
Une vérification dans un **nouveau processus Python** retrouve la compétence
candidate et l'expérience. Cela ne constitue pas un redémarrage Windows/Hermes.

Le nouvel essai Windows à autoriser utilisera une nouvelle fenêtre, une nouvelle
base synthétique et de nouveaux identifiants ; jamais l'ancienne mission ambiguë.
Hermes devra retrouver une paraphrase via le vrai Qdrant, citer la révision/source,
proposer une compétence évaluée par l'hôte, puis la retrouver après arrêt complet.
La version reste candidate pendant tout l'essai.

## Pilote B prêt à autoriser

Le nouvel adaptateur injecte l'évaluation étendue dans le cycle natif existant,
avec base synthétique neuve, budget partagé 50 000 tokens et fenêtre 16 appels /
3 missions / 20 minutes. Il doit retrouver une expérience enregistrée et la même
compétence candidate après redémarrage du runtime. Ces branches sont testées
localement ; elles ne constituent pas un nouvel essai Hermes réel.
A2 a validé le stockage/retrieval sémantique, sans aucune nouvelle proposition
par Hermes. La compétence phase 4 demeure inchangée et candidate.
Plan : `JARVIS_2_PHASE5_B_TRIAL_PLAN.md`. Aucune publication ne sera exposée au modèle.

## Mise à jour après essai B autorisé

Hermes/Ollama ont démarré temporairement puis ont été arrêtés proprement. Le relais
a refusé la première inférence : réserve 64 000 incompatible avec plafond 50 000.
Aucun token génératif ni apprentissage nouveau ; cinq points synthétiques indexés
avant cette étape portent la collection expérimentale à onze points. Les bases
précédentes et la collection historique ne sont pas modifiées par ce pilote.
Le précontrôle de quota refuse maintenant cette incompatibilité avant démarrage.
Une enveloppe B2 à 98 304 tokens partagés est préparée, **non autorisée et non
exécutée**. Voir `JARVIS_2_PHASE5_B_RESULTS.md` pour les preuves et limites.

## Résultat B2 réel après nouvel accord

Trois missions natives Windows réussies, 8 appels Qwen/RTX, 37 918 tokens sur
un budget partagé 98 304 : correction avec historique et sources, compétence
candidate évaluée 3/3 et 16/16, récupération après redémarrage du runtime et retour
d'expériences de missions antérieures. Aucun élément publié. Jobs et tunnels
arrêtés, fenêtre fermée, données synthétiques conservées ; 16 points expérimentaux.

Le verdict strict du lanceur reste en échec car la requête Hermes avait aussi des
hits FTS. Le contrôle hôte séparé avec filtre knowledge réussit sans FTS. Aucune
validation sur données personnelles ni déploiement. Quelques arguments d'outils
présentent un encodage d'accents à diagnostiquer. Les garanties indépendantes de
permissions/publication restent en place ; aucune amélioration intrinsèque de la
résistance de Qwen aux injections n'est déduite de ce succès guidé.
Preuves et limites : `JARVIS_2_PHASE5_B2_RESULTS.md`.
