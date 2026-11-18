# Phase 6 — Résultats de tests d'intégration isolée

Commande : `python3 scripts/evaluate_memory.py --phase6-integration`.
**22 commandes réussies**, avec les régressions précédentes. Trace complète :
`JARVIS_2_PHASE6_INTEGRATION_TEST_RESULTS.json`. L'ancien fichier de préparation
`JARVIS_2_PHASE6_TEST_RESULTS.json` et les preuves C1/B2 restent conservés.

| Vérification | Environnement réel/simulé | Résultat |
|---|---|---|
| Audit route active | Source réelle et un GET anonyme à espace invalide ; pas de contenu privé | Lacune auth confirmée, statut 400 |
| Sessions, expiration, usurpation | Serveur HTTP Node local, registre réel et tokens aléatoires synthétiques | Sans identité/expiré : 401 ; faux profil/autre espace : 403 |
| Cookie et CSRF | Cookie réel via HTTP loopback de test, Origin hostile simulé | HttpOnly/SameSite ; Origin hostile refusé |
| Route docs | Backend réel du worktree, synchronisation de fond désactivée, SQLite synthétique | Lecture autorisée ; aucune base personnelle |
| Outil Gemini Live | Vrai code liveSetup/createLiveSession/liveTool ; Google simulé | Mission admise queued, même callId idempotent ; aucun appel Gemini supplémentaire pour l'orchestration |
| Bridge et missions | Vrai HTTP Memory Manager et SQLite temporaires | Liste/état/événements/annulation et idempotence réussis |
| Mission et retour d'expérience | Faux runtime déterministe, vrai bridge et wrapper worker | Réponse sourcée via outil résultat ; expérience inferred conservée une seule fois |
| Autorisations humaines | Identités API writer/approbateur différentes, broker réel | Refus de l'agent et du mauvais fingerprint ; once accepté par compte humain distinct |
| Approvisionnement GPU | Télémétrie synthétique + tests existants phase 4 | Différé avant départ, budgets/reprise contrôlés ; pas un contrôle GPU réel de phase 6 |
| Contrôleur arrêté/redémarré | Arrêt vrai du subprocess serveur local puis réouverture SQLite | Missions queued conservées ; aucun rejeu natif implicite |
| Transport | HTTP loopback réel, réponses trop longues/lentes/redirect simulées | Refus/bornes, pas de redirection ni injection d'en-tête Authorization |
| Switch de sécurité | Fichiers privés réels temporaires et vrai mount | Désactivation/invalidation du switch : Hermes bloqué, authentification encore requise |
| Interface | Navigateur headless réel, API intégralement simulées | Desktop/mobile, XSS inerte, résultats et approbations affichés sans déclenchement audio |
| Non-régression audio | `test_live.mjs`, fournisseur simulé, code audio client inchangé | Config native/interruption, limites, erreurs expurgées et rééchantillonnage 16/24/44,1/48 kHz réussis |
| Patch | Copie locale temporaire des fichiers actifs | Dry-run et application vérifiés octet par octet, aucune écriture production |

`test_phase6_gateway.mjs` vérifie aussi l'impossibilité d'appeler une commande
physique ou une mémoire commune non autorisée depuis une session Live ; ajout
arbitraire d'objectif à un template rejeté. L'archivage vocal hors espace et la
lecture de faits sans Commun sont couverts par fixtures Python.

## Ce qui n'est pas démontré

- Aucun échange phase 6 avec le vrai Gemini payant, runtime Hermes Windows ou RTX.
- Aucun nouveau test C1, import personnel, Qdrant historique ou matériel physique.
- Le chemin vocal de production est **hybrid**, pas celui du test Live natif.
  Ses tests existants passent mais ne prouvent pas le confinement du worker Codex
  ni l'intégration Hermes dans /ask. Ce profil le refuse volontairement.
- Pas de test Safari/iPhone réel, charge longue, panne du PC matériel, redémarrage
  complet de gateway active ou publication de compétence.

Les premiers essais navigateur ont échoué faute de bibliothèques du binaire
Chromium complet. Résolution sans installation par le headless shell/sysroot déjà
présents. Deux défauts d'attentes de test ont aussi été corrigés : exception de
transport synchrone et statut HTTP de refus 403. Les succès finaux ci-dessus ne
présentent pas ces passages comme des essais matériels réussis.
