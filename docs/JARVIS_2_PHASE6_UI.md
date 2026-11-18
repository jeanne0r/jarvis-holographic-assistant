# Phase 6 — Interface holographique et notifications

## Ajout réutilisant l'interface existante

Deux nouveaux assets, hermes-missions.js et hermes-missions.css, sont chargés par
une ligne ajoutée à l'index existant. Pas de nouveau frontend, build, framework ou
modification du microphone. Le bouton/panneau est superposé à l'hologramme actuel.
Si la configuration de session n'est pas montée (flag par défaut), le probe reçoit
404 et le panneau reste invisible. Aucun jeton master gateway demandé.

Quand la protection serveur est autorisée : connexion avec un code personnel
fourni hors bande par l'administrateur, puis cookie HttpOnly. Le code est effacé
du champ et n'est ni stocké dans localStorage ni envoyé à un autre service.
La sélection de profils masque/désactive les espaces interdits pour le confort,
mais seules les ACL serveur font autorité. Expiration de session : panneaux privés
vidés, invitation à se reconnecter, pas de lancement de mission en arrière-plan.

## Fonctionnalités préparées

- Liste des cinquante missions canoniques les plus récentes, objectifs et états.
- Mission synthétique DoseLab via template fixe ; admission puis retour immédiat,
  même clé d'idempotence conservée si l'envoi ne reçoit pas une réponse certaine.
- Détail et progression via états/événements, sortie et références de provenance.
- Annulation des missions non terminales, erreurs, attente et réconciliation.
- Approbations exactes : description, boutons once/deny seulement pour le rôle
  humain configuré ; confirmation de clic, identité machine d'approbation distincte.
- Actualisation déterministe toutes les cinq secondes si la page est visible ;
  indication visuelle d'un nouvel état terminal ou d'approbation, sans son ni
  appel Gemini. Détail chargé si le panneau est ouvert, liste légère sinon.
- Le bouton Compte permet la déconnexion même quand Hermes est désactivé mais que
  l'authentification serveur est active. Les conversations continuent via leur
  route existante selon le profil autorisé, jamais par une boucle d'agent UI.

L'historique et le résultat sont conservés en SQLite côté bridge. La map de
notifications visuelles est locale au chargement de page : une nouvelle ouverture
peut montrer de nouveau un état terminal ; pas de garantie exactly-once. L'inbox à
curseur durable préparée précédemment reste disponible mais n'est pas présentée
comme branchée dans ce panneau. Pas de copie locale des conversations/résultats.

## Sécurité de rendu

Tous les textes distants sont insérés avec textContent, y compris objectifs,
résultats et descriptions d'approbation. Une sortie contenant img/onerror reste
littérale. Aucun HTML, JavaScript, commande, lien ou approbation issus du résultat
n'est exécuté. Une notification n'est pas une preuve de vérité d'un fait.

Le premier périmètre ne transmet aucun objectif personnel : le seul corps admis
par le navigateur est `{"template":"doselab-current"}` ; le serveur construit
l'objectif synthétique et les limites. Le rôle humain ne peut pas être fabriqué
par un modèle ou un changement du profil visuel.

## Validation navigateur effectivement exécutée

`node test_phase6_ui.cjs` : Chromium headless existant, desktop 1366×900 et mobile
390×844, **page holographique existante**, toutes les API simulées en loopback,
réseau externe bloqué. Connexion, mission, résultat sourcé, texte malveillant
inerte, approbateur distinct requis, absence de dépassement horizontal, fermeture
et bouton micro encore visible ; aucune requête live/session ou live/tool émise
par le panneau. Code de connexion effacé et absence de persistance locale testées.

Le Chromium complet ne démarrait pas, faute de bibliothèques système. Le shell
headless et un sysroot déjà présents fonctionnent ; LD_LIBRARY_PATH ne s'applique
qu'au processus de test, aucun paquet installé ou système modifié. Captures locales
synthétiques `data/phase6-ui-desktop.png` et `data/phase6-ui-mobile.png`, non dans Git ;
vue mobile inspectée. Ce test ne valide ni Safari/iPhone réel, ni une session
vocale native sur matériel, ni Hermes Windows réel.

## Limite de mise en service

Le moteur actif est hybrid. La preuve UI et la preuve outil Gemini Live natif
ne constituent pas la validation de son chemin /ask. Voir SECURITY et INTEGRATION :
ce profil refuse /ask jusqu'à revue de ses permissions ; aucun raccordement actif
n'est permis en prétendant que l'expérience hybride serait intégralement conservée.
