# Phase 4 — Hermes natif Windows : validation réelle

Le 14 novembre 2026, après accord A puis B, **le cycle synthétique Windows est réussi** : bridge sur Proxmox → Hermes natif Windows → Qwen3.5:4b sur RTX 3080 → MCP contrôlé → Memory Manager → expérience persistante et compétence candidate. Gemini et la gateway de production restent inchangés.

Preuves : [essai réussi](JARVIS_2_PHASE4_NATIVE_WINDOWS_RETEST_REAL.json), [contrôles et mesures](JARVIS_2_PHASE4_WINDOWS_VALIDATION_REAL.json), [snapshot SQLite vérifié après arrêt](JARVIS_2_PHASE4_MEMORY_SNAPSHOT_REAL.json), [tests locaux](JARVIS_2_PHASE4_TEST_RESULTS.json). Le premier essai échoué est conservé dans [NATIVE_WINDOWS_REAL](JARVIS_2_PHASE4_NATIVE_WINDOWS_REAL.json).

## Résultats effectivement obtenus

| Mission réelle | Résultat |
|---|---|
| 05877b20-3488-4f2f-a159-866f47bdf56a | Configuration actuelle : quatre cellules identiques de 1 kg ; anciennes capacités conservées dans l'historique ; sources de correction et d'origine citées. Recherche et historique MCP réellement appelés. |
| 0f3eda97-9e7b-4e1c-8fce-47656874190a | Expérience synthétique consultée, `doselab_freshness` version 1 proposée par Hermes ; provenance reliée à l'expérience confirmée. |
| 3d6a98bd-6fa1-4d3c-baf4-ea868ca5d136 | Après arrêt et nouveau démarrage natif avec HOME neuf, Hermes appelle skill_get et restitue la même candidate, ses sources et son empreinte complète. |

L'hôte évalue la candidate sur les **trois cas synthétiques prédéfinis : 3/3**. La tentative de publication avec l'identité agent est refusée. Le registre contient une candidate et **zéro compétence active**. Il s'agit d'une procédure déclarative limitée aux contrôles flow/freshness et à memory.search/report, sans script ni commande d'équipement. Le registre contrôlé ne publie pas de paquet SKILL.md chargé automatiquement par Hermes. Cela ne valide pas un apprentissage général ou une compétence industrielle.

Le simulateur Jarvis reçoit son identifiant en 15–21 ms. Les trois missions utilisent huit appels locaux, 34 596 tokens et 39,54 s cumulées d'appels d'inférence. Le contexte servi de 64 000 tokens est réellement observé dans /api/ps. Pic VRAM de la carte échantillonné : 6 945 Mio ; marge minimale : 3 295 Mio. Pic mémoire engagée du groupe Hermes : 360,8 Mio, sous le plafond 2 Gio ; Ollama : 7,69 Gio, sous le plafond 12 Gio. Ces compteurs Job Object ne sont pas des mesures RSS.

Énergie GPU estimée par interpolation des mesures carte : 2,61 Wh pendant le pilote réussi. Cela inclut chargement et périodes inactives ; ce n'est ni l'énergie du PC complet ni un temps CUDA mesuré. Aucun coût API distant, téléchargement de modèle ou appel Gemini supplémentaire.

## Installation réellement effectuée

Sur GAMER uniquement : compte standard `hermeslab`, profil distinct, clé SSH de laboratoire dont la partie privée reste sur le contrôleur, ACL NTFS, deux règles sortantes limitées à ce SID. Installation dans C:\JarvisHermesLab : source Hermes au commit `4959268e312a21a361f248e49030d5f5df3984d5`, uv 0.13.8 vérifié, CPython 3.14.10, environnement verrouillé de 94 paquets avec extras mcp/sms. Aucun outil SMS autorisé ; cet extra fournit aiohttp à l'API native. Python 3.10 et l'installation Ollama existante sont conservés.

SQLite canonique synthétique, registre des missions/compétences et Memory Manager restent dans le worktree sur Proxmox. Seuls trois jetons de laboratoire et du code sont transférés à Windows. Les sessions natives sont des traces d'exécution, mémoire factuelle Hermes désactivée. Aucun SQLite canonique, accès mémoire privée réelle ou donnée de production n'est transféré.

## Échecs, diagnostic et correctifs

CreateProfile refuse le tampon 1 024 caractères avec HRESULT 800706F7 ; l'appel de 260 caractères réussit. Le compte partiellement créé a été conservé, vérifié par SID et complété sans suppression. Windows refuse la notation pare-feu IPv6 ::/0 ; deux préfixes /1 couvrent la même plage. La politique PowerShell globale est inchangée ; les scripts relus sont exécutés avec Bypass pour le seul processus installateur.

Le premier appel modèle natif dépasse 60 s ; la réservation demeure conservée et le SDK rencontre ensuite le refus du quota. Le bridge enregistre failed, les processus sont arrêtés, aucune candidate n'est créée par cet essai. Ce n'était pas une clé API incorrecte, malgré le message générique du runtime.

Les comparaisons 8/12 Gio, contexte 4 096/64 000 et retrait temporaire des limites CPU/mémoire Ollama n'améliorent pas cette lenteur. Les protections sont rétablies. Le lanceur historique répond en 3,61 s ; le nouveau lanceur retrouve 3,26 s après restauration d'une liste de variables Windows usuelles et du PATH existant pour **Ollama seulement**. La variable précise responsable n'est pas isolée. Aucun secret fournisseur n'est transmis ; Hermes conserve son environnement réduit. Les deux profils de supervision gardent plafonds mémoire/CPU/processus, délai et arrêt du groupe possédé.

Le compteur d'essai indépendant est fermé : 17 tentatives réservées de manière conservative, dont des refus avant inférence, et 4 missions admises au total, y compris l'échec initial. Maximum autorisé : 24 appels/4 missions/30 minutes. Une fenêtre fermée ou épuisée interdit tout nouveau démarrage ; aucun ancien run ambigu n'est repris.

## Sécurité, tests et limites

Les contrôles Windows réels démontrent : compte non administrateur, refus de lecture du leurre privé, refus d'écriture du code/runtime/jeton, écriture des traces autorisée, DACL privées, loopback autorisé, nouvelles connexions HA/Qdrant/LAN/Internet refusées sous hermeslab et témoin administrateur non affecté. Le Job Object arrête son enfant et son descendant au délai ; une allocation de 3 Gio est refusée sous limite 2 Gio. Son compteur de pic inclut cette tentative refusée : il ne mesure pas 3 Gio effectivement résidents.

Les 13 commandes d'évaluation locales passent, avec les 20 tests mémoire initiaux, 30 de phase 2, 49 de phase 3 et 17 de phase 4 ; les tests phase 4 supplémentaires couvrent concurrence des quotas, fermeture de fenêtre et refus de démarrage. Les régressions Python/Node restent vertes. Les faux endpoints demeurent explicitement des simulations ; les trois missions ci-dessus utilisent le vrai runtime, le vrai modèle et la vraie RTX, sur des données synthétiques.

Un compte standard et un Job Object ne constituent pas une sandbox parfaite. L'arrêt brutal d'une mission en cours sur le vrai modèle et le redémarrage du PC n'ont pas été testés ; la reprise inconnue reste couverte en simulation. La liaison IPv6 du NIC LAN est désactivée et n’a pas été changée ; le filtrage externe IPv6 n’a pas pu être éprouvé. Le loopback IPv6 reste accessible aux deux comptes. Le modèle conserve ses deux échecs de sécurité du corpus antérieur : ses décisions ne valent pas autorisation. Aucun shell, web, HA, cron, sous-agent ou publication n'est exposé au modèle. L'évaluation de compétence reste trois cas fixes. Qdrant réel et CT205 ne sont pas raccordés ni modifiés.

## État final et suite

Hermes, Ollama, superviseurs et tunnels temporaires sont arrêtés, aucun port 8643/11434/8792/11436 n'écoute sur Windows. Kryptex UI reste présente, aucun mineur détecté ; aucune commande de minage, réglage GPU, pilote ou pare-feu global n'a été changé. Aucun autostart n'est installé. Le compte, les règles ciblées et les fichiers de laboratoire sont conservés pour revue.

VM102 reste arrêtée. Les SHA256 des configurations VM102/103/201 correspondent exactement aux références antérieures ; aucun gardien RAM actif observé. Aucun changement Proxmox, gateway, Gemini, Home Assistant ou production dans cette phase.

Prochaine étape : revue de cette candidate et préparation séparée du raccordement Qdrant expérimental. Une nouvelle fenêtre réelle exige un nouvel accord et des précontrôles frais ; aucune réouverture automatique du compteur, publication, connexion gateway, activation permanente ou intervention CT205 n'est autorisée par ce pilote.

## Comparaison avec le pilote Linux

Le pin Hermes, le modèle/digest, le contexte servi64 000 et le plafond Hermes2Gio sont conservés. La première mission Linux avait réussi avec11 575 tokens et un pic carte6 862Mio ; sa répétition Windows réussit avec13 002 tokens, pic carte du pilote Windows6 945Mio. Ces pics incluent le bureau et ne sont pas normalisés pour cette charge. La phase3 ne contenait aucune candidate validée ; Windows démontre maintenant proposition, évaluation3/3 et retrouvaille après redémarrage. Cela ne permet pas de réattribuer les anciens refus Linux dont les traces complètes restent sur VM102 arrêtée.
