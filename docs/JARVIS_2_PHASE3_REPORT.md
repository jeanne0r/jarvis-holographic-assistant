# JARVIS 2 — phase 3 : premier cycle natif validé

## Résultat

Le 14 novembre 2026, **Hermes officiel + Qwen3.5:4b sur RTX 3080 + Memory Manager**
ont accompli une mission synthétique réelle. La phase 3 entière reste incomplète :
la mission de compétence n'a pas terminé et le raccordement Qdrant réel reste différé.

Le simulateur Jarvis admet la mission en environ 20 ms, sans attendre l'agent.
Le runtime natif appelle réellement `jarvis_memory_search`, puis deux fois
`jarvis_memory_history`. Il répond quatre cellules identiques de 1 kg, conserve
l'ancienne configuration [1,2,5,10] comme remplacée, et cite
`synthetic://doselab/correction` et `synthetic://doselab/old`.
Les références de révision existent dans les traces et le snapshot ; la réponse
finale cite les URI et horodatages, sans recopier les UUID de révision.

Le bridge reçoit completed. Le contrôleur enregistre un épisode **inferred**,
avec référence de mission, run natif, modèle et digest. La base SQLite est
réouverte et l'expérience est retrouvée. Le modèle ne valide aucun de ses faits.
Toutes les données sont synthétiques ; aucune conversation privée importée.

Preuve reproductible : `python3 scripts/validate_phase3_real.py --check`.
Les 14 contrôles du cycle mémoire natif passent. La validation analyse des
traces réelles conservées, elle ne lance aucune simulation ni nouvelle inférence.

## Matériel, installation et ressources

VM102 `jarvis-lab`, 2 vCPU, **4096 Mio**, disque qcow2 de **24 Gio sur hdd**,
IP privée 192.0.2.241, onboot=0. Image Ubuntu officielle vérifiée par SHA256,
instantané preinstall conservé. Clé SSH de laboratoire distincte, identité SSH
vérifiée indépendamment via QEMU Guest Agent.

Hermes commit `4959268e312a21a361f248e49030d5f5df3984d5`, Python **3.14.10**,
uv 0.13.8, 84 distributions installées avec lockfile et extras mcp/sms ; sms
fournit aiohttp, aucun outil SMS activé. Empreintes et versions dans
JARVIS_2_PHASE3_HERMES_INSTALL_REAL.json. Pas d'installation sur le contrôleur.

Après accord supplémentaire, shares=0 a tenu temporairement Codex à 2816 Mio et
Tailscale à 1024 Mio. Le gardien indépendant PVE a surveillé leurs marges et
l'hôte pendant une fenêtre limitée à **1800 secondes**, puis arrêté uniquement
le laboratoire et restauré les configurations, avec le délai d'arrêt gracieux.
Les SHA256 des deux configurations initiales et finales sont identiques.
Minimum hôte observé pendant cette fenêtre : environ **2,43 Gio disponibles**.
Aucun reboot d'un invité existant. L'état final est VM102 arrêtée, allocations
Codex/Tailscale rétablies à 4/2 Gio, shares initiaux rétablis, gardien inactif.

## Résultats GPU et limites découvertes

Le commit Hermes impose réellement **64 000 tokens minimum**, contrairement au
profil préparatoire 8192. Le relais et Ollama servent maintenant honnêtement
64000 ; cette capacité est observée dans /api/ps. Aucun assouplissement du
contrôle Hermes ni faux contexte annoncé. Le profil mémoire reste distinct à 4096.

Mission DoseLab : **3 inférences**, 11204 tokens d'entrée, 371 de sortie,
**11575 tokens** comptabilisés, coût distant 0 CHF. Pic VRAM totale échantillonné
**6862 Mio**, soit environ 3378 Mio de marge ; /api/ps annonce 5154285812 octets
résidents sur GPU au contexte 64000. Pic de puissance observé 302,72 W ; énergie
échantillonnée de la fenêtre du pilote 1,23 Wh. Ce n'est ni une mesure à la prise,
ni un débit statistiquement représentatif, ni une attribution énergétique isolée
à la mission. Le modèle est déchargé après chaque appel.

La mission compétence a effectué quatre autres inférences locales puis a été
interrompue à l'échéance du gardien. **Aucune compétence candidate créée**, aucune
publication. Les détails des appels refusés restent à diagnostiquer dans les
traces du laboratoire avant un autre essai. Au total : sept appels natifs mesurés,
29178 tokens, tous soldés dans le ledger. Les pilotes mémoire précédents
comptaient 43 inférences : total phase 3 observé 50, aucun appel distant payant.

Les comparatifs précédents restent valables pour le profil mémoire : Qwen4B
19/21 contre 15/21 pour le 9B installé, avec deux échecs de sécurité du 4B.
Ils ne prouvent pas la fiabilité générale des missions autonomes.

## Corrections et vérification

Le vrai runtime a révélé : permissions de lecture du compte sans privilèges,
minimum 64K, outils génériques de découverte activés par défaut, champ SDK
reasoning_effort, réutilisation trop rapide du port après arrêt, et SSE avec
le nom d'événement dans le JSON. Ces écarts sont corrigés dans les adaptateurs.
La sortie sensible d'un échec natif est désormais masquée sans laisser une
mission running à cause du filtre de journalisation.

Les rapports bruts ne sont pas réécrits : le premier pilote ne pouvait ouvrir
le lanceur ; son ancien indicateur runtime_tested était trop optimiste. Les
rapports suivants distinguent API atteinte et réussite. Le rapport _4 garde
passed=false pour la seconde mission non démarrée et pour l'ancien parseur SSE.
Sa réévaluation séparée, avec SHA256 des sources, prouve la première mission.
Les correctifs d'attente TIME_WAIT et de vérification réseau fraîche sont testés
localement, mais n'ont pas encore été réexercés sur la VM arrêtée.

`python3 scripts/evaluate_memory.py --phase3` : **12 commandes réussies**,
20 tests mémoire initiaux, **30 tests phase 2**, **30 tests phase 3**, plus
régressions Python/Node sélectionnées. Aucun appel modèle dans ce banc synthétique.
Les preuves GPU/runtime réelles sont dans les rapports distincts.

## Sécurité et état final

Compte hermeslab sans sudo, runtime MemoryMax=2G, CPUQuota=100%, TasksMax=128,
NoNewPrivileges et sources en lecture seule. Pare-feu de cette VM : sorties
nouvelles interdites sauf loopback, SSH d'administration depuis le contrôleur.
Quatre refus TCP depuis hermeslab constatés vers HA, Qdrant, Windows et Internet.
Les seules capacités exposées au modèle sont les cinq outils mémoire contrôlés,
plus skill_propose uniquement pour la seconde mission. Pas de shell, Home
Assistant, web, sous-agents ni publication. Mémoire native factuelle désactivée ;
les sessions Hermes sont des traces d'exécution, pas une deuxième vérité.

Nettoyage vérifié : gateway HTTP200, VM Tailscale joignable en SSH, Ollama et les
tunnels arrêtés, VRAM revenue à 1061 Mio. Le daemon tailscaled n'est pas contrôlé
indépendamment. Aucune modification de gateway, Gemini, HA, CT205 ou Qdrant.

## Suite concrète

1. Préparer la réutilisation sûre de VM102 arrêtée : le mode --reuse-lab du gardien vérifie
   maintenant le tag connu, VM arrêtée, 4 Gio, onboot=0 et disque HDD. Ce mode
   est testé localement, pas encore déployé ni exécuté sur PVE.
2. Lors d'une nouvelle fenêtre autorisée, inspecter les traces de la mission
   compétence interrompue, puis terminer création candidate et contrôles de refus
   de publication. Ne pas relancer aveuglément les anciens run_id interrompus.
3. Éprouver les correctifs de redémarrage et la reprise native après interruption.
4. Demander séparément D avant tout raccordement embeddings/Qdrant expérimental.
   Ne jamais écrire dans jarvis_memory_v1. L'intégration gateway reste différée.

Les autorisations précédentes ne prolongent pas la fenêtre de 30 minutes écoulée.
Aucun nouveau démarrage n'est effectué pour compléter ces points dans ce rapport.

Les scénarios de compétence préparés après cette fenêtre précisent maintenant
memory_id (stable) plutôt que id (révision) comme source, déclarent la catégorie
memory.propose et évaluent le candidat sans autoriser sa publication. Ces
clarifications restent à vérifier réellement ; elles ne sont pas une conclusion
sur la cause des refus précédents. Nouvelle fenêtre demandée, non démarrée.

## Suivi du 14 novembre — préparation de la compétence interrompue

Aucun nouveau démarrage VM, changement RAM, appel GPU ou accès CT205.
VM102 arrêtée et paramètres103/201 initiaux revérifiés en lecture seule.
Les preuves natives antérieures demeurent immuables et la première mission validée
n'a pas été rejouée. Aucun candidat réellement appris n'est encore démontré.

Développé hors production : schéma strict de compétence, évaluation candidate
persistée, outil de lecture canonique skill_get avec ACL/provenance, diagnostics
MCP sans arguments ni secrets, contrôle des outils annoncés et retournés selon
les grants hôte, rejet des valeurs VRAM non finies. Nouveau scénario --skill-only :
création/évaluation, arrêt du runtime, démarrage dans un HOME neuf et recherche
canonique de la candidate. Les HOME antérieurs restent conservés et non repris.
Aucune publication automatique, aucun nouveau schéma ou migration SQLite.

Les deux échecs Qwen4B sont détaillés dans
[JARVIS_2_PHASE3_MODEL_RELIABILITY.md](JARVIS_2_PHASE3_MODEL_RELIABILITY.md).
Les arguments/résultats des refus de la mission interrompue ne figurent pas dans
les traces copiées : leur cause exacte reste à établir depuis les sessions VM102
après accord. La confusion memory_id/révision est une hypothèse, pas un constat.

Validation locale : banc complet12 commandes, dont20 tests Memory Manager initiaux,
30 tests phase2 et40 tests phase3 ; données synthétiques, transports simulés,
aucune inférence réelle. Évaluation persistée et lecture après réouverture SQLite
réussies localement ; le nouveau cycle natif et son confinement restent à retester
réellement. La réanalyse hors ligne des preuves natives existantes conserve14/14.
Voir JARVIS_2_PHASE3_TEST_RESULTS.json pour sorties et horodatage.

Prochaine étape soumise à accord A/B explicite :
[JARVIS_2_PHASE3_SKILL_RETRY_PLAN.md](JARVIS_2_PHASE3_SKILL_RETRY_PLAN.md).
Raccordement Qdrant préparé séparément, pas activé :
[JARVIS_2_PHASE3_QDRANT_PLAN.md](JARVIS_2_PHASE3_QDRANT_PLAN.md).
La phase3 reste incomplète jusqu'à preuve réelle de la compétence et de sa
relecture. Aucun branchement à Gemini/gateway ni action physique.

## Essai autorisé — admission refusée le 14 novembre 2026

Après l'accord explicite « Oui go », la fenêtre A/B a été engagée à 2026-11-14T15:31:48.427249+00:00
et refermée avant son échéance : restauration confirmée à 2026-11-14T15:32:56.972207+00:00.
Les configurations103/201 ont été sauvegardées en root-only avec SHA256 vérifié.
Le mode de réutilisation du gardien a été réellement exécuté pour VM102 existante,
sans création de VM ni changement de son allocation4Gio.

Les cibles autorisées103=2816Mio et201=1024Mio, shares0, ont été appliquées.
Les marges invitées sont restées au-dessus de1Gio et512Mio dans les échantillons.
Cependant le maximum hôte observé pendant cet ajustement n'a été que
**4.284Gio**, contre **5Gio requis avant boot102**.
Huit échantillons gardien pendant l'ajustement ; aucun ready.json créé.
Le changement de cible balloon ne garantit pas un gain équivalent de mémoire
physique disponible. La cause précise du faible gain n'a pas été isolée ; ne pas
l'attribuer arbitrairement à un service ou confondre plafond alloué et RAM résidente.

L'appel SSH du contrôleur a atteint son timeout60s pendant apply. La commande
d'admission distante et le gardien sont indépendants de cette connexion ; la
restauration distante a ensuite été vérifiée. Aucun processus apply restant,
gardien inactif, configurations byte-à-byte identiques aux sauvegardes, allocations
103=4096Mio et201=2048Mio restaurées, VM102 toujours arrêtée.
Le timeout du contrôleur n'est pas présenté comme une preuve de marge ni comme
un résultat Hermes ; une future commande de contrôle devra laisser assez de temps
aux observations et à la restauration, sans prolonger la fenêtre du gardien.

Gateway : HTTP200 après restauration. VM Tailscale : SSH joignable, ce qui ne
prouve pas l'état applicatif du démon Tailscale. Windows : RTX libre sans mineur
au précontrôle, Ollama absent après l'essai ; aucune tentative de démarrage.

**Aucun appel modèle, démarrage Hermes ou VM102, nouvelle compétence, installation,
téléchargement, intervention CT205 ou action physique. Coût distant0CHF.**
La première preuve mémoire native reste valide ; le nouveau cycle compétence
n'a pas été exécuté. Les journaux natifs stockés dans la VM arrêtée n'ont donc
pas pu être lus. Les deux missions neuves restent à lancer après admission RAM.

Preuve : [JARVIS_2_PHASE3_SKILL_ADMISSION_REAL.json](JARVIS_2_PHASE3_SKILL_ADMISSION_REAL.json),
SHA256 `c0c9b5d1ede460aa6324cb6020401938cf341eda1c97f554ddca4a07b7036299`.
La fenêtre est close, ses marqueurs ne doivent pas être réutilisés.
Suite : obtenir réellement>=5Gio disponibles avec les mêmes garanties et une
nouvelle fenêtre, ou choisir un hôte de laboratoire offrant la RAM nécessaire.
Aucune réduction supplémentaire d'invité ni baisse de seuil n'est autorisée.

## Décision du 14 novembre2026 — phase4 Windows

L'hébergement Hermes passe au PC GAMER Windows natif ; la stratégie de récupération
RAM Proxmox et de réservation4Gio est abandonnée provisoirement. VM102 reste
arrêtée sur disque ; allocations103/201 et absence de gardien vérifiées en lecture
seule. Les anciennes preuves et composants sont conservés. Aucun nouveau
démarrage/installation autorisé par cette note. Plan courant :
[JARVIS_2_PHASE4_WINDOWS_PLAN.md](JARVIS_2_PHASE4_WINDOWS_PLAN.md).
