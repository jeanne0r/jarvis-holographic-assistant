# Phase 6 — Intégration progressive préparée, inactive

## Architecture conservée

Gemini Live et les interfaces restent dans Jarvis sur Proxmox. Le bridge et SQLite
conservent admissions, états, événements, résultats et approbations. Hermes Windows
et Ollama/RTX restent derrière les tunnels privés existants ; aucun modèle distant
supplémentaire autorisé. Qdrant est un index reconstructible, jamais la source
canonique. Aucun deuxième registre de missions ou mémoire factuelle sur Windows.

Pas d'installation, démarrage Hermes/Ollama, changement réseau, migration réelle
ou montage de gateway effectué dans cette préparation. C1 clos, aucun nouvel essai.

## Code préparé dans le worktree

| Composant | Comportement |
|---|---|
| `hermes-bridge-client.mjs` | Transport Node 18 vers le bridge contrôleur en loopback uniquement ; identité serveur injectée, pas de redirection ; délais total/inactivité, taille de réponse et routes bornés ; aucune API modèle |
| `jarvis-hermes-experimental.mjs` | Réutilisé : admission 202, idempotence, consultation, pages SSE, résultats et annulation ; aucune boucle d'agent dans HTTP ; quotas distants 0 et quota local explicite 98 304 tokens |
| `hermes-server-auth.mjs` | Réutilisé : sessions opaques hachées, expiration et espaces attribués côté serveur ; profil visuel ignoré |
| `jarvis-phase6.mjs` | Point d'insertion à dépendances injectées ; flag false par défaut ; droits de route et espace côté serveur, journal d'admission obligatoire ; aucun import du backend actif |
| `resultInbox` | Pages d'événements liées à une mission, curseur durable fourni par l'hôte, notifications de résultats/approbations/erreurs ; texte non exécuté, validation unreviewed |
| Worker phase 4 | Réutilisé sans modification : différer avant premier dispatch si Windows/GPU indisponibles, conserver le premier début d'exécution, jamais rejouer un run ambigu |

Le backend existant importe des modules aux effets de bord, dont une synchronisation
planifiée : les tests n'importent pas `backend.mjs`. Le wrapper prend une fonction
legacy injectée ; aucun changement apporté à la source servie par la gateway.

## Authentification et ACL : périmètre précis

À l'état actif de laboratoire, toutes les routes Jarvis traversant le wrapper
exigent une identité serveur et un espace explicite autorisé, sans espace implicite
user. Requête à plusieurs paramètres space refusée. Les droits de route sont
issus d'une table serveur distincte, jamais du profil ou du corps de requête.
L'accès Hermes reste également contrôlé par sa façade et par l'identité propre au
bridge ; les autorisations SQLite s'appliquent encore en aval.

**Les routes existantes effectivement préparées pour délégation sont seulement
les GET** docs, doc, memory/map, memory/status, live/status, voice/status et capabilities.
Les autres sont refusées en mode sécurisé, même si une table de droits essaye de
les autoriser. Aucune route capabilities/run, ask, live/tool, shell, import,
evolution, publication ou approbation exposée par cette ouverture initiale.

Cela **ne constitue pas une correction déployée de toutes les routes existantes**.
En particulier, les flux vocaux POST, les mutations mémoire et l'outillage Gemini
nécessitent encore la revue de leurs effets, le mécanisme de session côté client,
les protections CSRF si un cookie est choisi et des tests de compatibilité avant
activation réelle. L'allumage prématuré du wrapper sécurisé bloquerait ces routes :
il est interdit de le monter en production à ce stade. La voix actuelle reste
inchangée parce qu'aucun patch n'est monté.

Les secrets du client bridge restent côté serveur ; le navigateur n'obtient qu'une
session utilisateur distincte. Révocation/rotation des sessions et propagation des
ACL à la véritable interface restent à raccorder, pas de token de laboratoire à
réutiliser comme session publique. Aucune modification d'Origin ne remplace l'auth.

## Non-blocage et mode dégradé

POST mission écrit d'abord dans le bridge Proxmox et rend 202/mission_id ; il ne
contacte pas Windows. Le worker indépendant vérifie disponibilité et télémétrie
avant premier départ. PC éteint ou Kryptex actif : la mission peut rester queued,
la conversation conserve son chemin normal. Pas d'arrêt automatique du minage.

Un contrôleur indisponible rend 503 borné ; une réponse d'admission perdue doit
être récupérée avec **la même clé d'idempotence**, sans nouvelle demande créée
aveuglément. Si la livraison au runtime est ambiguë, le bridge existant marque
unknown/reconciliation_required. Pas de rejeu automatique après disparition du PC.

Annulation déjà soumise à l'ACL de mission ; terminal reste terminal. Approbations
humaines restent dans le broker indépendant, non exposées par cette façade initiale.
Un endpoint d'approbation ne doit être ajouté qu'après revue du canal humain et
vérification de la séparation des acteurs/fingerprint/expiration existante.

## Notifications et audit

Les événements canoniques sont ceux du bridge SQLite, avec curseur SSE. Le client
inbox exige mission_id et numéro d'événement cohérents. Notification avec ID stable,
curseur sauvegardé après livraison ; reprise via Last-Event-ID. Livraison **au moins
une fois**, donc callback d'affichage idempotent nécessaire, pas de promesse de
exactement une fois. Le host doit sérialiser les consommations par clé et stocker
les curseurs durablement ; l'UI et son stockage réel ne sont pas raccordés.

L'audit de route ne contient ni requête, texte de résultat ni jeton. Le callback
d'audit doit être durable ; son échec interdit la délégation. Les résultats du
modèle sont données non fiables, jamais HTML/instructions/approbations. Le canal
vocal de notification n'est pas activé et ne génère aucun appel Gemini automatique.

## Tests et preuves de laboratoire

`node test_phase6.mjs` utilise le **vrai serveur HTTP Memory Manager et la vraie
SQLite synthétique temporaire** avec son middleware existant. Aucun runtime Hermes
ni GPU. Création/idempotence/état/SSE/annulation, arrêt du contrôleur et réouverture
du même fichier, refus de profil/espace, API d'approbation et action physique,
rollback du flag. Curseur de notification testé avec vrai fichier temporaire et
réinstanciation, payload synthétique. Tests de bornes transport, redirection non
suivie et délais ; pas de charge longue ni arrêt matériel du PC réel.

`python3 scripts/evaluate_memory.py --phase6` conserve les régressions locales des
phases précédentes et produit `JARVIS_2_PHASE6_TEST_RESULTS.json`, distinct des
preuves C1 historiques. Le calcul de coûts reste déterministe et distant à 0 CHF.

## Séquence d'activation future — approbations séparées

1. Revue du patch, de toutes les routes écriture/vocales, des ACL serveur par
   utilisateur/espace, sessions/expiration/révocation et stockage d'audit/curseurs.
2. Laboratoire Jarvis distinct, fixtures synthétiques et simulateur du PC absent ;
   cette étape est testée ici, sans lancer Gemini/Hermes réels.
3. Nouveau pilote réel explicitement autorisé **de phase 6**, sans refaire C1 :
   une mission synthétique depuis une interface de préproduction, quotas, fenêtre,
   gardiens et arrêt bornés définis avant essai. Pas d'autorisation implicite ici.
4. Après revue et nouvel accord gateway : installer l'intégration désactivée,
   puis activation pour un utilisateur/espace expérimental seulement, sans données
   personnelles tant que leur propre périmètre n'est pas approuvé.
5. Observer admissions, erreurs, latences et événements ; pas de montée en charge
   ou fallback payant automatique.

Retour arrière immédiat du raccordement expérimental : flag false bloque les
routes Hermes et restaure la délégation legacy ; aucune donnée de mission supprimée.
Cette désactivation ne révoque pas par elle-même un run déjà parti : annuler via le
bridge ou arrêter les seuls Jobs possédés avec procédure approuvée. La suppression
éventuelle du wrapper après revue reste un changement de gateway soumis à accord.
Une politique de sécurité globale ne doit pas être retirée en prétendant que ce
rollback applicatif constitue une protection : authentification/ACL production
nécessiteront un déploiement distinct et une stratégie de maintenance.

## Vérification de préparation

`python3 scripts/evaluate_memory.py --phase6` : **19 commandes réussies**,
preuves séparées dans `JARVIS_2_PHASE6_TEST_RESULTS.json`. Les vérifications
complémentaires du contrat de dates et du wrapper passent aussi après les derniers
ajustements. Aucun nouvel essai C1, appel GPU ou effet sur la production.

## Mise à jour — intégration de laboratoire développée

Voir `JARVIS_2_PHASE6_REPORT.md` et les nouveaux SECURITY/INTEGRATION/UI/TEST_RESULTS.
22 commandes locales réussies, façade HTTP/SQLite réelle, fournisseurs/runtime
simulés, navigateur réel. Patch de 16 cibles produit et répété en copie locale,
non appliqué. Les comptes, le switch et l'audit privés restent à provisionner.

L'audit actuel établit un moteur **hybrid**, pas Live natif. Le profil sécurisé
refuse /ask à cause de son worker Codex large ; il ne doit pas être activé comme
un raccordement transparent. Choix d'une stratégie compatible à revoir avant
pilote/déploiement réel ; aucun changement d'engine, microphone ou routeur effectué.

## Suite 6B — mode hybride conservé

Le constat précédent de blocage `/ask` et la preuve Live natif sont historiques.
L'adaptation sûre du véritable chemin hybride est maintenant développée, inactive :
voir `JARVIS_2_PHASE6_HYBRID_AUDIT.md`, `JARVIS_2_PHASE6_HYBRID_INTEGRATION.md`,
`JARVIS_2_PHASE6_PREFLIGHT.md` et `JARVIS_2_PHASE6_NEXT_STEPS.md`.
Le handler réel et son routeur sont testés avec fournisseurs simulés et bridge
SQLite synthétique; les pilotes Windows P6-L1 et P6-L2 nécessitent un nouvel accord.
Le patch minimal 6B exclut le montage Live natif. Aucun changement à Jarvis actif.
