# JARVIS 2.0 — Bilan final de la phase 5

## Décision de clôture technique

Le socle expérimental mémoire/Hermes de phase 5 est validé sur le scénario strict
synthétique C1, accepté par l'utilisateur. **C1 est clos : aucun nouvel essai C1.**
La mémoire personnelle n'est pas importée et l'intégration à la gateway n'est pas
activée. La clôture technique ne transforme pas ces étapes exclues en succès.

Architecture conservée : Gemini Live pour la voix ; Hermes Windows natif pour les
missions ; Ollama/Qwen3.5:4b sur RTX 3080 ; bridge, Memory Manager et SQLite sur
Proxmox ; Qdrant index reconstructible. Pas de VM Hermes supplémentaire à réserver,
pas de changement de RAM, balloon ou shares. VM102 conservée comme référence,
aucune intervention sur son état pendant cette clôture.

Ce bilan s'appuie sur les rapports et preuves déjà conservés. Aucun service réel,
GPU, base personnelle ou gateway n'a été relancé pour le rédiger.

## Ce qui a été réellement validé

| Bloc | Validation réelle et portée | Preuves |
|---|---|---|
| A1 sauvegarde | Snapshot Qdrant 168 229 376 octets ; restauration isolée 41 428 points, SHA vérifié ; instance de vérification arrêtée | `JARVIS_2_PHASE5_A1_RESULTS.md` |
| A2 vecteurs | Service existant d'embeddings multilingues 384 dimensions, identité dédiée, collection expérimentale, références revalidées SQLite, réindexation/reprise/masquage logique sur fixtures | `JARVIS_2_PHASE5_A2_RESULTS.md` |
| Hermes Windows | Runtime natif officiel épinglé `4959268e312a21a361f248e49030d5f5df3984d5`, MCP contrôlé, Ollama/Qwen/RTX réels, aucune mémoire factuelle concurrente | `JARVIS_2_PHASE4_REPORT.md` et rapports B/B2 |
| Compétence | `doselab_freshness` candidate proposée sur expérience synthétique, évaluée par l'hôte 3 puis 16 cas ; même candidate retrouvée après redémarrage des processus Hermes | `JARVIS_2_PHASE5_B2_RESULTS.md` |
| Unicode | Reconfiguration stricte UTF-8 et conservation des arguments/retours sous Windows ; roundtrip MCP réel avec HTTP simulé, accents et Unicode testés hors ligne | `JARVIS_2_PHASE5C_UNICODE_WINDOWS_REAL.json` |
| C1 strict | Recherche réellement effectuée par Hermes, zéro FTS, vecteurs réels, référence actuelle canonique, historique avec vrai memory_id, sources explicites, sortie et expérience persistantes après arrêt | `JARVIS_2_PHASE5C_C1_THIRD_RESULTS.md` |

Le troisième C1 a utilisé **3 appels, 12 853 tokens, 56 secondes, 0 CHF**. La réponse
cite `synthetic://doselab/correction` et `synthetic://doselab/old`. Tous les critères
stricts et le contrôle supplémentaire du memory_id sont vrais ; `passed=true` pour
**ce seul nouveau rapport**. Les Jobs Hermes/Ollama et tunnels possédés sont arrêtés,
ports Windows/contrôleur fermés, résultat relu dans une nouvelle connexion SQLite.
Aucune publication de compétence ni action physique dans ces pilotes.

La collection historique `jarvis_memory_v1` n'a pas reçu les points du prototype,
aucun prune global exécuté. Les mesures de comptage rapportées sont historiques,
pas un nouvel inventaire de la production à la date de ce bilan.

## Verdicts historiques conservés

- B2 : trois missions réussies, mais `passed=false` global parce que la condition
  zéro FTS n'était pas obtenue par la requête réellement choisie par Hermes.
- Premier C1 : `passed=false`, lecteur refusé par une seconde liste d'outils avant
  dispatch modèle. Correctif local du relais préparé puis exercé avec nouvel accord.
- Deuxième C1 : `passed=false`, recherche sémantique réelle acquise, source exacte
  omise en sortie et URI de source passée à l'historique. La cause a été confirmée
  ensuite depuis la seule session synthétique en lecture seule, pas supposée depuis
  le message d'erreur générique.
- Troisième C1 : succès strict, nouveau run et nouveau fichier de preuve ; aucune
  réécriture des anciens verdicts ni assouplissement de leurs critères.

## Données synthétiques et simulations : distinction essentielle

Les missions réelles ci-dessus utilisent des **données synthétiques** DoseLab :
elles prouvent l'exécution runtime/GPU/MCP/services, pas la compréhension d'un
projet personnel effectivement installé. Une déclaration de fixture confirmée ne
constitue pas une mesure indépendante de matériel.

Les régressions Python/Node et évaluations de refus utilisent fixtures, faux modèles
et faux endpoints selon les groupes. L'interruption de l'indexeur A2 était une
exception contrôlée après une écriture distante réelle ; pas un arrêt brutal CT.
Les redémarrages de compétence sont ceux des processus Hermes, pas du PC Windows.
La persistance de C1 est une réouverture SQLite après arrêt du laboratoire, pas un
nouveau cycle d'inférence. Aucun test de longue durée ou de charge multi-utilisateur
ne permet d'extrapoler une fiabilité générale.

Les deux échecs de sécurité antérieurs de Qwen 4B restent des limitations réelles.
Les succès ciblés ne rendent pas le modèle autorité de permissions, de faits ou de
publication. Les contrôles sont imposés hors modèle, par services, rôles, outils et
budgets. Aucun nouvel examen GPU de sécurité exécuté pour cette clôture.

## C2 : incident conservé et suite explicitement bornée

L'ancien lecteur a compté dix-huit documents multi-tours au lieu des tours prévus.
Le respect de vingt tours n'est donc pas démontré. Rapport privé **bloqué** pour
import/transmission, origine des données inchangée, réserve conservée. Aucun contenu
privé n'avait été envoyé à un modèle ; aucune correction de rapport ne rend cette
lecture rétroactivement conforme.

Le nouvel inventaire autorisé ne lit que des métadonnées : trois documents
(ChatGPT 1, Codex 2), aucun tour normalisé exact déductible du précédent filtre
par titre. Ce résultat ne prouve pas l'absence de discussions pertinentes dans les
corps non lus. Catalogue privé local, aucun ID/titre/extrait personnel dans Git.

La procédure de découpage repose sur les formats structurés d'origine, pas sur
les marqueurs textuels ambigus des documents aplatis. Le noyau de planification
métadonnées est testé hors ligne, sans accès personnel. L'ouverture des exports,
la présentation d'un manifeste de vingt tours maximum, puis la lecture de ce lot
requièrent des accords distincts. Détails : `JARVIS_2_PHASE5_C2_SEGMENTATION_PLAN.md`.
Aucun import à blanc supplémentaire, import canonique ou transmission implicite.

## Éléments non activés et risques restants

- Raccordement gateway/interface Jarvis, notifications vocales et API d'approbation
  côté interface non activés ; authentification de toutes les anciennes routes et
  ACL de production non démontrées par les modules expérimentaux.
- Publication automatique absente ; promotion de compétence et canal humain restent
  distincts. Une candidate et 16 fixtures ne démontrent pas une procédure physique
  sûre ou généralisable, ni un entraînement automatique des poids du modèle.
- Worker Codex de production non réutilisé pour autonomie ; shell, Home Assistant,
  minage, équipements électriques, pompes et chauffage hors des outils Hermes.
- Isolation Windows : compte standard/Job Object et restrictions existantes ; pas
  une sandbox parfaite. Démarrage permanent non activé, arrêt PC en pleine mission
  réelle et fiabilité après panne réseau prolongée encore non validés matériellement.
- Snapshot encore sur le stockage de CT205 ; copie HDD/chiffrement externe C5
  non autorisés. Plan de chiffrement avant sortie et clés privées hors Proxmox
  conservé, aucune clé générée ni sauvegarde transférée. HDD du même hôte ne
  constituerait pas à lui seul une protection contre perte de l'hôte.
- Marge mémoire CT205 mesurée lors d'A2 limitée ; aucun dimensionnement/changement
  de RAM ni déploiement supplémentaire implicitement autorisé.
- Statistiques GPU échantillonnées, pas de bilan énergétique intégré, pas de
  comparaison complète avec un modèle supérieur. Aucune dépense API supplémentaire.

## Passage à la phase 6

Le développement isolé prépare transport privé, authentification serveur, ACL par
route/espace, admissions asynchrones, événements/notifications, flag et rollback.
Il réutilise bridge, missions, worker de disponibilité, budgets, mémoire et
approbations existants : aucune deuxième implémentation de leur source canonique.

Le test phase 6 utilise HTTP/SQLite **réels locaux** sur fixtures sans appeler
Hermes, Ollama, Gemini, Home Assistant ou Qdrant de production. Ce n'est pas encore
l'intégration de Jarvis réel. Les mutations et routes vocales restent un jalon de
revue explicite avant montage du patch. Voir `JARVIS_2_PHASE6_PLAN.md`.

Restrictions inchangées : C3/C4/C5/C6 non autorisés, pas de lecture personnelle
nouvelle, aucun déploiement gateway, pas de publication, physique ou fournisseur
payant automatique. Budget API distant supplémentaire **0 CHF**.

## Vérification de préparation

`python3 scripts/evaluate_memory.py --phase6` : **19 commandes réussies**,
preuves séparées dans `JARVIS_2_PHASE6_TEST_RESULTS.json`. Les vérifications
complémentaires du contrat de dates et du wrapper passent aussi après les derniers
ajustements. Aucun nouvel essai C1, appel GPU ou effet sur la production.
