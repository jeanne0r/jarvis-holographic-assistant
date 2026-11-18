# Hermes à la demande — livraison logicielle

Le code est testé en laboratoire et empaqueté. **Aucune installation ni activation réalisée.** Authentification Hermes actuelle conservée ; SSO B inchangé et toujours en attente. Aucune modification de `server.js`, du backend hybride, de l'audio, des équipements, de CT205 ou d'une mémoire personnelle.

## Fonctionnement livré

Le panneau existant présente « Décrire une mission » et « Confier à Hermes ». Après confirmation et contrôle des droits, la mission est enregistrée dans les tables canoniques existantes. La disponibilité du GPU ne conditionne plus l'enregistrement. La prise en charge n'est annoncée qu'à partir de l'état effectivement enregistré ; les demandes en attente, résultats, annulations et erreurs restent visibles. Les sources restent repliables et les notifications silencieuses.

La liste et les résultats proviennent toujours de la même SQLite. Deux tables additives `p6q_jobs` et `p6q_keys` ne stockent que l'ordonnancement, les réservations et les clés d'idempotence ; elles ne constituent pas une seconde mémoire ni une copie des missions.

Le superviseur non privilégié consulte la file, vérifie Windows, le GPU, Kryptex, les identités, les empreintes et le confinement, puis réserve une seule mission. Il appelle le cycle de vie Windows existant, qui démarre temporairement Ollama et Hermes et les arrête avec leurs tunnels. Aucun modèle ne tourne lorsque la file est vide. Windows éteint ou GPU occupé : attente, sans tentative de réveil ni interruption d'un processus existant.

L'acceptation et l'exécution ont des autorisations distinctes. Le profil initial peut accepter les demandes avec `executionEnabled=false`, sans identifiants de runtime dans ce profil. Les réglages d'exemple sont désactivés et non commissionnés : une simple copie du paquet ne peut pas les activer.

### Quotas et reprise

- Une exécution réservée à la fois ; six appels, 98 304 tokens, 240 secondes de travail et 0 CHF distant par mission. Réservation technique de 300 secondes et délai de nettoyage borné, sans durée limite artificielle du service lui-même.
- Dix missions non terminées au maximum ; expiration des demandes non démarrées après 24 heures. Plafonds conservateurs supplémentaires : 50 enregistrements et 12 réservations d'exécution sur 24 heures glissantes ; registre d'idempotence limité à 10 000 clés, refus plutôt qu'effacement silencieux à saturation.
- Double clic et perte de réponse : même clé et même corps. Rechargement : l'onglet ne conserve que la clé et l'empreinte du texte, jamais le texte ni un secret. Même intention exacte reconnue côté serveur durant ses 24 heures, y compris avec une autre clé ou après achèvement : le résultat existant est renvoyé, pas réexécuté. Une demande volontairement différente doit avoir un texte différent ; aucun paramètre « forcer » ne contourne cette règle.
- Arrêt pendant une réservation : mise en quarantaine ; aucun rejeu automatique. Un résultat déjà terminé n'est pas changé en échec ou effacé. Un nettoyage incertain bloque l'exécution suivante, tout en conservant la possibilité de consulter l'historique et d'enregistrer des demandes dans les limites de capacité.
- Temporisation déterministe de 30 secondes ; aucun appel modèle pour surveiller la disponibilité. Une réservation est consommée même si son exécution échoue. Une mission ou un reçu d'autorisation historique ne peut pas être adopté comme nouveau travail.

### Citations et audit de mémoire

Le correctif de citations `d14a2d5` est réutilisé : contrat serveur de réponse et descriptions MCP homogènes. Chaque conclusion issue de la mémoire doit citer le `source.ref` exact, avec une section Sources. Aucun ajout automatique à la réponse du modèle. Le validateur strict existant est inchangé ; les références `mission://…` nécessitent une mission synthétique terminée et son événement de résultat canonique.

Pour les nouvelles missions uniquement, un événement `report_quality` signale la présence ou l'absence de citations vérifiées. Un calcul techniquement terminé reste un calcul terminé ; sa qualité et sa vérification factuelle ne sont pas inventées. L'interface distingue une référence retrouvée d'un fait indépendamment vérifié. Aucun statut `inferred` n'est promu.

L'outil `memory.audit` / `jarvis_memory_audit` est un agrégat de lectures, sous le droit de lecture mémoire existant. Il compare les révisions, contenus et empreintes, dates de validité, statuts et provenances (ressemblance lexicale bornée à 512 tokens, jamais preuve d’égalité) ; il retrouve aussi les informations expirées que la recherche courante masque volontairement. Il distingue un remplacement historique d'un conflit non résolu et ne déduit pas un doublon du seul sujet. Deux textes égaux avec des provenances ou dates différentes restent des candidats à revue, pas des enregistrements interchangeables.

L'audit ne supprime, ne fusionne, ne corrige et ne promeut rien. Chaque proposition renvoie ses références. Limite : 20 mémoires et 200 révisions par sujet, sinon demande à préciser. Les nouvelles expériences de résultat restent les rapports `inferred` enregistrés par l'hôte comme auparavant ; le modèle n'obtient aucun outil d'écriture.

Le composant hybride Qdrant/FTS existant est réutilisable par `hybrid_searcher`, injecté côté hôte. Le test emploie des embeddings et Qdrant simulés et vérifie la revalidation SQLite ainsi que l'absence d'upsert pendant l'audit. Le service préparé utilise SQLite/FTS par défaut : aucun accès CT205 ou nouveau proxy vectoriel n'est activé. Un transport vectoriel réel supplémentaire demanderait sa propre revue réseau ; il n'est pas nécessaire pour utiliser la file et l'audit canonique initiaux. La collection historique n'est jamais touchée.

## Paquet et fichiers

Paquet de revue : `data/hermes-demand/deliverable/` ; son SHA-256 et les sources sont épinglés dans `HERMES_ON_DEMAND_MANIFEST.json`. Il contient :

- `private-release/` : copie du code installé vérifié, avec **14 fichiers différents**, dont les deux manifestes. Le manifeste du paquet donne les préimages et empreintes après de chaque fichier. Le mode privé à cookie est préservé : le code SSO inactif du worktree n'est pas imposé à ce lot.
- `frontend/hermes-embedded.js` : **seule cible de frontend à remplacer**. HTML et CSS sont copiés pour les essais, pas proposés comme changements de production. Aucun redémarrage de gateway.
- `windows-bindings.json` : **trois fichiers de laboratoire Windows à mettre à jour** (`phase2/mcp.py`, `phase2/memory_tools.py`, `phase3/mcp.py`). Hermes épinglé, Ollama, modèle, comptes Windows et pare-feu Windows ne sont pas réinstallés ni modifiés.
- `supervisor/` : dépendances Python déjà utilisées, copiées depuis les sources versionnées, sans HOME, données, identifiants ni environnement personnel.
- `before-private/` et `frontend.before.js` : préimages du code uniquement, pour vérification du retour arrière. **Aucune SQLite ni configuration privée réelle n'est copiée dans le paquet ou Git.**

Les modèles de service restent désactivés et préparatoires. `jarvis-hermes-supervisor.service` utilise une identité Linux dédiée sans privilèges, HOME dédié, code en lecture seule, répertoires d'état bornés, restrictions système et réseau. Les seuls ports liés restent loopback ; le navigateur passe par le relais actuel et ne reçoit aucun secret.

Deux opérations root brèves et fixes accompagnent le démarrage : le coordinateur existant vérifie/démarre le service privé avec son contrôle BPF ; une unité distincte vérifie ensuite les deux cgroups effectifs avec contrôles réseau et témoin négatif. Ces opérations n'exécutent aucune mission. Le second contrôle s'exécute hors du cgroup filtré afin que ses contrôles témoins soient réellement indépendants. Il produit une preuve root liée au démarrage de la machine, aux PIDs et aux empreintes des unités. Sans cette preuve, aucune réservation d'exécution n'est autorisée. Un changement de PID ou d'unité l'invalide.

Le réseau du superviseur autorise uniquement la file loopback et SSH vers le PC Gamer. La table nftables est réservée à sa nouvelle identité OS, sans modification des règles de la gateway ou des équipements. Les clés SSH et les empreintes des identités Windows doivent être provisionnées explicitement ; aucun HOME personnel n'est copié. Les trois jetons runtime sont distincts du jeton de file, du jeton du panneau et du jeton d'observation.

## Tests démontrés

Résultats finaux : **48 tests Python ciblés, 1 intégration HTTP/navigateur, 113 assertions Node et 101 couples route/méthode examinés (97 protégés exercés)**. Les commandes et résultats sont consignés dans le manifeste de livraison. Couverture :

- Vrai navigateur aux largeurs 1440 et 390, vraie authentification privée, relais et HTTP temporaires, vraie SQLite, véritable contrôleur existant ; **runtime Hermes, modèle, GPU et processus de nettoyage simulés**.
- Enregistrement avant toute exécution, perte de réponse après acceptation serveur, double clic, rechargement de page et renvoi de même clé sans doublon ; résultat lisible, références canoniques, expérience et état conservés après redémarrage.
- Authentification refusée ; jeton du panneau ou du modèle incapable de réserver une exécution ; jeton de supervision incapable de consulter librement les missions ; autre propriétaire/espace et outils supplémentaires refusés.
- Windows indisponible, GPU occupé, Kryptex, VRAM insuffisante, maintenance, capacité/quotas, annulation, expiration et quarantaine sans rejeu.
- Audit sans mutation SQL, contradictions, expiration, statut non vérifié, provenance, ressemblances avec sources distinctes et recherche hybride simulée revalidée dans SQLite.
- Contrats de preuve root/BPF, identités et nettoyage des deux processus propriétaires/tunnel/ports testés avec fixtures. **Le confinement effectif des nouvelles unités n'est pas validé sur l'hôte tant qu'elles ne sont pas installées et sondées après accord.**
- Unités vérifiées statiquement par `systemd-analyze verify --man=no` : succès, sans démarrage. Empreintes du paquet et restauration du code initial sur copie : succès.

La mission `a573c225-1879-4458-9ca0-89407cb2cc5f`, son `passed=false`, ses reçus et ses preuves restent intacts. Aucun nouveau GPU, API payante, compte, service, donnée personnelle ou déploiement n'a été utilisé. Gateway PID 2538966 et service privé PID 2591233 inchangés pendant les vérifications.

## Installation minimale à autoriser

1. **Installation du code, sans exécution.** Vérifier espace disque, tous les SHA-256 et propriétaires ; refuser toute dérive. Sauvegarder release, config et SQLite synthétique ; restaurer la sauvegarde SQLite sur copie et comparer intégrité/contenus avant migration. Installer les seuls écarts privés et le JS unique ; conserver authentification actuelle, secrets et ACL. Redémarrer uniquement le service privé via son coordinateur BPF, profil acceptation/exécution désactivé. Préparer la nouvelle identité OS, les répertoires privés, les clés nommées et les règles réseau dédiées, après autorisation explicite. Pas de redémarrage de gateway.
2. **Enregistrement depuis Jarvis.** Autoriser `accepting=true` et les flags correspondants du relais, avec `executionEnabled=false` et superviseur désactivé. Vérifier sessions, refus, historique et persistance. Le bouton peut alors enregistrer des demandes sans Windows ni GPU. Ce changement est une activation persistante d'enregistrement, à approuver séparément.
3. **Exécution automatique à la demande.** Autoriser les trois patches Windows, provisionner les identités et preuves source, puis activer l'exécution synthétique et le superviseur non privilégié. Les unités root de démarrage/probe doivent passer leurs vrais contrôles ; aucune désactivation de protection si un contrôle échoue. L'approbation doit couvrir le lancement temporaire Windows/Ollama/Hermes pour les demandes explicitement confirmées dans le panneau, avec les plafonds ci-dessus. Ne créer aucune mission à la place de l'utilisateur. Activer le démarrage au boot seulement si cet accord le prévoit.

Les champs non provisionnés des exemples (`commissioned=false`, empreintes fictives, absence de secrets et de preuve root) empêchent leur démarrage. Ils doivent être remplacés avec les valeurs observées et vérifiées lors de l'installation autorisée, jamais par une supposition ou un contournement. Les installations et probes root réels sont les seules vérifications non simulées restant obligatoires avant activation ; aucune nouvelle conception ni pilote GPU de citations n'est demandé.

### Arrêt et retour arrière

Suspendre d'abord les nouvelles demandes. Laisser finir le travail et le nettoyage bornés, ou annuler sous ACL ; en cas d'incertitude, conserver la quarantaine et interdire tout nouveau départ. Arrêter seulement les services du nouveau dispositif et leurs processus/tunnels propriétaires. Ne jamais arrêter Kryptex, Jarvis, Codex, Home Assistant ou un processus non possédé.

Restaurer les fichiers/configurations sauvegardés avec contrôle des empreintes, et le seul JS C précédent, sans redémarrer la gateway. Le retour à l'ancien service privé exige sa vérification BPF habituelle. **Ne pas restaurer une ancienne SQLite par-dessus les missions enregistrées :** conserver la base courante et les tables additives ; l'ancien mode de consultation ignore les métadonnées de file. Les anciennes fenêtres manuelles doivent rester bloquées devant une mission en attente ou incertaine, pas être forcées. Restaurer les trois fichiers Windows seulement depuis leurs préimages vérifiées. Ne jamais effacer les preuves ou réinitialiser un reçu consommé.

Après installation et autorisations réussies, l'utilisation normale se fait uniquement dans Jarvis : connexion habituelle, texte synthétique, confirmation, puis historique. Aucun sudo ni fenêtre manuelle pour chaque mission.
