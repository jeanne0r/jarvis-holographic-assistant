# Problèmes et limites ouverts

## Bloquant immédiat : superviseur non démarré

Le correctif `fe589cc` résout le plafond principal 16 Kio trop petit. Test synthétique avec 213 entrées et plus de 22 Ko de carte d'empreintes ; JSON d’identifiants toujours 16 Kio. L'erreur actuelle de lecture Python est distincte de l'ancien `200/CHDIR` conservé dans systemd. L'application réelle et le démarrage sous UID 995 restent non confirmés ; ne pas annoncer accord 3 opérationnel.

Correctifs successifs déjà présents : stdin privé lu avant SSH (`6049401`), code 750 root:groupe explicite malgré umask 077 (`cd3bc03`), diagnostic de chaque étape sans stderr secret et reprise des seuls changements reconnus (`496aef5`). Leur existence n'autorise pas à adopter une installation inconnue ou à refaire l'accord 3 complet.

## Sécurité globale et SSO : NO-GO maintenu

L'authentification forte du panneau ne couvre pas toutes les anciennes routes de gateway. Les adaptateurs persistants, la propriété, les comptes auxiliaires, le cycle des conversations/runs et la séparation fournisseur Codex ne sont pas tous validés dans l'entrée active. Le broker testé en laboratoire n'isole pas rétroactivement le worker actuel. Voir [SSO](../JARVIS_2_LOT_B_SSO.md) et [décision globale](../JARVIS_2_PHASE6_PRODUCTION_DECISION.md).

Un remplacement global de la gateway ne fait pas partie du prochain déploiement. Pas de rôle administrateur universel, pas de permission déduite d'un profil/du modèle, pas de clé partagée pour simuler une session humaine.

## Qualité des réponses

La mission textuelle du 15 novembre a utilisé les bons outils/révisions mais cité des UUID au lieu des URI `source.ref`. Analyse hors ligne : [HERMES_TEXT_CITATION_ANALYSIS.md](../HERMES_TEXT_CITATION_ANALYSIS.md). Sources disponibles dans les révisions ; aucune incompatibilité de format prouvée côté validateur. Limite : pas de capture intégrale des octets du contexte modèle ; ne pas inventer une certitude sur son attention interne.

Contrats MCP/bridge homogénéisés (`d14a2d5`), sans changer le texte historique ni la validation. Présence d'une citation ne prouve pas couverture de toutes les affirmations. P6-L1 conserve également une mauvaise date produite par modèle : le rendu UTC canonique est séparé et ne corrige pas silencieusement la réponse. Qwen 4B conserve 2 échecs antérieurs de sécurité ; aucune autorité de permission ne lui est confiée.

## Confidentialité, sauvegardes et généralisation

- C2 ancien lot mal borné en tours : reste bloqué, aucune transmission personnelle implicite. Le nouvel inventaire ne prouve pas l'absence d'autres conversations.
- Sauvegarde Qdrant restaurée mais même stockage/hôte ; chiffrement et conservation des clés avant copie externe encore à approuver. Pas de transfert pendant passation.
- Pas de preuve d'arrêt brutal du PC Windows en pleine mission réelle, de longue charge multi-utilisateur ni d'autostart. La reprise prudente est testée en simulation ; ne pas confondre redémarrage de processus et redémarrage du PC.
- Candidate doselab_freshness n'est pas une procédure industrielle publiée ; tests 3 puis 16 fixtures ne démontrent pas la sécurité d'un équipement physique.
- CT205 / embeddings actifs ne signifient pas transport vectoriel autorisé depuis superviseur. Ne pas ouvrir de flux supplémentaire pour « débloquer » sans revue.
- S9 de code et S19 Hydro de projet ne sont pas identifiés comme un même équipement. La boucle active reste inchangée ; aucun test physique.

## Limites de vérification de cette passation

Pas de sudo non interactif, pas de lecture du code privé superviseur/config 600, pas d'accès SQLite privée et personnelle. Donc : flags exacts actuels, état de chaque mission en attente, backup root, DACL complètes actuelles et attestation BPF courante non certifiés à neuf. Les preuves root opérateur restent des preuves historiques, pas des mesures actuelles.

L'écoute LAN 8787/8788 et d'autres services de cette VM a été observée ; aucune absence d'exposition Internet n'est démontrée par `ss` seul. Ne pas modifier pare-feu/SSH pour la passation. Le certificat TLS de l'origine doit être accepté/vérifié séparément par les clients.
