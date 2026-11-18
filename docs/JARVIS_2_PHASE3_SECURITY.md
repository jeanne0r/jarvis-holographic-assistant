# Phase 3 — sécurité observée et limites

## Protections réellement exercées

La gateway, Gemini, les automatisations HA, CT205 et Qdrant restent inchangés.
Les seules modifications de production sont les allocations RAM temporaires
explicitement approuvées des VM103/201 ; elles sont restaurées exactement,
SHA256 et copies root-only vérifiés. La nouvelle VM102 est arrêtée, onboot=0.
Le gardien PVE indépendant a réellement interrompu l'essai à sa limite de temps.
Minimum hôte observé durant l'essai : 2,43 Gio, au-dessus de la marge 1 Gio.

Dans VM102, hermeslab n'a ni sudo ni clé SSH du contrôleur/Windows, aucune base
JARVIS montée, aucun secret de production. La clé SSH d'administration du
laboratoire reste sur le contrôleur. Le runtime a été lancé via unité transitoire,
User/Group hermeslab, MemoryMax2G, CPUQuota100%, TasksMax128, RuntimeMaxSec300,
NoNewPrivileges, ProtectSystem=strict, ProtectHome=read-only, PrivateTmp,
écriture autorisée dans son HOME Hermes d'exécution uniquement.

Le réseau de cette VM accepte loopback, connexions établies et SSH entrant du
contrôleur. Les quatre nouvelles connexions TCP depuis hermeslab vers HA8123,
Qdrant6333, Windows11434 et Internet443 échouent après application des règles.
Le premier contrôle a été lancé avant la fin du réglage des permissions et n'a
pas été accepté comme preuve ; aucun appel applicatif ni action physique effectué.
Le contrôle final après confirmation du pare-feu est conservé dans NETWORK_REAL.json.
La clé d'hôte SSH de cette VM a été vérifiée par un chemin indépendant via PVE/QGA.

Ollama Windows reste sur 127.0.0.1:11434, atteint par SSH privé. Aucun changement
Windows/minage/pare-feu, aucune exposition publique, aucun nouveau modèle téléchargé
pendant cette fenêtre. Les refus réseau et les identités sont distincts de l'IA.

## Contrôle des capacités

Les toolsets shell, fichiers, web, HA, cron et sous-agents sont absents du profil.
La façade générique tool_search/tool_describe/tool_call, activée par défaut dans
Hermes, a été détectée et refusée avant inférence. Elle est désormais explicitement
désactivée. Le relais contrôle les noms des outils effectivement envoyés : cinq
outils mémoire, six uniquement dans le mode candidat choisi par l'hôte.
Les outils ne peuvent ni changer de rôle/espace, ni promouvoir une connaissance,
ni publier une compétence, ni exécuter un script. Le token MCP est reader/proposer.

Mémoire native factuelle désactivée par deux flags distincts, provider none,
nudge0 ; background_review et fonctions auxiliaires IA désactivés. Les sessions
Hermes persistent pour les traces ; elles ne sont pas indexées comme faits.
Les résultats de missions sont des épisodes inferred, avec attribution, jamais
une mesure indépendante. Les faits synthétiques confirmés viennent du fixture hôte.

Le relais impose modèle/digest locaux, contexte64000 effectif, think=false, sortie
768, six appels, 180 s et ledger de quotas persistants, budget distant0. Le champ
reasoning_effort du SDK ne peut pas activer thinking côté Ollama. Les IDs d'appels
outils sont uniques entre tours. Le contenu externe ne change aucun de ces paramètres.

## Correctifs et limites

La sortie d'un échec natif peut contenir les mots API key sans divulguer une clé.
L'ancien filtre bloquait alors l'enregistrement terminal et laissait running.
Le bridge masque maintenant cette sortie et conserve failed ; test de persistance
ajouté. Il n'abaisse pas les règles d'ingestion ni les contrôles de publication.
Les anciennes livraisons interrompues sont paused/cancel_requested, sans retry
aveugle. Les correctifs postérieurs à l'arrêt sont locaux, pas encore rejoués sur VM.

Le Qwen4B échoue encore à deux cas de sécurité du corpus mémoire. Une mission
réussie ne rend pas le modèle fiable pour des actions physiques ou des permissions.
La publication d'une compétence n'est pas validée par ce premier runtime ; aucune
compétence n'a été créée ou activée. Le prototype de compétences reste déclaratif.

Les règles nftables ne sont pas présumées persistantes. Le contrôleur vérifie
maintenant boot_id et empreinte des règles avant tout prochain démarrage du
runtime ; ce correctif doit être exercé dans la prochaine fenêtre. Ne pas
raccorder la gateway aux missions tant que ses routes et ACL ne sont pas corrigées.
Les sécurités physiques demeurent indépendantes des modèles ; aucune action HA.

Nettoyage : gateway HTTP200 ; VM Tailscale joignable SSH, daemon non vérifié
indépendamment ; Ollama/tunnels arrêtés ; VRAM1061 Mio. Preuves : HELD_RAM_REAL,
NETWORK_REAL, CLEANUP_REAL et NATIVE_VALIDATION_REAL, préfixés JARVIS_2_PHASE3_.

Le registre historique exprime des catégories : memory.search couvre les lectures
(recherche, historique, projet, expériences, contradictions), memory.propose les
propositions non validées. Le prochain scénario compétence déclare explicitement
memory.propose en plus du mode hôte. Ces catégories restent expérimentales ;
une ACL fine par outil et mission est requise avant intégration gateway.

## Renforcement local après la fenêtre réelle

Le nouveau profil annonce six outils de lecture, dont skill_get ; le mode
candidat en ajoute un seul, skill_propose. Publication absente. Le relais vérifie
maintenant les noms exacts, les catégories de mission, la présence des outils dans
l'annonce et les arguments des sorties avec des schémas serveur indépendants.
Une réponse proposant shell, HA, publication ou champs d'élévation est refusée,
même lorsque le modèle considère l'action autorisée. Les tokens consommés par
une sortie refusée après inférence sont comptabilisés.

Les refus MCP produisent des catégories fixes et un journal stderr limité à
outil connu/outcome ; aucun argument ou nom d'outil arbitraire n'y est copié.
Le refus en aval reste volontairement générique pour éviter un oracle ACL.
Les essais natifs suivants utilisent des HOME exclusifs, jamais l'ancien HOME
interrompu susceptible d'auto-reprise. Le contexte conversationnel natif n'est
pas une deuxième source de vérité : skill_get relit le registre SQLite.

Ces ajouts ont des tests locaux ; ils ne sont pas encore déployés dans VM102.
Les restrictions réseau/OS doivent être revérifiées au prochain boot avant tout
runtime. Les risques de production recensés dans les audits ne sont pas levés
par ces tests de laboratoire ; la gateway reste hors raccordement.
