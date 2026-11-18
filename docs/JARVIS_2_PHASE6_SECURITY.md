# Phase 6 — Audit de la gateway active et sécurité préparée

## Audit réel en lecture seule

La gateway `codex-gateway.service` était active, PID observé 2033987, Node 18.19.1.
`/home/user/gateway/server.js` importe directement
`/home/user/workspace/jarvis/backend.mjs` et sert les fichiers d'interface depuis
`/home/user/gateway/public/jarvis`, qui est un dossier distinct de public dans
le dépôt. Ne pas confondre avec une copie publique GitHub.

Dans routeRequest, `/api/jarvis/*` est délégué **avant handleApi**. Le contrôle
isAuthorized au bearer du gateway ne s'applique qu'à d'autres familles de routes,
notamment S9 et iCloud. Le backend Jarvis vérifie des espaces et certains Origin,
mais ne fournit pas une identité serveur prouvée pour ses routes générales.

Un unique GET anonyme sur capabilities avec un espace volontairement inexistant
a reçu **400**, démontrant l'arrivée au contrôle métier sans authentification.
Aucun état privé, conversation, token, équipement ou réponse de fournisseur demandé.
Le corps n'a pas été conservé. Empreintes et observation :
`JARVIS_2_PHASE6_ACTIVE_AUDIT.json`. Aucune requête de pilotage, aucun test intrusif
sur une route de production autorisée.

**Configuration active observée : `hybrid`.** `voice-router.js` choisit
codex-voice.js et /ask pour ce mode ; backend refuse la session Live native dans
les modes codex/hybrid. Le code Live natif existe mais n'est pas le chemin actif.
Ce point empêche d'annoncer la voix de production intégrée sur la base du test Live.
Aucun changement du moteur, du routage ou de sa configuration effectué.

## Corrections isolées

- Registre d'identités serveur distinct du profil visuel et du master token du
  gateway ; bearers opaques hachés, expiration vérifiée à chaque appel.
- Connexion utilisateur : cookie HttpOnly, SameSite=Strict, Path=/api/jarvis,
  Secure sous HTTPS ; code saisi non stocké dans localStorage, pas de code dans URL.
- POST/DELETE protégés par l'Origin configuré côté serveur, pas le Host arbitraire
  de la requête. Origine HTTPS obligatoire, exception loopback pour les tests.
- Table serveur des espaces et rôles ; espace par défaut attribué par serveur,
  rejet des paramètres space multiples et des routes inconnues/non attribuées.
- Liaison des sessions Live à l'utilisateur et à l'espace ; impossible de réutiliser
  une session Live ancienne sans identité lorsqu'un appel authentifié arrive.
  Droits courants réappliqués aux outils, jamais les droits déduits de la réponse IA.
- Commun n'est plus inclus implicitement dans les faits/recherches vocaux d'une
  identité qui n'y a pas droit. Le frontend ne constitue pas cette ACL.
- La carte actuelle inclut Commun par construction : sa route est refusée sans
  droit Commun explicite, plutôt que de lire puis masquer ces points. Pas de
  refonte de la carte ni opération sur Qdrant historique.
- Déplacement de document : espace cible vérifié. Archivage vocal : expected_space
  serveur vérifié avant qu'une session connue impose son propre espace.
- Tous les accès Hermes passent par un client serveur configuré par utilisateur
  et espace, identité machine dédiée et endpoints loopback bornés ; pas de
  redirection ou de bearer bridge dans le navigateur.
- Modèle/caller incapable de choisir les outils, permissions, budget ou contexte
  mémoire de la première mission : template DoseLab synthétique fixe seulement.

Les descriptions, IDs, résultats et pages externes restent des données non fiables.
Le panneau utilise textContent ; une balise malveillante est affichée comme texte,
pas exécutée. Aucun iframe, script ou URL de modèle n'est ouvert automatiquement.

## Permissions de déploiement proposées

| Canal | Rôles/permissions minimaux | Interdictions |
|---|---|---|
| Utilisateur pilote | voice, missions.create/read/cancel, espaces explicitement attribués ; mémoire Jarvis seulement si explicitement attribuée | Pas de rôle physical, development, memory.admin, missions.approve par défaut |
| Identité serveur bridge | reader/mission_writer pour un propriétaire et un périmètre synthétiques précis | Pas de validation de faits, publication, shell ou Home Assistant |
| Worker contrôleur | mission_worker + proposer bornés, compte budget distant 0, profil/sandbox contrôlés existants | Pas de secret de production, promotion autonome, autorisation de minage |
| Approbateur humain | Session distincte missions.approve et credential Memory API distinct reader/human_approver, même propriétaire de mission autorisé | Acteur différent du créateur et du demandeur, fingerprint/expiration/once/deny imposés par le broker |

La configuration d'exemple est **inutilisable telle quelle** : empreinte fictive,
expiration nulle, origine invalide, aucun secret réel. Les comptes/rôles, la durée
de session, l'origine et chaque couple espace/credential restent à revoir avant
création de configuration privée. Aucun compte Windows ou changement d'ACL créé.
Ne pas partager un credential bridge entre espaces privés : les identités en aval
doivent réellement isoler ces périmètres, pas seulement changer le nom affiché.

## Routes héritées : obstacle volontaire à une activation générale

Le wrapper protège toutes les routes Jarvis qu'il intercepte. Les routes sync,
import, evolution, capabilities/run et **ask** sont refusées dans ce premier profil,
même si un rôle tente de les ouvrir. Le worker Codex historique conserve des
capacités shell/réseau larges : il n'est ni réutilisé ni transformé en worker Hermes.
Un simple token de session ne résout pas son confinement ou ses ACL fichiers.

Conséquence **matérielle pour le mode actif hybrid** : /ask est son chemin vocal et
écrit. Activer tel quel le profil sécurisé général sur la gateway active bloquerait
ce chemin. Ce patch n'est donc **pas autorisable comme activation transparente du
Jarvis actuel**. Revoir une délégation compatible avec le chemin hybride ou choisir
explicitement un laboratoire natif Live, sans modifier la production. Ne pas
contourner le blocage en accordant conversation/physical/development à Hermes.

Les endpoints voix legacy transcribe/speak ne sont pas convertis en API Hermes.
La non-régression des algorithmes audio est testée, pas un échange réel avec les
fournisseurs ni le confinement du worker Codex historique.

## Secrets, journaux et réseau

La configuration, chaque credential machine, l'audit et le switch sont des fichiers
privés, propriétaires du compte serveur et mode 0600 ; lstat refuse les liens
symboliques en cible et les droits trop larges. Répertoires parents privés à
prévoir lors de l'installation autorisée. Les chemins sont configuration serveur,
jamais arguments d'un outil du modèle. Aucun secret dans le patch/manifeste/Git.

L'audit d'admission contient sujet/espace/route/méthode/date, jamais corps, jeton
ou résultat ; écriture suivie de fsync, défaillance empêchant la délégation.
Les événements/actions/approbations restent dans SQLite. Les refus sont testés et
répondus ; un journal d'agrégation des tentatives de connexion hostiles, rotation
et quotas disque devront accompagner une exposition durable. Aucun test de charge
ou pentest général revendiqué.

Les interfaces restent privées, contrôleur loopback et SSH existant vers Windows.
Pas de port LAN/public, changement pare-feu/SSH ou service Windows permanent.
Le switch désactive Hermes en cas de fichier absent/invalide sans désactiver
l'authentification. Cela ne tue pas automatiquement une mission déjà admise.
