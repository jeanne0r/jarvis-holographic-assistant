# Lot B — Connexion humaine unique Jarvis / Hermes

État : code fonctionnel et testé sur copie isolée. Activation en production **NO-GO** tant que les prérequis ci-dessous restent ouverts. Aucun service actif, compte, secret, mémoire ou équipement modifié. Aucun appel Windows, GPU ou fournisseur distant.

## Audit ciblé de l'installation active

Origine : `https://192.0.2.16:8788`. Gateway : `/home/user/gateway/server.js`, backend importé : `/home/user/workspace/jarvis/backend.mjs`.

- Le jeton historique `GATEWAY_TOKEN` est une identité partagée ; il ne prouve pas l'identité d'un humain. Il n'a pas été lu ni copié.
- La route commune `/api/jarvis/session` répond 404 ; la session privée du panneau répond 401 sans authentification. Ce sont deux contrats différents actuellement.
- L'entrée active appelle directement le backend Jarvis après le relais du panneau. Le contrôle général des routes et des ACL de l'entrée sécurisée préparée n'est pas installé. Les contrôles d'origine et le choix d'un espace ne constituent pas une identité humaine.
- Le lancement Codex actif hérite de l'environnement du processus gateway, avec le même utilisateur OS. Une clé de délégation accessible à cet utilisateur ne serait donc pas isolée de cet exécutant.
- Le mode vocal observé reste `hybrid`. Les processus gateway 2538966 et pilote 2556916 sont restés inchangés ; le panneau existant reste activé, sans activation d'admission.

L'audit n'a consulté aucune conversation, base personnelle ou valeur de secret. Il ne certifie pas les droits des anciennes routes par leur seul code source.

## Raccordement réalisé

Le registre existant `jarvis-session-auth.mjs` émet une seule session humaine Jarvis. Le panneau réutilise le client de connexion général, indépendant de sa fenêtre, sans seconde saisie Hermes et sans stockage de secret dans le navigateur.

Le relais local authentifie la session, vérifie les droits et signe une preuve serveur de cinq secondes liée au sujet, espace, méthode, URL et corps exacts. Le service privé refuse les cookies et l'ancienne connexion opérateur en mode unifié, vérifie signature, expiration et rejeu, puis applique **sa propre liste de sujets et ses propres ACL**. Aucun rôle déclaré par le navigateur ou le modèle n'est accepté. La preuve ne contient pas de secret du bridge.

Les deux politiques sont revérifiées avant restitution d'un résultat. Une révision de politique strictement croissante empêche un rechargement obsolète de rétablir des droits révoqués pendant le fonctionnement du processus. Les sessions et le cache anti-rejeu sont en mémoire : un redémarrage déconnecte les humains, ne restaure pas leurs sessions. Le cache anti-rejeu ne constitue pas un registre durable ; sa fenêtre est bornée à cinq secondes. Les révisions et fichiers de politique doivent rester protégés au niveau OS, y compris pendant une restauration.

Le montage est facultatif et désactivé par défaut. Il compose l'entrée sécurisée existante, sans repli vers une ancienne route non protégée. Le chemin historique direct `/api/jarvis/hermes/*` est refusé dans cette composition. Le lot B n'accorde que lecture et annulation dans l'espace synthétique déjà utilisé ; création, approbation, délégation vocale et outils physiques restent exclus.

## Vérifications exécutées

| Commande | Résultat observé |
|---|---|
| `node test_hermes_single_session.mjs --browser` | 39 assertions HTTP ; 20 contrôles navigateur aux largeurs 1440 et 390 ; une seule connexion |
| `node test_hermes_human_mount.mjs` | 17 assertions : configuration, cookies HTTPS, fichiers privés, refus des chemins alternatifs |
| `node test_hermes_private_human_policy.mjs` | 14 assertions : identité privée, permissions excessives, clés réutilisées, liens symboliques |
| `node test_jarvis_policy_revision.mjs` | 10 assertions : refus des politiques obsolètes et non versionnées |
| `node test_hermes_embedded.mjs` | 42 assertions ; ancien mode privé conservé |
| `node test_hermes_operational.mjs` | 32 assertions ; fonctionnement opérationnel simulé conservé |
| `node test_phase6d_security.mjs` | 101 couples route/méthode, dont 97 protégés ; révocation et propriété vocale |
| `node test_phase6d_final.mjs` | 53 couples de routes métier ; hybride et fournisseurs simulés |
| `node test_production_bindings.mjs` | Adaptateurs, révocation, hybride simulé, absence de contournement Codex |
| `python3 -B -m unittest memory_manager.phase6.test_human_assets -q` | 3 tests réussis |
| `python3 -B -m unittest memory_manager.phase6.test_operational_runtime -q` | 1 test réussi : navigateur → services temporaires → faux Hermes/Ollama → mémoire synthétique |

Couverture hostile : anonymat, identité de service, faux profil, autre espace, paramètres ambigus, droit d'annulation manquant, origine malveillante, preuve falsifiée/rejouée/expirée ou liée à un autre corps, révocation pendant réponse, déconnexion et politique indisponible. Les données, identités et clés de ces essais sont synthétiques.

Une première exécution du dernier test a refusé un port occupé par un processus temporaire de test antérieur. Ce seul processus a été identifié par son chemin temporaire et arrêté ; la nouvelle exécution a réussi. Aucun service installé n'a été arrêté ni adopté comme faux fournisseur.

Vérification supplémentaire : le générateur opérationnel inclut désormais la dépendance de délégation du relais et son empreinte ; import et syntaxe contrôlés. Les anciens manifestes et verdicts ne sont pas modifiés.

## Proposition de déploiement minimale, sous conditions

1. **Précondition bloquante :** raccorder effectivement l'entrée sécurisée et ses adaptateurs aux fonctionnalités actives, avec confinement réel de l'exécutant Codex. Le lot B ne remplace pas ce travail par une session réputée fiable. Aucun remplacement global de `server.js` n'est proposé comme prêt.
2. Faire approuver les sujets humains nommés et leurs espaces/rôles ; aucun propriétaire ne sera déduit d'un profil visuel ou attribué aux anciennes données. Prévoir une clé serveur dédiée, distincte de toutes les identités existantes, lisible uniquement par les services autorisés. Aucun compte ni clé créé dans ce lot.
3. Après approbation exacte, sauvegarder release/configuration et restaurer la SQLite synthétique sur copie. Installer les six fichiers privés et deux manifestes du paquet de revue ; configurer les ACL privées explicites ; redémarrer uniquement le pilote et revalider authentification, refus et BPF. Aucun changement de son confinement réseau.
4. Après revue de l'entrée réellement sécurisée et autorisation de redémarrage, monter le registre commun et le relais signé. Déployer le JS du panneau réutilisant la connexion générale ; CSS inchangée. Admission et voix désactivées. Vérifier connexion, historique, annulation autorisée, refus croisés, révocation et fonctionnement hybride, sans mission ni fournisseur réel.

Paquets de **revue**, sans installation : `data/lot-b-sso/review/` et `data/lot-b-sso/frontend/`. Empreintes des sources, préimages actives et manifestes : `JARVIS_2_LOT_B_MANIFEST.json`. Le paquet de bibliothèques gateway n'est pas un remplacement autonome de son entrée active.

Retour arrière : refermer le montage SSO et restaurer les seuls fichiers/configurations sauvegardés avec leurs empreintes. Conserver la file SQLite et l'historique ; ne restaurer ni identifiants révoqués ni anciennes ACL pour faire fonctionner la connexion. En cas d'incertitude, fermer le panneau. Un éventuel redémarrage de gateway exige son autorisation distincte.

Verdicts : **GO laboratoire** pour la connexion unique et le contrôle indépendant des missions ; **NO-GO installation/activation de production** jusqu'à résolution des préconditions d'entrée sécurisée, d'isolation et d'enrôlement explicite. Aucune autorisation de production n'est présumée.
