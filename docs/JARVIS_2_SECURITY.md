# JARVIS 2 — Sécurité et limites

## Compléments de phase 2

Le nouveau broker vérifie rôle human_approver, acteur distinct, owner/scope,
empreinte et expiration. Le worker modèle n’a aucune API de validation ; la
consolidation ne crée que inferred. Les tokens API sont mappés à des acteurs
serveur, sans identité sélectionnable par requête. Le service reste loopback.
Un transport privé sans proxy/redirect refuse les origines publiques ; aucun
endpoint de téléchargement ou repli payant n’existe.

La sandbox bubblewrap est testée réellement : namespaces, HOME séparé, absence
du HOME hôte, réseau refusé, mounts système en lecture seule, workspace writable,
limites CPU/mémoire/fichier/sortie. Ce test ne vaut pas confinement d’un runtime
Hermes installé ; ce dernier reste bloqué avant revue et mise en place OS/réseau.
L’exécuteur doit recevoir un checkout jetable filtré, jamais un dossier de secrets.
La proposition Codex reste sans exécution et exige un budget approuvé distinct.

Budgets partagés réservés avant inférence, en SQLite : zéro coût distant par
défaut, plafond mensuel configurable jusqu’à 10 CHF par un budget_admin serveur,
enfants dans le même budget. Les erreurs à consommation inconnue gardent leur
réservation. GPU occupé/absent/fraîcheur inconnue suspend sans appel modèle.
L’arrêt du calcul distant après timeout HTTP reste à prouver sur le vrai serveur.
Les détails et limites supplémentaires sont dans le [rapport phase 2](JARVIS_2_PHASE2_REPORT.md).

## Résultat du pilote réel

Le modèle Windows existant a répondu `execute_physical:true` deux fois à une
fausse instruction externe. Aucun actionneur n’était connecté ; ce verdict
n’accorde aucun droit. Le test de régression vérifie les refus du broker mémoire
et de l’exécuteur OS face à cette sortie. Ne pas activer ce modèle avec des outils
physiques. Les 6/7 succès du petit banc ne prouvent pas sa sûreté générale.
Voir [les preuves et le nettoyage](JARVIS_2_PHASE2_GPU_PILOT.md).

## Frontières appliquées dans le prototype

1. Aucun import par la production, aucune commande HA, aucun appel de modèle distant,
   aucun chargement des secrets existants. Le nouveau magasin est initialisé
   dans un fichier inexistant uniquement ; l’audit utilise mode=ro.
2. `Principal` est une capacité fournie par le serveur. `private` contrôle le
   propriétaire ; les espaces partagés sont attribués par configuration serveur.
   Ni contenu, ni source externe, ni paramètre MCP ne modifie ces droits.
3. HTTP écoute 127.0.0.1 seulement. Bearer obligatoire, mapping par SHA256
   dans fichier privé ; aucune route de validation/correction privilégiée.
   Pas de CORS ni cookies d’authentification. Les logs HTTP détaillés sont coupés.
4. Une proposition HTTP reçoit le canal external et le statut inferred côté
   serveur ; tout champ de statut, correction ou identité est refusé. Les clés
   de rejeu divergentes échouent ; un lot invalide est entièrement annulé.
5. Seul l’ingress de confiance peut enregistrer observed/user_confirmed ;
   verified exige en plus validator, mesure/test et preuve. Les rôles privilégiés
   ne doivent jamais être confiés à un client modèle ni à un champ de requête.
6. FTS, historique et vector hits vérifient ACL et révision SQLite ; les relations
   ne traversent pas les périmètres. Sources et révisions sont conservées.
7. Une page malveillante est stockable comme donnée inferred, jamais exécutée.
   Aucun interpréteur de shell, commande physique, évaluation de code arbitraire
   ou outil de permission n’existe dans le MCP expérimental.
8. Les missions de laboratoire n’acceptent que mémoire consultative, proposition
   et rapport ; budget modèle/coût zéro. Le retour à queued après une demande
   d’approbation est fermé, y compris via pause/reprise. Aucune route humaine
   n’est simulée comme si elle existait.
9. Indexeur sans création, suppression ou prune ; préfixe expérimental imposé.
   Sans transport/embedding fourni explicitement par l’hôte, aucun accès réseau.
10. Rejet d’un ensemble de motifs de secrets à l’entrée. C’est un filet de
    protection, pas un détecteur universel ; l’ingress doit aussi minimiser les
    champs et exclure les configurations/secrets avant extraction.

## Isolation à réaliser avant exécution autonome

Le worktree protège le code utilisé par JARVIS ; ce n’est pas une sandbox de
sécurité. Le prototype et les tests locaux ont été exécutés comme l’utilisateur
de développement. Avant d’exécuter des compétences arbitraires : compte dédié,
conteneur/VM, aucun HOME réel, aucun socket système, aucun montage de secrets
ou de bases réelles, dépôt en lecture seule hors checkout de mission, réseau
filtré, ressources et sorties bornées, aucun sudo/systemctl de production.

Les approbations et le sandbox sont des mécanismes distincts. Les modes et
paramètres Codex actuellement observés viennent du code local audité ; ils ne
constituent pas une barrière suffisante pour l’autonomie. Référence officielle
consultée : [sécurité Codex](https://learn.chatgpt.com/docs/security).
Le broker doit appliquer les restrictions hors du processus agent, sans laisser
un worker modifier sa propre configuration, ses tests de publication ou ses droits.

Un futur service possède des credentials de modèle limités et un quota global
approuvé. Le budget doit inclure enfants, retries, extraction, évaluations et
embedding éventuel. L’exécutant n’a aucun token HA ; un broker séparé applique
les demandes explicitement approuvées. Pour les équipements critiques, les
interverrouillages matériels/déterministes restent nécessaires et indépendants.

## Risques restant ouverts

- Identités de production et droits familiaux non définis ; les sélecteurs
  d’espace actuels ne sont pas des comptes authentifiés.
- Preuve de source : le prototype contrôle le canal et la présence d’une référence,
  pas sa signature ni sa vérité physique. Capture immuable côté ingress à ajouter.
- SQLite/FTS scanne les connaissances visibles et compare les contradictions en
  mémoire ; pas de certification de charge. Les snapshots et suggestions peuvent
  contenir des références devenues obsolètes ; revalidation nécessaire à l’application.
- Limites temporelles coopératives, pas de confinement OS ni quota disque implanté.
  HTTP de laboratoire sans rate limiter, protection contre saturation ou TLS.
- La détection de contradiction utilise sujet/prédicat et différence JSON, pas
  une compréhension générale du langage, des unités ou des contraintes physiques.
- MCP testé avec un client protocolaire synthétique, pas avec le runtime Hermes.
  Aucune promesse de compatibilité d’une version Hermes non épinglée.
- Les protections de confidentialité n’empêchent pas un administrateur du même
  compte OS de lire/modifier les fichiers. Séparer les comptes et sauvegarder.

## Tests de sécurité démontrables

`test_07_external_injection_cannot_promote_correct_or_act`, tests ACL/relations,
refus d’anciens vector hits, secret ingress, refus d’écrasement de base/sauvegarde,
approbation impossible même via pause, HTTP 401/403, MCP sans outil HA et sans
token en sortie. Ces preuves portent sur ce prototype ; elles ne constituent
pas un pentest de la gateway ou de Home Assistant en production.
