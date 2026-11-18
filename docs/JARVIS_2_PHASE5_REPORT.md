# JARVIS 2.0 — Rapport phase 5

14 novembre 2026. Branche `codex/jarvis-2-memory-20261113`, worktree isolé.
**A1 et A2 validés. B2 : trois missions réelles réussies ; critère strict zéro FTS
non atteint par Hermes, verdict global du lanceur conservé en échec.**
Les acquis Windows de phase 4 restent conservés. Démarrages temporaires B terminés et arrêt vérifié ; aucun import personnel ni
raccordement à la gateway active.

## Résultat concret

Le Memory Manager utilise désormais les vrais embeddings MiniLM/384 et Qdrant
expérimental, avec SQLite canonique, FTS5, contrôle des révisions et des droits.
Le service d'embeddings CT205 a été étendu après accord A2 ; aucun logiciel ou
modèle installé. Son redémarrage contrôlé a réussi. La collection expérimentale
contenait **6 points synthétiques** après A2, puis **11** après B et **16** après B2. `jarvis_memory_v1` conserve **41 428 points**,
sa configuration et ses index ; Qdrant principal conserve son PID 11122.

Le code livré inclut indexeur versionné/reprenable, recherche hybride, API/MCP
facultative, import à blanc, évaluation de compétences et adaptateur Jarvis inactif.
Un pilote Windows dédié réutilise le cycle de vie phase 4 avec une nouvelle base,
un budget partagé et des preuves de recherche sémantique et d'expérience.
**Premier essai B bloqué sur budget ; B2 a ensuite réussi les trois missions.**
La recherche était hybride : le critère plus fort zéro FTS reste non démontré par
Hermes. Détails et preuves dans `JARVIS_2_PHASE5_B2_RESULTS.md`.

## Validations réelles A1 et A2

A1 : snapshot privé de **168 229 376 octets**, SHA256 vérifié, restauration isolée
Qdrant 1.20.0, comptage exact 41 428 et authentification vérifiés, instance arrêtée.
Le plafond cgroup de 256 Mio a été sollicité ; aucun OOM observé. Deux défauts de
lancement corrigés restent tracés. La sauvegarde demeure dans CT205 ; pas de copie
hors hôte. Voir `JARVIS_2_PHASE5_A1_RESULTS.md`.

A2 : endpoint `/v1/embeddings` authentifié séparément, pipeline épinglé et hors
ligne, réutilisation de l'instance FastEmbed existante ; démarrage sans PUT historique.
Source et configuration sauvegardés, contrôles root protégés, aucun gardien A2 actif.
Déploiement total **6,47 s**, durée d'indisponibilité HTTP non mesurée séparément.

- **12/12 contrôles réels synthétiques** : index, reprise après exception au point
  d'accusé distant, IDs stables, historique, correction, ACL, références périmées,
  masquage réversible, reconstruction et relecture depuis une nouvelle connexion.
- « masse nominale identique » : **0 résultat FTS**, configuration actuelle
  quatre cellules de 1 kg retrouvée au rang 1 par les vrais vecteurs.
- **11/11 sondes HTTP de sécurité** : séparation des identités, schéma, contexte,
  refus de champs de permission et vecteurs 384D cohérents.
- Latence HTTP locale brute : **8,683–9,201 ms**, trois appels de 11 tokens.
  Ce petit échantillon ne mesure ni le tunnel ni un débit soutenu.
- Après essai : RSS embeddings **886,84 Mio**, cgroup **935,44 Mio**, mémoire CT
  disponible **616,49 Mio**. Pas de RSS initial comparable ni mesure d'énergie.

Le corpus est très petit ; deux distracteurs restent retournés. Aucun seuil de
pertinence général n'est revendiqué. L'interruption est une exception contrôlée
après une vraie écriture, pas un arrêt OS/CT. Le retour arrière automatique du
service est préparé mais n'a pas été déclenché réellement.
Preuves : `JARVIS_2_PHASE5_A2_REAL.json`, détails `JARVIS_2_PHASE5_A2_RESULTS.md`.

## Tests locaux

Commande : `python3 scripts/evaluate_memory.py --phase5`.
La preuve `JARVIS_2_PHASE5_TEST_RESULTS.json` distingue ces tests locaux des essais CT205.

| Groupe | Résultat |
|---|---|
| Memory Manager phase 1 | 20/20 |
| phase 2 | 30/30 |
| phase 3 et dimensionnement archivé | 49/49 |
| contrats Windows phase 4 | 17/17 |
| phase 5, déploiement A1/A2 et préparation B | 38/38 |
| adaptateur Node 18 et régressions applicatives | réussite |

Les simulations emploient SQLite/HTTP réels, agents émulés et vecteurs constants.
Elles ne prouvent pas un nouvel apprentissage GPU. Les tests Home Assistant
n'exécutent aucune action physique. Les deux sorties dangereuses Qwen sont refusées
par les contrôles externes ; aucune amélioration intrinsèque du modèle revendiquée.
La compétence phase 4 conservée a réussi hors ligne **16/16 cas étendus**, sans
changement de statut : toujours candidate, aucune publication.

## Suite et autorisations distinctes

**B — Autorisé, exécuté, échec propre.** Une mission admise, une tentative au relais,
0 token génératif : réserve 64 000 > plafond partagé 50 000. Aucun outil mémoire
appelé par Hermes ni compétence créée. Runtime Hermes/Ollama et tunnels arrêtés,
fenêtre fermée. Les précontrôles ont été corrigés pour vérifier l'archive réellement
installée, sans exiger un Git absent. Voir `JARVIS_2_PHASE5_B_RESULTS.md` et ses preuves.

**B2 — Autorisé et terminé.** 3/3 missions réussies : correction sourcée, compétence
candidate évaluée 3/3 et 16/16, récupération après redémarrage du runtime et retour
d'épisodes des missions précédentes. **8 appels, 37 918 tokens**, budget partagé
98 304, coût distant 0 CHF ; tous les Jobs/tunnels arrêtés et fenêtre fermée.
Aucune publication ni import personnel.

Le verdict strict reste `passed=false` : Hermes a ajouté des mots à sa requête,
qui a obtenu aussi des hits FTS. Le contrôle hôte ultérieur avec filtre knowledge
retrouve la bonne configuration au rang 1 sans FTS ; il est distinct de la mission.
L'apprentissage démontré est guidé sur données synthétiques ; pas une autonomie
générale. Encodage d'accents dans certains outils à diagnostiquer avant import.
Voir `JARVIS_2_PHASE5_B2_RESULTS.md`. Aucun nouvel essai automatiquement autorisé.

**C — Non autorisé.** Choisir une personne/un projet, maximum 20 sources, rapport
personnel à blanc privé. Autorisations séparées pour lecture de contenu, traitement
local Windows et éventuelle ingestion. Aucun import massif.

**D — Non proposé à l'exécution.** Authentification/ACL legacy et montage gateway
à revoir sur copie avant toute demande de déploiement. Gemini Live, gateway et HA
restent inchangés ; aucune réservation RAM Proxmox pour Hermes.

## Risques et limites restants

Sauvegarde encore locale CT205 ; clé Qdrant hôte à large portée ; anciennes routes
Jarvis sans ACL fortes démontrées ; aucune nouvelle intégration de production.
L'identité root SSH du contrôleur n'est jamais donnée à Hermes, mais reste un
privilège du composant de confiance. Pas de publication native de compétence ni
promotion autonome de faits. L'intégration de la suite étendue à la transaction de
publication humaine reste à terminer avant activation.

Documents : `JARVIS_2_PHASE5_MEMORY_PLAN.md`, `JARVIS_2_PHASE5_QDRANT.md`,
`JARVIS_2_PHASE5_SKILLS.md`, `JARVIS_2_PHASE5_SECURITY.md`.

Le cycle réel avec mémoire hybride et compétence candidate est démontré sur données
synthétiques. Son isolation sémantique seule par Hermes et la fiabilité sur mémoire
personnelle restent à qualifier ; les preuves phase 4 demeurent conservées.

## Préparation phase 5C — sans nouvelle intervention de production

Correctif Unicode à la frontière MCP et environnement enfant préparés localement,
lecteur knowledge filtré et lanceur sémantique à mission unique testés hors ligne ;
rapport personnel borné à vingt sources et authentification serveur opaque préparés.
Audit disque réel : HDD `/mnt/hdd` distinct du NVMe de CT205, copie possible mais
non autorisée/transférée. Aucune conversation privée consultée ni nouvelle mission
GPU exécutée. Plan et accords distincts : `JARVIS_2_PHASE5C_PLAN.md`.
Les preuves et le verdict historique B2 restent inchangés.

## Exécution phase 5C — C1/C2 autorisés séparément

Patch Windows et test Unicode réels réussis, mais unique mission synthétique
refusée avant modèle par une liste d'outils secondaire du relais. Correctif local
et test préparés ; aucun nouvel essai. C2 a lu 18 documents sans imposer la borne
par tours des conversations : **rapport bloqué, conformité non démontrée**. Aucun
contenu personnel aux modèles, aucun import/index privé, aucune modification de
base source ou gateway. C5 reporté avec proposition de chiffrement.
Voir `JARVIS_2_PHASE5C_RESULTS.md`. Verdict B2 historique inchangé.

## Mise à jour — deuxième essai C1 autorisé

Un nouvel accord explicite a permis un essai réel distinct (20:35:58–20:36:51 UTC).
Hermes a bien appelé le lecteur filtré, obtenu zéro correspondance FTS et une
connaissance vectorielle actuelle revalidée dans SQLite. Il n'a pas cité sa
source exacte et son accès à l'historique a échoué : **`passed=false` maintenu**.
Deux appels, 7 604 tokens, aucun coût distant, laboratoire arrêté et ports fermés.
Correctif de consigne et régression préparés hors ligne, sans troisième essai.
C2 bloqué, C5 reporté, aucune nouvelle lecture personnelle ou action production.
Voir `JARVIS_2_PHASE5C_C1_RETRY_RESULTS.md`. B2 historique inchangé.

## Troisième C1 autorisé — succès réel du scénario strict

Le 14 novembre, 20:54:30–20:55:26 UTC, une seule nouvelle mission synthétique
a démontré zéro hit FTS, vecteurs réels revalidés SQLite, historique avec le bon
`memory_id`, citations exactes des deux sources, résultat durable après arrêt
des processus. **`passed=true` pour ce nouvel essai uniquement** ; anciens
verdicts B2/C1 conservés. Trois appels, 12 853 tokens, 0 CHF, ports fermés.
C2 : inventaire privé de métadonnées seulement, trois documents mais aucun tour
normalisé sélectionnable par ces métadonnées ; aucune lecture de contenu, ancien
rapport toujours bloqué. C3/C4/C5/C6 non autorisés, production inchangée.
Détail et limites : `JARVIS_2_PHASE5C_C1_THIRD_RESULTS.md`.

## Clôture technique de phase 5

C1 validé et clos par l’utilisateur, sans nouveau lancement. Bilan consolidé :
`JARVIS_2_PHASE5_FINAL_REPORT.md`. C2 reste en préparation locale sans lecture
supplémentaire de contenu ; procédure : `JARVIS_2_PHASE5_C2_SEGMENTATION_PLAN.md`.
Préparation du raccordement isolé, sans gateway : `JARVIS_2_PHASE6_PLAN.md`.
