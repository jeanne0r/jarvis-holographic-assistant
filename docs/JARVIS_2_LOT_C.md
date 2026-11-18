# Lot C — Missions textuelles depuis le panneau actuel

**Déployable indépendamment du SSO, sous autorisation.** Le service privé installé accepte déjà `{objective: "…"}` avec son authentification propre. Pas de nouvelle mémoire, de nouveau frontend ni de remplacement de gateway. Le lot B reste conservé au commit `f545107`, avec ses prérequis documentés.

## Changement minimal

Une seule cible de production : `/home/user/gateway/public/jarvis/hermes-embedded.js`. Candidat : `data/lot-c-text/ready/`. Aucune modification de CSS, `app.js`, `server.js`, backend, moteur hybride ou release privée. Aucun redémarrage de gateway.

Le champ permet de préparer une demande même hors fenêtre, sans la transmettre. L'envoi exige le flag texte, l'admission, le rôle existant `missions.create` et une confirmation explicite de l'utilisateur. Le serveur demeure l'autorité : maximum 2 000 caractères, enveloppe exacte, contexte vide, outils `memory.search` et `report`, espace synthétique existant. Toute tentative d'ajouter outils, historique ou propriétaire est refusée. Le texte n'accorde ni shell, ni action physique, ni publication.

Un double clic produit une seule tentative. En cas de réponse réseau perdue, aucun réessai automatique : le texte est figé, un nouvel accord est requis, et le renvoi conserve exactement le même corps et la même clé d'idempotence. Après admission, la mission est sélectionnée dans l'historique. Réponse et provenance restent consultables ; aucune promotion automatique d'un résultat `inferred`.

La confirmation est une déclaration de l'utilisateur, pas un détecteur de données personnelles. Ne saisir que des exemples fictifs : le texte sera conservé dans la SQLite synthétique et transmis à Windows lors d'une exécution autorisée. Aucune conversation privée n'est récupérée automatiquement.

## Fenêtre réelle préparée, non exécutée

Le lanceur existant conserve ses anciens modes. L'option distincte `--approved-text-window` réutilise exactement ses contrôles BPF, clés, service privé, gardiens Windows/GPU/Kryptex, modèle et tunnels. Plafonds inchangés : une mission, 300 secondes de fenêtre, 240 secondes de budget mission, six appels, 98 304 tokens, 0 CHF distant. La voix reste désactivée.

Un nouveau reçu root à usage unique `text-operational-window-used.json` est requis ; les reçus précédents ne sont ni effacés ni réutilisés. Les nouvelles empreintes du JS C et de la CSS A sont explicitement épinglées dans `HERMES_TEXT_MISSIONS_MANIFEST.json`. Toutes les autres préimages et le manifeste privé installé restent exigés. Un écart interrompt le lancement.

Le contrôle final distingue les sources synthétiques originales des expériences `mission://…` : ces dernières exigent une mission synthétique terminée et un événement de résultat existants dans SQLite. La projection doit provenir des reçus d'outils authentifiés et du stockage canonique, et la réponse doit citer une source synthétique. Aucun verdict historique n'est modifié, notamment celui de la fenêtre du 15 novembre à 20:09:50.

Cette première activation reste supervisée : saisie libre dans le périmètre synthétique, pas d'exécuteur permanent. L'admission n'est ouverte qu'après disponibilité vérifiée du worker et se referme après le démarrage de la mission. Une mission incertaine bloque le lancement suivant. Le service d'historique n'a pas de durée artificielle de cinq minutes.

## Tests exécutés sans GPU

- `node test_hermes_operational.mjs --installed` : 32 assertions HTTP contre les modules réellement installés de l'API et du relais, avec authentification privée actuelle ; flags, ACL, requêtes interdites, texte et capacités serveur.
- `node test_hermes_mission_policy.mjs` : 25 assertions de politique, sans appel modèle.
- `python3 -B -m unittest memory_manager.phase6.test_text_window memory_manager.phase6.test_operational memory_manager.phase6.test_worker_window_admin -q` : 32 tests réussis, dont quotas, identités distinctes, mémoire contrôlée, budget, indisponibilité GPU/Kryptex, redémarrage sans rejeu et contrôle des sources.
- `python3 -B -m unittest memory_manager.phase6.test_operational_runtime.OperationalRuntimeTests.test_text_deployed_auth_and_runtime -v` : copie exacte de la release privée installée, SQLite synthétique temporaire, vrai navigateur et protocoles HTTP ; seul le runtime Hermes/Ollama est simulé. Saisie Unicode, accord, double clic, panne réseau et renvoi idempotent, résultat, historique mobile, brouillon sans envoi hors fenêtre et refus d'outils supplémentaires. Une seule création du faux runtime, un seul appel du faux modèle ; droits et budget persistés vérifiés dans SQLite.

La préparation copie uniquement le code installé vérifié, jamais sa configuration ni ses secrets. Les données, identités et serveurs de test sont temporaires et fictifs. La procédure root C n'a pas été exécutée : ses contrats sont testés hors ligne, le contrôle réel BPF et l'état Windows restent des préconditions du lancement autorisé. Aucun résultat simulé n'est présenté comme une exécution RTX.

## Installation et autorisations

**Accord 1 — un asset uniquement.** Vérifier SHA-256 avant, propriétaires, liens, réserve disque et services. Sauvegarder le JS et son manifeste dans un répertoire privé daté, vérifier l'empreinte et restaurer une copie de contrôle. Remplacer atomiquement le seul JS en conservant mode et propriétaire. Vérifier les bytes servis en HTTPS et l'absence de changement des PIDs. Tous les flags restent désactivés. L'authentification Hermes actuelle reste obligatoire. Recharger Jarvis suffit.

**Accord 2 — une fenêtre textuelle réelle.** Après installation vérifiée, autoriser séparément le redémarrage temporaire du seul service privé, son armement, Windows/Ollama/Hermes et l'admission d'une demande synthétique écrite par l'utilisateur. Le lanceur vérifie espace disque, sauvegarde configuration et SQLite par API backup, restauration sur copie et absence de mission active/incertaine avant armement. Il ne crée jamais la mission : attendre « worker prêt », puis saisir et confirmer dans Jarvis. Aucune permission nouvelle ni aucune dépense ne sont requises.

Commande préparée, **à ne pas exécuter sans cet accord 2** :

```bash
sudo python3 -B /home/user/workspace/jarvis-2-memory/ops/pilot-network/run-worker-window.py --approved-text-window
```

Le lanceur referme l'admission, laisse le superviseur arrêter seulement ses processus/tunnels, restaure la configuration initiale et vérifie à nouveau le confinement du service d'historique. Aucune relance automatique après refus ou incertitude. Aucun compte, service permanent ou changement de pare-feu.

**Retour arrière UI :** vérifier l'empreinte courante C, restaurer atomiquement le seul JS A sauvegardé et contrôler le hash HTTPS ; aucun redémarrage. **Retour arrière fenêtre :** restauration des flags/configurations par le lanceur, sans écraser la SQLite courante ni effacer missions, reçus ou preuves. Si le nettoyage ou BPF échoue, conserver l'admission fermée et signaler le blocage sans retirer de protection.

Conclusion : aucun blocage SSO pour C. Le seul passage en production restant est l'approbation des deux opérations ci-dessus et la réussite de leurs précontrôles effectifs. La compatibilité du chemin texte est démontrée en simulation complète ; aucune nouvelle exécution GPU n'a été effectuée.
