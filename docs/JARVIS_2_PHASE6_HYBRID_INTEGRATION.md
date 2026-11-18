# Phase 6B — Admission Hermes dans le mode hybride

Développé dans `jarvis-2-memory`, branche `codex/jarvis-2-memory-20261113`.
Aucun raccordement à la gateway active. Les preuves de phase 5/C1 restent inchangées.

## Contrat serveur minimal

`phase6-gateway.mjs` authentifie la personne et son espace, exige `conversation`
pour `/ask`, puis attache un callback privé au véritable objet HTTP via WeakMap.
Ni un champ JSON, ni un historique, ni un profil ne peuvent créer ce binding.
`backend.mjs` invoque ce callback après validation de la question courante, avant
l'archivage et la génération de réponse.

`hybrid-mission-admission.mjs` accepte quatre variantes strictes de la phrase :
« [Jarvis,] demande à Hermes de vérifier la configuration DoseLab [X4] ».
Accents, casse, espaces et ponctuation finale sont normalisés pour la comparaison.
Une commande ajoutée, citation ou consigne mêlée est refusée. Les autres textes
mentionnant Hermes sont refusés sans passage à Codex : ce premier contrat ne permet
pas encore une conversation libre sur Hermes. Le fil précédent n'est jamais
utilisé pour décider d'une admission.

Pour une phrase admise :

1. Vérifier `missions.create`, espace autorisé et flags indépendants.
2. Exiger `archive.id` stable et `archive.turn` entier positif ou nul, déjà fournis
   par les clients écrit et hybride. Sinon 409, sans création.
3. Dériver la clé d'idempotence de version/identité/espace/id/tour. La même demande
   retrouve la même mission; une nouvelle question humaine constitue un nouveau tour.
4. Auditer seulement identité/espace/template/empreinte de demande.
5. Appeler la façade existante avec l'objectif synthétique **fixé côté serveur**,
   contexte mémoire vide et outils `memory.search`, `memory.propose`, `report`.
6. Renvoyer 202 avec `answer`, `speech`, sources vides, action null et
   `mission:{mission_id,state}`. Aucun appel Windows dans la requête d'admission.

Ni question libre, ni historique, ni source privée, ni propriétaire ou budget
fourni par le navigateur ne sont transmis. Un refus, flag éteint ou problème de
bridge ne déclenche aucun repli Codex/LLM. Délai de transport borné à 1,5 seconde
par la façade; aucun rejeu automatique après admission incertaine.

## Configuration et rôles

Tous les flags restent à 0 par défaut : `JARVIS_SERVER_AUTH`,
`JARVIS_HERMES_ENABLED`, `JARVIS_HERMES_HYBRID`, `JARVIS_HERMES_NATIVE_LIVE`.
Le montage 6B refuse explicitement Native Live : son patch séparé n'est pas inclus
au déploiement minimal. Le test historique Live reste conservé dans le worktree.

L'authentification possède des sessions opaques personnelles expirantes, hachées
au serveur, cookie HttpOnly/SameSite et Origin épinglée. Un rôle `conversation`
autorise le routage historique; `voice` son transport, `missions.create/read/cancel`
les opérations du pilote. Le compte humain du pilote n'a pas `missions.approve`.
Le compte runtime ne dispose pas de session conversationnelle Jarvis. Le secret
bridge est dans un fichier privé 0600 côté Proxmox, jamais dans le navigateur.

Les capacités navigateur nécessitent `capabilities` : un volume `target=ici`
reste disponible, une cible HA ou un trajet personnel est refusé dans cette façade.
Aucun élargissement d'outil Hermes, de droits OS ou de permissions Codex.

## Interface et mode dégradé

Le panneau existant de phase 6 conserve liste/états/annulation/résultats et sources
rendus comme texte. Rafraîchissement toutes les cinq secondes lorsque visible,
pas d'annonce vocale automatique ni d'appel Google à chaque événement.
`window.jarvisAsk`, `codex-voice.js` et `live.js` restent inchangés.
Seul le chargeur `voice-router.js` retente le chargement après login, avec garde
contre les doublons. Aucune logique micro, interruption ou streaming modifiée.

PC arrêté/GPU occupé : l'admission reste possible si le bridge est disponible;
le worker existant diffère l'exécution selon ses gardiens. Les runs ambigus
nécessitent réconciliation, pas de répétition aveugle. Bridge indisponible : refus
borné, le chemin ordinaire demeure séparé. Pas de fallback payant.

## Patch préparé en quatre étapes

Artefacts : `docs/phase6b/01-*.patch` à `04-*.patch`, liste exacte et empreintes
avant/après dans [patch-manifest.json](phase6b/patch-manifest.json).
Génération reproductible : `python3 scripts/prepare_phase6b_patch.py`.
Ce script ne peut écrire que les artefacts et une copie temporaire de répétition;
il ne contient pas d'application ou redémarrage en production.

| Étape | Contenu | Retour arrière / dépendances |
|---|---|---|
| 01 | Sept modules serveur inertes, dont façade, authentification et admission; montage initial hybride forcé éteint | Pas de montage actif; ne pas retirer ces dépendances tant que 02 est monté |
| 02 | backend.mjs, voice-memory.py, store.py, server.js | Auth et routes legacy; flags Hermes éteints; retrait après désactivation et revue |
| 03 | index.html, hermes-missions.js/css, voice-router.js | Quatre ressources UI; restaurables sans changer les missions |
| 04 | Une ligne du montage autorisant le flag hybride explicite | Réversible seule; laisse auth, panneau et historique en place |

**15 chemins uniques**, contre 16 dans l'ancien patch. Les changements Live natif
`live.mjs`, `knowledge.mjs`, `voice-memory.mjs` ne sont pas nécessaires à ce pilote
hybride et ne sont pas copiés. Le garde Python `include_common` reste indispensable
pour memory/status. Le store empêche la réaffectation d'un ancien id de conversation
à un autre espace. Le petit chargeur vocal est nécessaire à la connexion sécurisée.

Ce sont des étapes à dépendances, pas quatre déploiements entièrement indépendants.
Les imports serveur imposent 01 avant 02; le login pratique nécessite 03.
Aucun allumage d'auth sur la gateway active entre ces étapes. L'ensemble est répété
sur copie isolée avant toute proposition d'activation réelle. Application puis
inversion de tous les patchs vérifiées octet pour octet sur copie temporaire. Le même test HTTP `/ask` passe également contre le backend
assemblé avec ce patch minimal et les modules de production non modifiés
(fournisseurs et runtime toujours simulés). Résultat dans le manifeste.

## Limites des preuves

`test_phase6_hybrid.mjs` utilise le handler `/ask`, le routeur hybride, un vrai
serveur bridge et SQLite temporaires. Un loader **réservé aux tests** remplace
les fournisseurs, le choix de route et l'archive à la frontière module; il n'est
jamais déployé. Les assertions vérifient les deux chemins ordinaires, zéro appel
classificateur/Codex pour Hermes, idempotence, ACL, refus d'approbation, provenance,
budget et absence de contexte privé. Le runtime de mission est simulé.

`test_phase6_ui.cjs --hybrid` exerce le vrai `window.jarvisAsk` et le panneau en
Chromium ordinateur/mobile, avec toutes les API simulées et réseau externe bloqué.
Le 401 initial puis la reprise du chargeur hybride sont testés. Ce test ne prouve
ni l'appel au vrai bridge depuis le navigateur, ni l'exécution matérielle Hermes.
La jonction navigateur + serveur minimal déployable + Windows doit encore être
observée lors du pilote autorisé. Les phases précédentes en restent les preuves
historiques, pas un substitut à cette nouvelle validation.

## Observation réelle du 15 novembre 2026

Les pilotes proposés ont été autorisés séparément puis terminés. P6-L1 démontre
le panneau avec le vrai runtime; P6-L2 démontre sa jonction au vrai `/ask` de la
copie minimale. Voir `JARVIS_2_PHASE6B_P6_L1_RESULTS.md` et
`JARVIS_2_PHASE6B_P6_L2_RESULTS.md`. Les limitations décrites plus haut sont celles
avant pilotes; les fournisseurs des demandes ordinaires restent simulés, la voix
micro et la production restent non activées. Les preuves historiques sont conservées.
