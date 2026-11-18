# Phase 6B — Résultat et décisions restantes

## Réalisé dans le worktree

- Chemin hybride actif audité, écart Live natif confirmé et contourné sans changer
  le moteur de production.
- Admission serveur du seul template DoseLab par le vrai `/ask`, avec rôle humain,
  espace, idempotence, quotas existants et absence de contexte libre vers Hermes.
- Refus Hermes sans recours au classificateur ni aux permissions Codex.
- Réouverture contrôlée de `/ask` et des capacités navigateur après authentification;
  aucun accès physique ajouté. Reprise du chargeur vocal après connexion.
- Panneau existant conservé, admission non bloquante, résultats et provenance.
- Patch minimal de **15 chemins**, préparé en quatre étapes; application et retour
  arrière répétés sur copie. Aucune application de production.

**Validation : 25 commandes réussies**, préflight de 24 contrôles réussi.
Admission locale observée : 36 ms dans le banc d’évaluation, 48 ms sur la copie
assemblée avec le patch minimal; ces durées ne mesurent pas Hermes ou le GPU.
Les résultats détaillés sont dans `JARVIS_2_PHASE6B_TEST_RESULTS.json`. Le préflight
local est distinct des preuves réelles C1/phase 5, conservées sans modification.
Les verdicts historiques ne sont pas recalculés.

## Autorisations à examiner

| Bloc | Autorisation demandée | Effets et ressources | Arrêt / restauration |
|---|---|---|---|
| P6-L1 | Un essai panneau avec vrai Hermes/Ollama existant Windows et mémoire synthétique | Runtime temporaire, tunnels privés, RTX selon gardiens; 1 mission, 5 min, 6 appels, 98 304 tokens, 0 CHF distant | Annulation, arrêt des seuls Jobs/processus labo, état initial vérifié; aucune modification gateway |
| P6-L2 | Après L1, un essai du vrai `/ask` sur copie Jarvis avec texte de transcription synthétique | Même enveloppe, une mission distincte; preuve serveur/bridge/runtime/UI; Google et Codex non appelés | Même procédure; aucun rejeu ambigu |

La procédure complète est dans `JARVIS_2_PHASE6_PREFLIGHT.md`. Ces deux blocs ne
sont **pas autorisés par la demande de préparation** et n'ont pas démarré. Les
quotas sont par bloc, sans réessai automatique. Autoriser L1 ne vaut pas accord L2.

Aucun accord de production n'est demandé à ce stade. Il reste nécessaire de
vérifier sur copie minimale les autres fonctions historiques, les rôles exacts des
comptes et les limites du worker Codex existant. Le wrapper sécurise les routes,
mais ne transforme pas ce worker privilégié en bac à sable multi-utilisateur.
L'import/sync, le développement legacy et les cibles physiques sont encore fermés
sous ce wrapper. Ne pas l'activer globalement sur Jarvis avant cette revue.

## Ce qui reste non démontré par la phase 6B

- Jonction complète navigateur → copie minimale de Jarvis → vrai Hermes Windows.
- Nouvelle mesure GPU/VRAM/Kryptex et latence du runtime pour ce pilote.
- Conversation micro réelle avec authentification, sans régression perceptible.
- Déploiement gateway, service Windows permanent ou mémoire personnelle.

L'étape suivante utile est P6-L1, puis P6-L2. Aucun nouveau modèle, composant mémoire,
entraînement, VM Hermes ou essai C1 n'est nécessaire pour ces validations.

## Mise à jour du 15 novembre 2026 — P6-L1 terminé

Après accord distinct, P6-L1 a réellement réussi : panneau → bridge/SQLite →
Hermes Windows → Qwen RTX → MCP → résultat et expérience persistants → panneau.
Une mission, trois appels, 13 453 tokens, environ 68 secondes, 0 CHF distant;
processus et tunnels du laboratoire arrêtés, production inchangée.
Voir `JARVIS_2_PHASE6B_P6_L1_RESULTS.md` et la preuve JSON horodatée associée.
Une erreur de date est signalée séparément : intégration réussie ne vaut pas
validation factuelle de tout le texte. Aucun résultat promu automatiquement.
**P6-L2 demeure non autorisé**, aucune preuve vocale /ask ou microphone nouvelle.

## Mise à jour du 15 novembre 2026 — P6-L2 terminé

Après autorisation distincte, le véritable chemin `/ask` de la copie isolée a admis
une mission en 80 ms et transmis son résultat Hermes Windows/RTX au panneau.
Une mission, trois appels, 13 470 tokens, 50 secondes, 0 CHF distant. Compteurs
fournisseur inchangés pour l’admission; deux routages ordinaires testés en simulation.
Voir `JARVIS_2_PHASE6B_P6_L2_RESULTS.md` et les preuves brute/qualité associées.
Les processus du laboratoire sont arrêtés et la gateway active est inchangée.
Les timestamps restitués sont conformes à SQLite dans cet essai; la réserve de date
P6-L1 reste conservée. Les résultats restent des récits non vérifiés automatiquement.
Aucun essai micro ou déploiement production n’est inclus. Les deux pilotes sont clos.

## Actualisation phase 6C

Voir `JARVIS_2_PHASE6C_DEPLOYMENT_READINESS.md` : préparation locale renforcée ; activation production NO-GO tant que la sécurité globale des routes et la compatibilité ne sont pas achevées. Pilotes L1/L2 clos, sans répétition.

## Sécurisation phase 6D

Voir `JARVIS_2_PHASE6D_SECURITY_READINESS.md` et `phase6d/ROUTE_MATRIX.md`. Politique centrale, client de session autonome, propriété vocale, reçus canoniques et heartbeat développés/testés hors production. Activation toujours NO-GO tant que les adaptateurs métier et l’isolation effective du worker ne sont pas raccordés. Pas de nouveau pilote GPU nécessaire.

## Finalisation 6D — résultats complémentaires

Voir `JARVIS_2_PHASE6D_FINAL_REPORT.md`. Adaptateurs métier, broker Unix, namespace réel testé et composition Hermes raccordée en laboratoire. Les verdicts de production restent réservés aux connecteurs réels, identités OS et entrée gateway. Aucun pilote Hermes à relancer.
