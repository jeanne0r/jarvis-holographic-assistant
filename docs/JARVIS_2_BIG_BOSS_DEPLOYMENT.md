# Lots de déploiement

Origine conservée : `https://192.0.2.16:8788`. Aucun lot n’est exécuté par cette préparation.

## A — Interface : premier lot recommandé

Candidat : `/home/user/workspace/jarvis-2-memory/data/big-boss/lot-a-ready/`.

**Exactement deux cibles :**

- `/home/user/gateway/public/jarvis/hermes-embedded.js`
- `/home/user/gateway/public/jarvis/hermes-embedded.css`

`manifest.json` contient les SHA-256 avant/après ; fichiers `.patch`, nouveaux assets et copies `.before` sont présents. Le manifeste consolidé Git `docs/JARVIS_2_BIG_BOSS_MANIFEST.json` en épingle les empreintes. La génération et l’inversion des patches sont testées sur copie. Les préparations antérieures restent conservées.

Après **accord spécifique pour ces deux fichiers** :

1. Vérifier espace disque (réserve d’au moins 16 Mio), absence de lien symbolique, propriétaire attendu et empreintes avant. Tout écart arrête la procédure.
2. Sauvegarder les deux assets et le manifeste dans un répertoire opérateur privé daté sous `gateway/data/backups/`, vérifier les copies par SHA-256. Aucune base ou identité à copier pour ce lot.
3. Appliquer uniquement les deux patches via fichiers temporaires et remplacement atomique de chaque cible en conservant propriétaire/mode. Vérifier les empreintes après.
4. Recharger Jarvis ; vérifier connexion actuelle, historique, résultat, détails, mobile et absence d’accès anonyme. Ne créer aucune mission. Vérifier flags d’admission/texte/voix/worker inchangés et gateway non redémarrée.
5. En cas d’anomalie : restaurer uniquement les deux assets depuis la sauvegarde vérifiée, après contrôle qu’aucune modification concurrente n’est apparue ; recharger. Aucune suppression de données ni modification de session. Les deux fichiers ne constituent pas une transaction commune : une page chargée entre leurs remplacements peut nécessiter un rechargement.

Impact : présentation uniquement ; aucune modification de `app.js`, du serveur, des mécanismes audio ou du service privé. **Pas de redémarrage requis.** Risque principal : compatibilité navigateur/présentation. L’authentification missions distincte est conservée provisoirement.

## B — Connexion unifiée : préconditions manquantes

Variante locale `data/big-boss/lot-b-single-session/`, **à ne pas installer** sur la gateway actuelle. Elle utilise les mêmes composants de sessions centrales que les tests d’identité, d’expiration et de révocation. Il faut d’abord terminer leur montage dans la gateway réelle, la compatibilité des clients et les identités/ACL explicites. Ne pas aliaser un cookie de gateway partagé ni élargir la confiance au profil/IP.

Un futur patch de gateway doit être revu avec ses propres empreintes et sauvegardes ; comptes, secrets, services et redémarrage nécessitent des accords distincts. Repli : connexion privée missions actuelle, sans substitution d’identité.

## C — Politique de création, puis exécution supervisée

Candidat minimal `data/big-boss/lot-c-policy/` : **quatre fichiers privés** (API, nouveau module de politique et deux manifestes). Les dépendances existantes ont été comparées ; imports du candidat et contrats HTTP testés. Aucune configuration, SQLite ou identité copiée. Le paquet conserve tous les flags désactivés.

Installation éventuelle après accord root : vérifier les quatre préimages, sauvegarder la release/configuration et SQLite par API backup avec restauration sur copie, déployer la release cohérente puis redémarrer uniquement le service privé avec validation BPF/auth/ACL. Garder admission/texte/voix/worker désactivés. Repli : ancienne release et manifestes ; préserver la SQLite courante, ne jamais l’écraser pour restaurer du code.

**Exécution = autorisation séparée.** Vérifier les nouvelles empreintes contre les lanceurs existants sans les forcer. Le reçu consommé n’est pas réinitialisé. Une future fenêtre doit conserver GPU/Kryptex/VRAM, une mission simultanée et quotas/coupe-circuit. Le défaut historique du contrôle final de provenance doit être corrigé et testé à partir des preuves existantes avant tout nouveau pilote ; aucune nouvelle exécution GPU n’est nécessaire pour diagnostiquer ce défaut.

Le mode texte est seulement synthétique, même lorsqu’une demande parle d’un projet réel : aucune récupération personnelle implicite. Aucune promesse de service Windows permanent ou de supervision quotidienne déjà opérationnelle.

## D — Voix

Réutiliser `/ask` hybride, l’admission serveur et les outils déjà testés. Activation séparée après identité fiable, lot C validé depuis le panneau et revue des flags. Les requêtes ambiguës doivent demander une précision ; aucun historique librement récupéré, aucun repli vers les permissions Codex. Sauvegarder le patch minimal exact avant toute écriture et prévoir le retour aux flags désactivés. Aucun changement audio préparé ici.

## E — Mémoire personnelle et apprentissage

Accord distinct sur projet, identifiants exacts des sources, lecture, indexation et éventuelle transmission Windows. Rapport privé à blanc avant import ; SQLite canonique/Qdrant reconstructible, expériences et compétences candidates seulement. Prévoir sauvegarde vérifiée hors stockage courant et gestion des clés avant transfert. Aucune de ces opérations n’est exécutée ou implicitement autorisée par ce travail.

## Exécution autorisée du lot A — 15 novembre 2026

Lot A installé après accord utilisateur sur le patch cc73bed. Exactement les deux assets prévus remplacés ; hashes HTTPS et sauvegardes/restauration sur copies vérifiés. Sauvegarde : `/home/user/gateway/data/backups/hermes-ui-A-20261115T204654Z-16bbad1e`. Les fichiers `.before` et `.restore-check` sont conservés, avec le manifeste et le résultat d’installation privés. Aucun redémarrage : gateway PID 2538966, service privé PID 2556916, inchangés. Page holographique 200, moteur hybrid conservé ; session et historique anonymes 401. Flags et fichiers serveur/audio inchangés ; aucune mission, Windows/GPU, API distante ou autre lot activé.

Le premier précontrôle local a refusé les modes 0775 des répertoires parents avant toute écriture. L’inventaire de groupe a ensuite établi qu’ils n’autorisent que le propriétaire user (aucun autre membre explicite ou primaire). Le contrôle final accepte uniquement cette équivalence d’identité ; aucune permission système n’a été modifiée. Répertoires applicatifs privés et assets restent à leurs modes existants.

L’affichage authentifié en production nécessite la session de l’utilisateur : aucun code opérateur privé n’a été lu. Les tests de présentation desktop/mobile et de session sont ceux de laboratoire sur les mêmes bytes, complétés par les vérifications HTTPS/auth anonymes réelles. Safari/iPhone physique reste une vérification utilisateur. Le rechargement de Jarvis suffit ; les lots B/C/D/E restent non activés. Preuve structurée : `JARVIS_2_BIG_BOSS_LOT_A_RESULTS.json`.
