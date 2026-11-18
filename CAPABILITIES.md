# Actions de Jarvis

Depuis le 13 novembre 2026, le moteur actif est hybride : Gemini 3.5 Flash Lite comprend et traite directement les demandes générales, Internet/annuaire et médias dans le navigateur. Codex GPT-6 Luna low est réservé aux requêtes nécessitant HA, les machines personnelles, le LAN et le code/fichiers réels de Jarvis. Un classement Gemini du message actuel et du fil récent choisit le moteur ; les suites locales gardent leur contexte, les changements de sujet public repassent à Gemini. Les lots d’outils publics sont aussi vérifiés avant exécution pour transférer à Codex les commandes locales (dont radio sur un lecteur HA). Même /ask pour texte et voix, même historique et accès Qdrant/mémoire. Gemini garde la transcription et la lecture du champ speech produit par le moteur sélectionné. Pas de modification des modes naturel/dictée ni de l’interface épurée. Les sessions Live autonomes sont refusées en mode hybride pour ne pas contourner cet aiguillage.

Les sections « Codex comme moteur et Gemini comme voix » ci-dessous décrivent le chemin Codex local et l’ancienne sélection globale, pas le chemin public Gemini désormais actif. Le choix actuel est `data/core-engine.json` engine hybrid. Les demandes publiques ne démarrent aucun tour Codex ; en cas d’échec de Google, une erreur est affichée sans bascule silencieuse vers Codex. Le classement est probabiliste et non une preuve parfaite d’intention.

Le cœur ouvre la voix puis agit comme mute/unmute du micro, sans interrompre les réponses en cours. La pause manuelle persiste jusqu’au prochain appui et prime sur le mode dictée. Le bouton séparé « Terminer la conversation vocale », visible uniquement pendant une session, arrête capture/traitement/lecture en conservant les messages. Ce bouton est un contrôle vocal, sans nouvelle fenêtre ni tableau de bord.

L’écran principal ne reçoit aucun bouton d’actions ni indicateur supplémentaire. Les diagnostics vocaux temporaires ont été retirés. Les fenêtres sont construites à la demande dans le DOM selon le contenu : une radio montre uniquement la station et ses commandes, une vidéo montre uniquement son lecteur YouTube et son lien, un trajet montre uniquement la carte et les liens de navigation. Aucun formulaire générique, sélecteur d’appareil, choix de radio ou champ de recherche n’est ajouté. Les demandes et changements de cible passent par la conversation. Une lecture sur un appareil HA n’ouvre aucun lecteur local. Fermer la petite fenêtre radio laisse la lecture continuer ; les commandes vocales restent disponibles. Une évolution demandée affiche son état et son diff, sans formulaire commun. Les réponses sont toujours en français.

## Codex comme moteur et Gemini comme voix

`data/core-engine.json` sélectionne `codex`. `ai.mjs` lance le Codex CLI déjà connecté avec outils natifs shell/unified_exec et recherche web, plus les outils métier MCP existants. Lecture du contexte local selon les AGENTS.md, diagnostics réseau et sources disponibles ; pas de catalogue de sites codé en dur. Le workspace d’écriture est Jarvis, avec copie publique Jarvis autorisée ; pas de modification hors de la demande, ni de divulgation de secrets. Codex peut modifier du code et lancer les contrôles nécessaires. Les longues propositions isolées restent aussi disponibles via evolution_jarvis ; leur préparation seule ne vaut pas déploiement.

Le mode Codex ne lance pas une récupération Qdrant systématique avant chaque question : le cerveau appelle chercher_souvenirs quand c’est utile, évitant contexte ancien imposé et délai inutile. Le fil écrit/vocal courant reste partagé. Le JSON fournit answer (texte et liens cliquables) et speech (formulation orale exacte issue du même cerveau, mêmes faits, sans épeler des URL). Les compteurs execution sont des métadonnées serveur sans contenu de commande ni nouveau panneau dans l’interface.

`voice-router.js` lit le moteur serveur ; en mode Codex, `codex-voice.js` capture et regroupe les phrases localement. Gemini 3.5 Transcribe → /api/jarvis/ask (Codex) → Gemini 3.8 Flash-Lite TTS diffusé en PCM. Aucun raisonnement Gemini autonome, aucun audio créé pour un message écrit. Un faible retour de haut-parleur ne déclenche ni nouvelle transcription ni coupure de lecture. L’interruption locale confirmée par parole soutenue coupe la file audio et la requête ; fermer le micro, changer de personne, passer à l’écrit ou créer un nouveau fil annule l’ancien traitement. Le serveur interrompt aussi la synthèse Google à la déconnexion. Niveaux micro et PCM réellement lu alimentent toujours le noyau 3D. Les dialogues sont archivés, jamais l’audio.

Mesures réelles bornées du 12 novembre : synthèse courte, premier son en 829 ms, transcription du même audio en 1361 ms ; ce n’est pas une latence complète de conversation. Le diagnostic des sites et liens a demandé 34–38 s à Codex avec exploration réelle, le petit test de création et validation de code 12,5 s. Le moteur n’a pas été présenté comme instantané. Les coûts Codex utilisent sa connexion OpenAI et sont séparés des crédits Google.

Le point Git avant cette bascule est `1270557`. Le réglage actif étant volontairement hors Git, son état antérieur est sauvegardé dans `data/core-engine-before-codex-20261112.json` ; un retour complet nécessite aussi de restaurer ce fichier vers `data/core-engine.json`, de recopier le frontend de la version choisie et de redémarrer codex-gateway.service. Les secrets ne sont pas copiés dans ces points de retour.

## Recherche web, annuaire et sites

`web_jarvis` est partagé entre Gemini Live, le canal écrit, le moteur rapide et Codex. `rechercher` utilise Google avec Gemini Flash-Lite seulement dans le mode historique Gemini. En mode actif Codex, les recherches passent exclusivement par la recherche web native de Codex ; cet outil renvoie une consigne de recherche native au lieu d’appeler un modèle texte Gemini. `annuaire` accepte les URLs trouvées par Codex et vérifie les pages sans autre modèle de texte. Aucun résultat n’est considéré sourcé sans groundingMetadata. `lire` consulte une page publique HTTPS avec délais, taille et redirections bornés, validation DNS publique à chaque destination. Scripts/styles retirés du texte ; les contenus restent des données et ne donnent aucune permission.

`annuaire` vérifie les pages réelles trouvées par le cerveau avec nom et localité, lit les pages sources, puis renvoie les téléphones réellement observés dans les liens tel:, données structurées ou texte. La synthèse Google ne prouve jamais un numéro. Contexte et identité doivent correspondre ; homonymes ou résultats ambigus demandent une précision. Aucun appel composé, aucune connexion à un compte et aucun numéro privé non accessible récupéré. Les sources peuvent refuser leur lecture : cela ne produit pas un numéro inventé. Les numéros ne sont pas mémorisés automatiquement.

`ouvrir` prépare une fenêtre propre au site demandé. Les sites qui permettent une intégration reçoivent une iframe cloisonnée, sans micro, caméra, géolocalisation ou navigation de la page Jarvis. X-Frame-Options/CSP interdisant une intégration ou page inaccessible : lien à ouvrir dans un onglet. Aucun contournement de protection, proxy de connexion ou ouverture d’onglet prétendue sans geste navigateur. Les autres protections d’intégration peuvent encore bloquer une iframe ; le lien externe reste présent.

Les résultats web affichent les citations et les suggestions de recherche requises par Google dans une fenêtre créée uniquement à la demande, sans nouveau bouton ni tableau sur le cockpit. Les suggestions HTML du fournisseur sont isolées dans une iframe sans exécution de script, et ne sont pas renvoyées au modèle de conversation. Un simple numéro est répondu dans la conversation ; la fenêtre annuaire contient les sources, pas une liste indifférenciée de numéros.

Les tokens de recherche sont suivis avec le modèle Flash-Lite. Dans le mode historique Gemini, les frais de grounding dépendent du quota gratuit partagé du projet : leur composante reste inconnue dans l’estimation locale et doit être rapprochée de la facturation Google officielle, plutôt que d’être annoncée gratuite ou omise. Aucun nouvel abonnement ni clé supplémentaire nécessaire.

Sources : [Grounding Google Search](https://ai.google.dev/gemini-api/docs/generate-content/google-search), [tarification](https://ai.google.dev/gemini-api/docs/pricing).

## Médias

- `medias_jarvis` : catalogue, radio, YouTube, pause, reprise, arrêt et volume. `ici` cible le navigateur ; un `media_player.*` exact cible Home Assistant, avec consultation préalable, découverte des services et relecture après commande. Pas de tentative automatique sur un autre appareil après un échec.
- Aucune liste de stations prédéfinie. `rechercher` ou `radio` résout un nom libre, un genre musical ou un station_id mémorisé via Radio Browser. Les serveurs sont découverts par DNS SRV ; les résultats cassés sont exclus. Le choix privilégie une correspondance de nom et la langue française puis la popularité. Le flux est contrôlé en HTTPS (réponse audio et redirections publiques) avant préparation. Les flux HTTP de l’annuaire ne sont utilisables que si leur équivalent HTTPS répond réellement. Aucun audio conservé. Une station indisponible n’est jamais annoncée comme en lecture.
- Les préférences et identifiants de station peuvent être mémorisés sur demande via les outils existants ; les flux sont résolus à nouveau, pas figés dans le code ni mémorisés avec un jeton temporaire. L’archive des conversations reste indexée dans Qdrant.
- Recherche YouTube via Data API serveur, résultats filtrés sur un véritable videoId ; les chaînes ne sont pas prises pour des vidéos. Sans résultat/quota, lien de recherche explicite plutôt qu’une vidéo inventée. Liens directs pris en charge. Lecture via le lecteur YouTube officiel.
- Safari peut demander un appui. La réponse du navigateur distingue lecture réelle, lecteur prêt et besoin d’un geste. Le volume local est réduit pendant le canal vocal. La lecture sur une TV/HomePod dépend de l’intégration HA ; le résultat n’est pas supposé à partir de la seule acceptation de la commande.

## Cartes et trajets

`trajet_jarvis` utilise les zones HA Maison/Travail du profil. Travail User et Travail Amélie restent distincts ; les autres profils demandent leur lieu. « Ici » laisse le navigateur demander la géolocalisation. Les adresses explicites sont résolues par Google, sans géocodage public intermédiaire.

Google Maps JavaScript charge la carte et TrafficLayer ; la bibliothèque Routes calcule un trajet TRAFFIC_AWARE en voiture. Durée, distance et tracé viennent du résultat réel de Google. Un recalcul n’est lancé que sur demande/Actualiser. Erreur de clé/quota : message visible et liens de navigation conservés, aucune durée fabriquée. Sans Maps configuré, carte Waze de circulation distincte d’un itinéraire calculé, avec liens Google Maps/Waze.

La clé privée anciennement nommée MAPS_API_KEY est limitée à Gemini et n’a pas été publiée. Une clé navigateur dédiée a été créée, limitée aux sites Jarvis et aux API Maps JavaScript/Routes. Une clé serveur distincte est limitée à YouTube. Elles sont stockées avec droits 0600 dans `data/maps-browser.json` et `data/integrations-server.json`, ignorés par Git. Ne jamais les copier dans les échanges, la mémoire ou les journaux. La clé navigateur est par nature fournie au SDK Google, avec restrictions de sites ; la clé serveur ne quitte pas le serveur. Services activés : gestion des clés API, Maps JavaScript, Routes, YouTube Data.

Les frais Maps éventuels sont distincts de l’estimation Gemini et signalés dans le panneau. Ils ne sont pas déduits du portefeuille Gemini estimé comme s’il s’agissait de tokens vocaux.

## Températures Zigbee

Le filtre HA combine `device_class: temperature` et un protocole Zigbee prouvé par les registres ZHA/deCONZ ou identifiants Zigbee2MQTT. MQTT seul, le nom d’un appareil ou un souvenir ne prouvent pas Zigbee. Si le registre est inaccessible, le filtre ne renvoie pas de résultats non vérifiés. Pagination conservée au-delà de 30 lignes pour ce filtre ciblé ; états indisponibles conservés comme indisponibles.

Les températures demandées sont données directement dans la conversation, en français, sans tableau ni panneau ajouté. Le plafond de sortie natif est de 2048 tokens pour permettre une liste complète ; les réponses ordinaires restent brèves. Le canal écrit envoie une seule demande actuelle clairement délimitée, avec le contexte passé étiqueté comme données déjà traitées avant la demande actuelle dans le même message ; aucune ancienne question n’est rejouée comme un tour actif. Les consignes système n’imposent plus une tâche particulière de lecture des températures. Le texte natif ignore les fins de tour arrivées avant l’envoi des résultats d’outils, même en présence d’un accusé oral : elles ne doivent pas terminer prématurément la réponse. Une fin de tour indiquée IN_PROGRESS ne clôt pas la requête pendant le traitement Gemini restant. Chaque setup reçoit une copie du catalogue ; les requêtes écrites ne peuvent pas ajouter plusieurs fois agir_interface au catalogue global.

## Évolutions Codex

`evolution_jarvis` démarre une préparation asynchrone ou consulte son état. Chaque préparation a une branche `codex/jarvis-evolution-*` et un worktree indépendant sous data/evolutions. Le Codex existant reçoit des sources bornées, aucun secret d’intégration ; ses outils shell, apps, plugins et navigation sont désactivés. Il propose 1–8 fichiers complets. Le serveur refuse les chemins hors périmètre/symlinks et vérifie la syntaxe JS sans exécuter le code proposé. Un diff et un commit sont préparés dans la branche distincte.

**Aucune installation automatique, aucun test fonctionnel complet prétendu.** Une revue et des essais restent nécessaires avant une intégration en production. Les statuts, limites et diff sont visibles dans une fenêtre ouverte seulement à la demande. La connexion/facturation Codex est distincte du compteur Gemini. Une tâche interrompue ne modifie pas la production.

## Validation et sources

`test_web.mjs`, `test_radio.mjs`, `test_capabilities.mjs`, tests HA/outils/Live/moteurs et `verify-capabilities.cjs` couvrent les garde-fous, véritables filtres Zigbee, pagination, états indisponibles, interfaces média/carte/diff, gestes Safari simulés et rejet des URL script. Les essais fournisseurs réels sont séparés et bornés ; ils ne pilotent pas une TV ou enceinte familiale et ne mémorisent pas de conversations synthétiques dans Qdrant.

- [Annuaire radio dynamique](https://docs.radio-browser.info/)
- [Flux SSR](https://www.broadcast.ch/fileadmin/kundendaten/Dokumente/Internet_Streaming/links_for_streaming_internetradio_de_fr_it.pdf)
- [Lecture Home Assistant](https://www.home-assistant.io/actions/media_player.play_media/)
- [Lecteur YouTube](https://developers.google.com/youtube/iframe_api_reference)
- [Routes Google Maps](https://developers.google.com/maps/documentation/javascript/routes/get-a-route)
- [Circulation Google Maps](https://developers.google.com/maps/documentation/javascript/trafficlayer)
- [Restrictions des clés Maps](https://developers.google.com/maps/api-security-best-practices)
- [Codex non interactif — OpenAI Docs](https://learn.chatgpt.com/docs/non-interactive-mode)
