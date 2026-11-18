# Mise en service du worker existant — décisions à autoriser

Développement isolé uniquement. La production conserve son panneau en consultation/annulation. Aucun service, switch actif, donnée personnelle ou équipement n'a été modifié pendant ce travail. Aucun démarrage Windows/Ollama, appel distant ou installation.

## Raccordement préparé

Le service privé conserve sa SQLite, ses comptes, sessions, ACL, ports 8796/8797 et son gardien BPF. Le nouveau point de composition réutilise `Bridge`, les ticks phase4/phase6, `HermesRuns`, `Gate`, les budgets et les migrations/reçus de lecture phase6d. Il ne possède aucun client SSH ni lanceur Windows. Un verrou OS empêche deux contrôleurs de tourner sur la même base.

Admission humaine rapide, identifiant d'idempotence stable, une mission en attente/exécution à la fois. Permissions et budget sont reconstruits côté serveur : outils `memory.search, report`, contexte personnel vide, zéro coût distant, 98 304 tokens, six appels, 240 secondes par mission. La porte d'inférence conserve son plafond interne de 180 secondes. Une fenêtre d'exécution autorisée de 300 secondes permet **une seule exécution**, même après redémarrage ; elle ne limite pas la durée du service interactif.

Le modèle reste Qwen3.5:4b, digest `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`, contexte 64 000, sortie 768 tokens par appel. Aucun téléchargement, fournisseur distant, outil shell, contrôle physique, promotion de faits ou publication de compétence. Les réponses de plus de 8 000 caractères sont conservées par fragments et empreinte, jusqu'à 32 000 caractères ; au-delà, la limite est signalée explicitement.

L'identité MCP ne peut que lire la mémoire synthétique de la mission active. Le serveur enregistre les reçus des réponses autorisées et réutilise la projection SQLite existante : dates/provenance distinctes de la réponse non vérifiée du modèle. Le contrôleur conserve le résultat comme épisode `inferred`, sans le promouvoir.

Le superviseur extérieur conserve ses clés SSH privées hors du compte applicatif ; son nouveau jeton ne permet qu'observations/heartbeat. Il réutilise les lanceurs et Job Objects Windows existants, avec arrêt des seuls processus créés. Les tunnels restent loopback, chiffrés, avec clé hôte épinglée : API native 8643, Ollama 11435→Windows11434, mémoire Windows8792→Proxmox8797, porte modèle 11436. Aucun changement SSH/pare-feu/compte Windows. La porte modèle déjà liée par le service est attestée par le canal superviseur authentifié ; tous les autres contrôles de ports libres sont conservés.

Disponibilité issue d'observations séquencées/expirantes et d'une vérification authentifiée de `/v1/models`. Kryptex actif, VRAM <8 500 Mio, charge ≥20 %, télémétrie périmée ou API absente empêchent le départ. Entre deux appels, une observation indépendante postérieure à l'inférence précédente est attendue au maximum trois secondes, sans relâcher les seuils. Une soumission ambiguë est marquée `unknown/paused`, jamais recréée automatiquement. Toute ancienne exécution incertaine bloque les nouvelles.

## Patch minimal et ordre

Le manifeste `HERMES_OPERATIONAL_MANIFEST.json` donne toutes les empreintes avant/après, les fichiers de la release privée et les 13 sources du superviseur. Les candidats se trouvent sous `data/operational/` ; aucun artefact historique n'est remplacé. L'unité système et ses protections restent identiques. `server.js`, le backend et les scripts audio ne sont pas modifiés.

Release finale : `data/operational/final`, 67 fichiers vérifiés ; SHA-256 du manifeste : `34abd3ab6c1fe9fad12e3eecb2df77bde963335bd528837ecf91d6f438884ed2`. Résultats ciblés : `HERMES_OPERATIONAL_TEST_RESULTS.json` (38 régressions Python, 13 nouveaux tests Python, 74 assertions HTTP).

1. **Accord installation reçu, exécution administrateur en attente.** Sauvegarder la release/configuration/SQLite synthétique et les seuls fichiers gateway concernés, vérifier l'espace et restaurer les sauvegardes dans des copies distinctes. Installer la release privée candidate et les deux modules gateway `hermes-embedded-relay.mjs`, `hermes-embedded-contract.mjs`, plus `public/jarvis/hermes-embedded.js`. Le CSS est identique : aucun remplacement nécessaire. Préparer les options privées à false. Appliquer la migration additive déjà existante (workers/reçus) uniquement à la base synthétique sauvegardée. Reprendre le seul pilote via le gardien supervisé et effectuer un redémarrage gateway dans une fenêtre autorisée ; pas de redémarrage improvisé pour le rollback. Le switch public de lecture est restauré à son état actuel après acceptation, mais admission/voix restent false. Vérifier les refus auth/ACL/BPF et le fonctionnement hybrid sans appel modèle.
2. **Accord première exécution, pas encore reçu.** Armer une fenêtre privée fraîche (300 s, 1 mission, 6 appels, 98 304 tokens, 0 CHF). Réutiliser exclusivement les trois justificatifs de laboratoire déjà présents `data/phase3/windows-20261114/{hermes,model,memory}.token`, sans les afficher, et créer un jeton superviseur distinct dans un fichier privé. Le service reçoit les justificatifs runtime sous son compte privé ; le superviseur extérieur ne reçoit que son jeton d'observation et les limites publiques. Aucun code opérateur n'est renouvelé/copié ici. Une reprise privée supervisée charge cette configuration, avec admission préarmée et texte/voix false ; le relais garde l'admission fermée jusqu'aux vérifications. Revalider les empreintes Windows et les protections réseau, puis démarrer temporairement les superviseurs Ollama/Hermes existants, sans modifier Kryptex. Le contrôleur authentifié et le superviseur doivent annoncer exactement la même échéance. Les contrôles BPF existants restent obligatoires ; leur ancien verdict queue-only ne doit pas être présenté comme une validation du nouveau worker : vérifier séparément le profil armé et sa porte d'inférence.
3. **Première mission humaine autorisée avec ce même accord.** Après disponibilité réelle, passer l'admission publique à true (le niveau privé est déjà préarmé), avec `textEnabled=false` et `voiceEnabled=false`. L'utilisateur clique « Retrouver les cellules DoseLab X4 » dans son Jarvis habituel. Le script ne crée aucune mission. Suivre le résultat, les sources exactes, les métadonnées canoniques et l'expérience persistée. Arrêter les seuls processus/tunnels détenus et fermer les fenêtres ; l'historique reste accessible. Refermer l'admission après ce premier essai avant de proposer une utilisation plus large. À l'échéance, les deux contrôles privés d'admission et la permission humaine de création se ferment aussi automatiquement, sans couper la consultation ni l'annulation.
4. **Accords ultérieurs distincts.** Le mode texte est prêt (1–2 000 caractères, question explicite seule, mêmes outils mémoire synthétiques ; aucun historique importé). La délégation est préparée dans une modification de `app.js` servi et source, séparée du lot panneau. Elle conserve le vrai point d'appel `window.jarvisAsk` utilisé par le mode hybride ; les conversations ordinaires continuent vers `/api/jarvis/ask`. Une demande Hermes passe par la façade authentifiée `/api/jarvis/hermes-panel/hybrid/ask`, réutilisant `hybridAdmission`, sans envoyer l'historique, ni invoquer Codex. Ce choix conserve le cookie privé dans son chemin actuel : pas d'élargissement vers les anciennes routes. Seul le template DoseLab explicite est admis pour la première voix. « Confie cette mission » sans objectif explicite est refusé plutôt que d'extraire un contexte privé. Aucun fichier audio n'est changé. Tester/activer la voix seulement après la mission panneau réelle.

Le lancement opérateur préparé est `python3 -m scripts.run_interactive_hermes --approved-worker-window --credentials <fichier-superviseur-0600> --window <fenêtre-0600> --output docs/<preuve-neuve>.json`. Il exige un service privé déjà armé par l'administrateur, vérifie ses préconditions et attend le clic humain. Il n'est pas autorisé ni exécuté à ce stade. Aucun service Windows permanent ou démarrage automatique.

## Retour arrière

Immédiat : switch `enabled:false`, sans restart, aucune suppression de mission ou de donnée. Pour revenir au panneau de consultation : admission/voix false. Arrêter les superviseurs par leurs demandes d'arrêt détenues, fermer les tunnels ; ne jamais arrêter Kryptex. La porte d'inférence refuse d'elle-même les appels après échéance. Les états incertains restent visibles et exigent réconciliation humaine.

Restauration du code/configuration depuis la sauvegarde vérifiée sous autorisation de maintenance ; conserver les justificatifs renouvelés et la SQLite la plus récente. Les tables additives peuvent rester sans être utilisées. Ne jamais écraser la base active avec un snapshot ancien. Reprise privée toujours sous validation BPF ; toute éventuelle deuxième reprise gateway nécessite présentation de la restauration avant exécution.

## Portée de la validation

38 régressions Python antérieures passent (mémoire, Windows, pilote interactif), ainsi que les 42 assertions HTTP historiques du panneau. Nouveaux contrôles : 32 assertions HTTP d'admission/identité/flags/voix ; tests contrôleur pour quotas, minage, VRAM, panne, annulation, persistance, absence de rejeu, résultats longs, refus MCP et propriété de la porte modèle ; candidat empaqueté exécuté avec vraie SQLite et HTTP. Chromium desktop/mobile valide soumission et annulation ; un scénario complet utilise des serveurs Hermes/Ollama **simulés** derrière les protocoles réellement raccordés, avec résultat/provenance affichés. Aucune nouvelle preuve RTX ou Hermes natif réel n'est revendiquée. Les fichiers et PID de production restent inchangés.

Les risques historiques des anciennes routes de la gateway ne sont pas déclarés résolus. Les nouvelles admissions utilisent exclusivement la session humaine privée et les ACL du panneau, jamais un profil visuel ou les permissions du worker Codex.


## Installation autorisée — exécution administrateur

Le lanceur `ops/pilot-network/install-operational-panel.py` couvre uniquement le premier lot autorisé. Il vérifie les 67 artefacts, les préimages et les sources du superviseur, conserve l'unité système et appelle son démarrage supervisé BPF existant. Il n'installe que les trois fichiers gateway cités au point 1 ; les deux `app.js` vocaux et le CSS restent inchangés. Aucune création de compte ou modification d'unité/pare-feu.

Après fermeture de l'interface vocale, dans un terminal administrateur :

```bash
sudo python3 -B /home/user/workspace/jarvis-2-memory/ops/pilot-network/install-operational-panel.py --install-approved --voice-closed
```

`--voice-closed` est une attestation de fermeture de l'interface ; les endpoints existants ne savent pas dénombrer les sessions vocales. Les runs doivent être absents et le cgroup gateway sans processus enfant. Une activité inconnue suspend l'opération avant le redémarrage. Aucune interrogation du S9.

Les sauvegardes sont conservées sous `/var/backups/jarvis-hermes/operational-*`, dossier root 0700 : release originale, état privé, snapshot SQLite restauré sur une copie indépendante, configuration et fichiers gateway originaux avec modes/propriétaires/empreintes. Une réserve de 256 Mio s'ajoute au volume de travail calculé avant toute écriture. Les tables canoniques existantes doivent rester identiques ; seuls les ajouts de schéma workers/reçus et leur état technique sont attendus. Une mission incertaine bloque l'installation. Aucun snapshot n'écrase une base existante.

Les trois justificatifs Windows désignés sont contrôlés uniquement par leurs métadonnées et tests de lecture sous d'autres identités. Aucun n'est lu ni copié. La protection 0600/0700 n'isole pas deux processus sous le même UID user : cette limite est explicitement conservée et leur éventuelle réutilisation exigera une décision distincte. Les accès privés renouvelés du lot R sont conservés.

L'acceptation contrôle auth, ACL, historique, origine HTTPS, session sécurisée puis fermeture de cette seule session, refus d'admission/voix/approbations (charges volontairement invalides), santé, assets et moteur hybrid. Aucun appel modèle ni commande physique. Les sessions panneau en mémoire peuvent nécessiter une reconnexion après reprise du service privé. Le worker et ses ports restent arrêtés ; aucune identité runtime n'est provisionnée.

Sur échec après modification, le lanceur demande switch false et arrêt du seul pilote ; il ne tente jamais un deuxième redémarrage gateway. Examiner `plan.json` et les originaux dans la sauvegarde avant restauration. Garder la SQLite la plus récente et les justificatifs du lot R. Les noms `gateway-0..2` et leurs chemins/modes sont consignés dans `plan.json`. Une restauration de code nécessitant un second redémarrage doit être présentée avant exécution.

Préparation vérifiée hors production : six tests ciblés de l'installateur passent (manifestes/périmètre, flags, refus non-root, liens et permissions, sauvegarde/restauration et migration désarmée sur SQLite synthétique, contrôles HTTP simulés). Aucun résultat d'installation root ou de redémarrage n'est encore revendiqué. `sudo -n true` demande actuellement un mot de passe dans la session de l'agent ; utiliser le terminal administrateur sans transmettre le mot de passe au chat.


## Point de reprise de l'installation interrompue

Le retour administrateur de l'essai `operational-20261115T185027Z-37511961` indique un OSError, zéro redémarrage gateway et arrêt sûr. Le diagnostic administrateur ultérieur confirme la release candidate exacte, l'ancienne release sauvegardée, les préimages gateway inchangées, tous les flags false, aucune identité runtime, la validation du layout, l'égalité snapshot/restauration/SQLite active et les ports libres. La cause historique précise reste indéterminée : un conflit de port transitoire n'est pas démontré. Aucun contournement de BPF ni modification du coordinateur épinglé.

Une reprise explicite de ce seul checkpoint est disponible, sous le même lot d'installation autorisé. Fermer d'abord l'interface vocale :

```bash
sudo python3 -B /home/user/workspace/jarvis-2-memory/ops/pilot-network/install-operational-panel.py --resume-approved --voice-closed
```

Elle vérifie à nouveau les empreintes, les sauvegardes, les identifiants privés inchangés, l'absence de mission incertaine, la SQLite identique au snapshot, les ports, l'espace disque et l'inactivité gateway. Elle refuse tout état différent, résultat déjà réussi ou précédente demande de reprise/redémarrage. Elle ne réinstalle ni la release ni la configuration et n'écrase aucune base. Un reçu de reprise à usage unique puis un reçu de demande de redémarrage sont persistés avant les opérations correspondantes. Le gardien BPF reste obligatoire avant toute pose de fichiers gateway. Le panneau ne retrouve son état de consultation qu'après acceptation. Admission, texte, voix et worker restent false. Un nouvel échec conserve l'arrêt sûr, expose désormais l'étape et errno sans secret et exige une inspection ; aucune répétition automatique.

Huit tests ciblés passent, dont refus d'un checkpoint ou secret modifié et preuve qu'un refus BPF interdit toute acceptation ou commande gateway. Ces tests sont hors production. La gateway conserve le PID 2516015 et le pilote est arrêté au terme de la préparation ; aucune reprise n'est encore revendiquée.


## Finalisation après le redémarrage déjà effectué

La reprise administrateur a passé le démarrage privé supervisé et posé les trois fichiers gateway, puis effectué le redémarrage autorisé (PID 2516015 → 2538966). Un PermissionError au contrôle post-redémarrage a laissé le switch false et arrêté le pilote. Les lectures indépendantes confirment ensuite santé HTTPS 200, interface/assets 200, voice/live 200, moteur hybrid, empreintes attendues et scripts voix inchangés. Le détail historique du PermissionError n'a pas été enregistré et sa cause précise n'est pas déclarée prouvée.

Un défaut du vérificateur est identifié : il réutilisait après redémarrage la condition de maintenance « aucun processus enfant », alors que le backend existant programme `sync()` deux secondes après import. Ce contrôle peut donc refuser un démarrage normal. Le contrôle d'inactivité reste strict **avant** toute intervention/reprise de gateway ; après démarrage, il vérifie service, nouveau PID et santé HTTPS. Aucun enfant n'est tué ni aucune synchronisation arrêtée. Le backend reste inchangé.

Le contrôle final dédié ne modifie aucun fichier gateway et ne contient aucune commande de redémarrage gateway :

```bash
sudo python3 -B /home/user/workspace/jarvis-2-memory/ops/pilot-network/install-operational-panel.py --verify-installed --voice-closed
```

Il exige le reçu du premier redémarrage, le checkpoint exact, les bonnes empreintes avant/après selon le fichier, les identifiants privés inchangés et la sauvegarde restaurable. Les tables canoniques originales doivent rester intactes ; les deux tables techniques additives workers/reçus sont autorisées. Il reprend uniquement le pilote privé sous son gardien BPF, contrôle ses ACL puis le relais HTTPS existant, et remet le panneau en consultation seulement après acceptation. Un reçu à usage unique interdit une répétition aveugle. Admission, texte, voix et worker restent false. Sur nouvel échec : panneau false, pilote arrêté, étape précise affichée, aucun redémarrage gateway.

Dix tests ciblés passent, dont le véritable protocole HTTP de connexion/historique/refus/logout via le relais et le service privé empaqueté sur ports éphémères et SQLite fictive. Le contexte de contrat est HTTPS ; ce test local utilise HTTP loopback et ne prétend pas vérifier TLS. TLS de production est vérifié séparément par les GET ci-dessus. Aucun Hermes/Windows/GPU ni fournisseur n'est lancé. La finalisation root reste à exécuter et aucun résultat positif n'est anticipé.


## Réconciliation ciblée Windows / contrôleur Proxmox

Autorisation de première fenêtre reçue ; aucun démarrage ni mission effectué. Le refus d'empreinte est expliqué et levé par une attestation par cible, sans installation Windows :

- Windows : `windows.py` correspond octet pour octet au commit `5e9469d2be9e922a60eccdf2e227534e540a4359`, SHA-256 `53df3cbfa2e76b5069204afa1b4e8ba5136bb8e328fb67a01a32da2ef50a652a`, déjà présent dans les preuves phase5C conservées.
- Proxmox : version `10bf3b43097cef5b59d55febfe74df595489a295`, SHA-256 `0797d19af9d0134e9dd7239596da7d68b584c01d1b76980161a8dc0f61a6c3a2`. Seule différence : paramètre host `memory_port`, borné à 8792/8797, et destination locale du reverse SSH. Profil MCP avec/sans compétences identique, arguments SSH par défaut identiques. Aucun changement de comptes, ACL, pare-feu, confinement, outils ou gardiens GPU/Kryptex. Les sept autres fichiers de l'application Windows sont identiques à leur version host.

Les nouveaux manifestes `HERMES_OPERATIONAL_WINDOWS_BINDINGS.json` et `HERMES_OPERATIONAL_RECONCILED_MANIFEST.json` conservent l'ancien manifeste opérationnel et les preuves historiques intacts. Le premier épingle distinctement les huit empreintes host/Windows ; son SHA est fixé dans l'attesteur. Le second référence la base immuable et les 13 sources superviseur effectives, avec seulement deux deltas : sélection du profil d'attestation opérationnel et son vérificateur. Les anciens pilotes conservent leur comparaison stricte par défaut ; aucune liste d'empreintes alternatives n'est acceptée. Le worker opérationnel choisit explicitement l'attestation dédiée. Toute autre dérive échoue.

Cinq tests ciblés passent : provenance Git, invariance des profils/arguments et restriction des ports ; empreintes exactes acceptées et dérive refusée ; comportement historique strict ; refus de dérive host/manifeste ; conservation des preuves et cohérence des 13 sources effectives. Nouvelle attestation Windows réelle en lecture seule : 8/8 fichiers conformes. Précontrôle GPU en lecture seule : 9195 Mio libres, 0 % de charge, minage non détecté ; cette observation devra être renouvelée avant tout départ.

La préparation peut reprendre sous l'autorisation de fenêtre existante, mais l'armement administratif devra vérifier le nouveau manifeste superviseur effectif tout en conservant les empreintes de release installée de la base originale. Aucun script d'installation historique ne doit être rejoué ni aucun manifeste remplacé pour forcer un contrôle. Dans la session de l'agent, `sudo -n true` exige encore une authentification : aucun armement de la configuration privée, redémarrage de service ou accès privilégié n'a été effectué. Admission/texte/voix/worker restent fermés ; le panneau demeure en lecture/annulation. Aucun fournisseur, mission ou équipement démarré.


## Commande administrateur de la première fenêtre humaine

Le raccordement administratif `ops/pilot-network/run-worker-window.py` est préparé, sans exécution privilégiée dans la session de l'agent. Il réutilise le service installé, le coordinateur BPF épinglé, le manifeste réconcilié 89b637d et le superviseur `run_interactive_hermes` existant. Ce script ne remplace aucune release, n'installe rien sur Windows, ne redémarre jamais la gateway et ne crée aucune mission.

Dans le terminal SSH habituel de la VM Codex (`user@codex-cli`, 192.0.2.16), garder le terminal ouvert et exécuter :

```bash
cd /home/user/workspace/jarvis-2-memory
sudo python3 -B ops/pilot-network/run-worker-window.py --approved-first-window
```

Ne pas rejouer les commandes install/resume/verify-installed. Le précontrôle est en lecture seule : version par machine, archive Hermes, pare-feu, ports, GPU/minage, trois identités nommées identiques à Windows sans les afficher. Après réserve disque et sauvegarde/restauration SQLite sur copie : arrêt du seul pilote, attente stricte des ports libres, reçu root de fenêtre à usage unique, configuration 300 s/une mission/6 appels/98304 tokens/0 CHF, démarrage privé supervisé BPF. Le worker reste Windows natif, mémoire synthétique, aucun shell ni donnée personnelle.

Le profil armé est vérifié séparément du contrôle queue-only : échéance/epoch authentifiés identiques, modèle exposé Qwen3.5:4b et contexte 64000, refus 401 sans identité modèle. Le superviseur démarre ensuite temporairement ses seuls processus/tunnels détenus. Le relais public reste en lecture jusqu'à disponibilité authentifiée effective. Le message JSON **`worker-ready-click-now`** est le seul signal autorisant le clic « Retrouver les cellules DoseLab X4 ». Ne pas attendre un aller-retour dans le chat à partir de ce signal : l'échéance absolue et les secondes restantes figurent dans le terminal. Le panneau peut demander une reconnexion, le code opérateur existant ne change pas. Aucun clic automatique.

Dès qu'une exécution est liée, le relais referme l'admission. Aucune ancienne mission active/queued/incertaine n'est adoptée. Après la mission ou l'échéance : nettoyage par les superviseurs existants, contrôle des listeners Windows fermés, retour du seul pilote en consultation sous nouveau contrôle BPF, configuration sans identités runtime ni admission. Le reçu d'usage interdit une deuxième fenêtre sans revue, même si aucun clic n'a eu lieu. Sur saturation, anomalie ou contrôle refusé : arrêt sans adoption de processus/listener, sans port réutilisé de force ni fallback. Un nettoyage non démontré n'est jamais déclaré réussi.

Les résultats sont vérifiés depuis la SQLite/les reçus : au plus une nouvelle mission, budgets, provenance exacte synthétique, citation explicite source.ref, expérience enregistrée ; état vérifié après reprise privée. Les réponses restent non vérifiées, aucune promotion. Les preuves et rapports sont privés sous `data/operational/window-*` et `/var/backups/jarvis-hermes/worker-*` ; aucun secret n'est affiché. `status.json` permet au Codex courant de suivre disponibilité/fermeture sans lire de justificatif. Le rapport final ne contient pas de conversation personnelle ni de jeton.

Sept tests ciblés du raccordement administrateur passent : bornes et profils, identité distincte et refus de dérives, empreintes, refus non-root, refus d'un précontrôle enfant, absence de POST mission/redémarrage gateway/installation Windows et exactitude des dépendances épinglées. Ils ne prétendent pas valider une nouvelle exécution GPU. Aucune commande administrateur ni mise en route effective n'a été exécutée pendant cette préparation.


Le premier appel administrateur a refusé avant le message `read-only-preflight`, sans dossier de fenêtre ni changement des services observés. Les empreintes installées et les sources superviseur ont été revérifiées en lecture seule : conformes. La raison précise du PermissionError reste à diagnostiquer ; aucune cause n'est supposée. Le lanceur offre désormais `--diagnose-only`, qui s'arrête avant toute vérification distante, sauvegarde, armement, écriture de reçu ou modification de service. Sur refus, il affiche le contrôle, la fonction et le numéro de ligne, sans texte d'exception ni valeur locale. Commande : `sudo python3 -B ops/pilot-network/run-worker-window.py --diagnose-only`. Ne pas réessayer l'armement avant cette vérification. Huit tests ciblés passent, dont le retour du diagnostic avant tout précontrôle distant ou écriture. Nouveau manifeste diagnostic distinct ; le manifeste initial et ses preuves restent conservés.


Le diagnostic administrateur après annulation de l'ancienne mission passe désormais la file et refuse à `distinct-runtime-identities`. Un défaut de lecture est identifié dans le nouveau lanceur : il comparait les textes bruts des fichiers avec une règle interdisant les fins de ligne, tandis que `phase3/lab.py` écrit explicitement une fin LF et que le chargeur Windows validé `phase4/credentials.py` applique déjà `read_text().strip()`. Le lanceur adopte ce contrat en mémoire uniquement, avec longueur 32–256, refus des espaces internes et contrôle d'unicité des cinq valeurs réellement utilisées. Aucun fichier de jeton ni identifiant n'est modifié. Une éventuelle collision véritable reste bloquante et doit être confirmée par le prochain diagnostic ; aucune unicité des secrets réels n'est anticipée.

Le précontrôle Windows compare dorénavant les valeurs effectivement chargées, plutôt que des empreintes de fichiers sensibles aux fins de ligne. Il épingle d'abord le chargeur credentials.py existant au SHA `56a87075e51c7aa2074c4c70ba7367dca33bbdee5639e55a72dc9d333584c684` du commit f1f2ec6, puis l'utilise en lecture seule sous hermeslab via SSH épinglé, avec ses contrôles DACL d'origine. Les empreintes de valeurs restent dans le canal capturé, jamais imprimées ou enregistrées. Le chargeur Windows a été revérifié réellement en lecture seule : conforme. Aucun processus modèle n'a été lancé. Dix tests ciblés passent, dont LF/CRLF, absence de modification de fichier et rejet des collisions après lecture, des espaces internes et des jetons trop courts.

La même chaîne `--diagnose-only && --approved-first-window` demeure applicable : seul un diagnostic réussi peut atteindre le précontrôle Windows, puis l'armement. Les manifestes administrateur précédents sont conservés ; le nouveau manifeste de lecture TOKEN_READING documente les empreintes effectives. Aucun contrôle de budget, BPF, GPU, minage ou identité distincte n'est supprimé.


Le précontrôle Windows sous administrateur a atteint le délai global de 180 secondes avant toute sauvegarde/activation de fenêtre. Les services et le switch de consultation sont inchangés, aucun dossier de fenêtre n'est créé. Mesures non privilégiées en lecture seule : archive Hermes 25615/25615 fichiers en 23,4 s ; précontrôle complet avec comparaison effective des trois identités et DACL Windows en 29,5 s ; même précontrôle avec stdin privé et capture subprocess en 30,7 s. Aucun modèle ni processus GPU lancé. Le timeout spécifique à l'enveloppe administrateur n'est pas expliqué définitivement par ces mesures.

La collecte du précontrôle administrateur est désormais observable et utilise deux fichiers temporaires privés non liés pour stdout/stderr, afin de ne pas dépendre de l'EOF d'un descripteur hérité par un descendant. Les entrées sensibles restent sur stdin. Seuls des événements/métadonnées explicitement filtrés sont affichés, jamais les autres champs de sortie ni stderr. Une session de processus locale dédiée permet le nettoyage des seuls descendants de cette vérification en lecture seule, sans signaler de processus Windows, mineur, gateway ou service. Le plafond reste 180 secondes ; les seuils GPU/VRAM/minage, empreintes, DACL et quotas ne changent pas. Le contrôle reste en refus si un délai ou une étape échoue.

Diagnostic administrateur Windows seul, avant toute activation : `sudo python3 -B ops/pilot-network/run-worker-window.py --diagnose-windows`. Cette option retourne après la vérification Windows, avant sauvegarde, reçu d'autorisation, arrêt de service ou armement de la fenêtre. Treize tests ciblés passent, dont stdin privé, absence d'attente d'EOF d'un descendant, arrêt au timeout, filtrage des champs privés et retour du diagnostic avant toute modification. Ces contrôles ne constituent pas une validation root réelle ; celle-ci reste à recueillir. Nouveau manifeste PREFLIGHT_IO distinct, preuves précédentes conservées.

### Refus BPF de la première fenêtre — 2026-11-15 19:56 UTC

Le précontrôle Windows administrateur a réussi. Le service privé a refusé son ExecStartPre, puis sa restauration en lecture seule a rencontré le même refus. La gateway reste active, PID 2538966 ; son switch est revenu à `{"enabled": true}` (admission absente/désactivée). Aucun superviseur Windows ni aucune mission n’a été lancé par ce chemin : l’échec précède leur lancement.

Cause logicielle reproduite hors ligne : `run-worker-window.py` impose umask 0077 ; `GATE.mkdir(mode=0755)` produisait un dossier root 0700 inaccessible au compte applicatif. Correction locale : chmod explicite 0755 uniquement du rendez-vous éphémère non secret, toujours root et non inscriptible par autrui. Les secrets restent 0600, leurs dossiers privés inchangés ; les tests BPF et leurs témoins restent obligatoires. Le coordinateur est à nouveau épinglé ; les anciennes empreintes/preuves sont conservées.

Validation : 14 tests ciblés réussis, dont exécution des instructions réelles de création sous umask 0077, contrôle du dossier 0755 et du secret 0600. Pas de test réseau, service ou GPU exécuté pour ce correctif.

La restauration effective du service privé requiert une exécution administrateur et une vérification préalable que toutes les opérations sont désarmées. Le reçu à usage unique doit rester intact : ne pas relancer `--approved-first-window`, ni supprimer ce reçu. Une nouvelle fenêtre nécessitera une autorisation distincte et un mécanisme explicitement lié à la tentative échouée. Aucun fichier installé, compte, unité ou service n’a été modifié par ce correctif local.

### Restauration refusée — 2026-11-15 20:00 UTC

Le dossier corrigé permet désormais au guard d’atteindre la sonde (refus après environ sept secondes), mais le fichier approved.json créé via open(mode=0644) restait 0600 sous umask 0077. Le premier correctif était incomplet. La correction prépare maintenant le reçu non secret en fichier exclusif 0600, écrit et synchronise le JSON complet, applique explicitement 0644 puis publie par lien atomique sans remplacement. Le temporaire est nettoyé en succès et en échec. Aucun assouplissement de BPF, des identités, des secrets ou de la fraîcheur nonce/session.

16 tests ciblés réussis, dont observation du contenu complet et des permissions au moment exact de publication sous umask 0077, refus d’écrasement et nettoyage en échec. Aucun service/GPU lancé par ces tests. Le service privé reste failed ; la gateway active PID 2538966 et son switch lecture seule sont inchangés. La restauration administrateur déjà autorisée est préparée via restore-readonly-pilot.py, avec contrôles de profil désarmé, SQLite, reçu consommé conservé et gateway inchangée. La fenêtre GPU n’est pas réarmée. Les erreurs futures exposent seulement type, fonction et ligne, sans contenu privé.

### Diagnostic et contrôle exact du heartbeat

Le diagnostic administrateur confirme uniquement p6d_workers modifié (une ligne avant/après), gateway PID 2538966 inchangé, toutes opérations désactivées, service privé inactive, reçu préservé. Le démarrage précédent avait passé supervised_start et ses validations BPF/auth/ACL, puis le contrôle trop large de toutes les lignes SQLite avait arrêté le service.

Le contrôle de restauration compare toujours exactement toutes les autres tables. Pour p6d_workers uniquement, il exige une unique ligne existante, les identités exactes windows-hermes/phase3-synthetic/operational-controller conservées, un nouvel epoch UUIDv4, sequence=0, seen=NULL et state=unknown. Tout autre changement reste refusé. Le résultat dit canonical_tables_unchanged et worker_heartbeat_reset_verified, sans prétendre que toute SQLite est immuable. Aucun reçu n’est supprimé, aucune admission/observation/mission n’est créée.

Validation hors ligne : 20 tests réussis au total. Les quatre nouveaux tests exercent le vrai heartbeat.register sur SQLite en mémoire, puis refusent changements canoniques, changement d’identité, observation, epoch rejoué/invalide, worker absent ou supplémentaire. Restauration administrateur toujours à exécuter depuis le terminal utilisateur, sans nouvelle fenêtre GPU.

### Reprise explicitement autorisée après restauration validée

La restauration administrateur a réussi : BPF ingress/egress et témoins vérifiés, authentification/ACL validées, canonical_tables_unchanged, heartbeat reset vérifié, gateway inchangée, opérations désactivées. L’utilisateur a demandé « on relance le test alors ? », autorisation d’une nouvelle tentative dans le périmètre précédemment fixé.

Entrée dédiée : run-worker-window.py --approved-recovery-window. Elle conserve sans suppression le premier reçu, exige l’identifiant exact de l’échec BPF 20261115T195459Z-a89456c1, le snapshot/configuration associés, aucune trace de lancement du superviseur précédent, aucune modification des tables canoniques hors heartbeat et aucune mission non terminale. Elle utilise un nouveau reçu root exclusif first-operational-window-recovery-used.json lié à l’empreinte du premier reçu. Une seconde utilisation est refusée. Tous les contrôles Windows, empreintes, BPF et GPU sont réexécutés ; 300 s, une mission synthétique créée par l’utilisateur, six appels, 98 304 tokens et 0 CHF sont conservés. Pas de suppression de données ni de réactivation de mission précédente.

22 tests locaux ciblés réussis. Aucune fenêtre ni service/GPU démarré par l’agent pour cette préparation. L’utilisateur doit exécuter la commande administrateur dans son terminal et attendre worker-ready-click-now avant de cliquer dans Jarvis.

### Fenêtre réelle terminée — contrôle final de provenance refusé

L’utilisateur fournit la sortie complète de la fenêtre 20261115T200950Z-29e0e47e : worker prêt, une mission admise par l’utilisateur, listeners Windows fermés, admission refermée, service privé restauré avec BPF/auth/ACL validés, gateway non redémarrée. Le rapport runtime local indique une exécution terminée et 0 CHF ; le verdict administrateur global reste passed=false avec PermissionError à main ligne 396. Cette ligne impose exclusivement synthetic://doselab/ à toutes les références de la projection canonique, contrairement au contrat mémoire existant qui inclut les expériences mission://. La présence exacte de ces références dans la projection de cette nouvelle mission reste à vérifier.

Diagnostic préparé : diagnose-completed-window.py --read-only, administrateur, lecture du snapshot et de la SQLite synthétique + GET canonique authentifié sur loopback. Aucun démarrage/service/mission ni écriture de données, aucun code ou texte de réponse exposé, aucun remplacement de verdict historique. Il rapporte uniquement état persistant, quotas, références, origine des reçus, citation et existence de l’événement expérience. 22 tests ciblés existants passent ; refus non-root du nouveau diagnostic vérifié. Le diagnostic administrateur n’est pas encore exécuté par l’agent.

### Vérification administrateur en lecture seule — mission persistante confirmée

Sortie fournie par l’utilisateur pour diagnose-completed-window.py --read-only : passed=true (diagnostic), fenêtre 20261115T200950Z-29e0e47e, mission 49f7bf6f-c6c8-4871-b23e-c4a51022d660, état persistant completed après restauration du service privé. Trois appels, 15 027 tokens, coût distant zéro, quotas respectés. Projection SQLite issue de reçus d’outils hôte authentifiés ; les trois sources synthetic://doselab/experience, synthetic://doselab/old et synthetic://doselab/correction sont citées dans le résultat. Événement expérience sauvegardé. Toutes opérations restent désactivées ; aucun service lancé par ce diagnostic.

La projection contient également mission://2b71ae54-314c-44e0-bdb3-93ee42d2cc52 : sa présence explique exactement le refus du contrôle de préfixe exclusif ligne 396. Le diagnostic confirme la présence de cette référence ; il n’atteste pas à lui seul la chaîne complète de provenance de cette expérience historique. Aucun élargissement automatique de l’allowlist ni modification de la validation n’a été effectué. Le rapport original reste passed=false, SHA-256 c5bde9447563170e9ba8bf1aa83bdf2528145114c5f6138c5aba2721cd24b7b4. La réussite fonctionnelle et la vérification postérieure sont consignées séparément ; aucun rejeu GPU n’est nécessaire pour ces constats. Une correction future du validateur devra contrôler explicitement les références d’expériences dans SQLite et conserver les refus pour les références non autorisées.
