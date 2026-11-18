# Phase 4 — contrôles Windows et limites d'activation

Le pilote natif utilise uniquement des fixtures synthétiques, sans connexion à la gateway de production. Preuves : WINDOWS_VALIDATION_REAL.json et NATIVE_WINDOWS_RETEST_REAL.json. Les validations Windows ci-dessous sont réelles ; les scénarios d'arrêt brutal de mission et de reprise inconnue restent simulés.

| Contrôle | Observation réelle |
|---|---|
| Identité | hermeslab standard, sans SID Administrateurs dans ses groupes ; SSH par nouvelle clé, clé privée conservée sur Proxmox. |
| NTFS | Jetons protégés, propriétaire Administrateurs, lecture seulement hermeslab/SYSTEM/Administrateurs. Lecture du leurre privé et écriture code/runtime/jeton refusées ; traces runs modifiables. Cela ne prouve pas une interdiction de lecture de tout fichier personnel du PC. |
| Réseau | Sous hermeslab : loopback permis ; LAN SSH, HA8123, Qdrant6333, Internet443 refusés. Le témoin administrateur garde LAN/Internet. Le loopback IPv6 ::1 reste accessible aux deux identités. La liaison IPv6 du NIC LAN est désactivée, sans adresse IPv6 ; les sondes LAN IPv6 sont donc non concluantes. La règle IPv6 est configurée, mais devra être éprouvée si cette liaison est un jour réactivée. Deux règles sortantes ciblent uniquement le nouveau SID, aucun changement global ni entrée publique. |
| Outils annoncés | Six outils MCP de lecture ; un outil de proposition de compétence supplémentaire seulement pour la mission autorisée. Contrôle indépendant des noms/arguments dans le relais. Pas de shell, web, fichier arbitraire, HA, cron ou sous-agent. |
| Autorités | Le jeton MCP ne peut ni valider arbitrairement les faits, ni publier une compétence. Proposition réellement créée ; publication refusée avec le principal agent ; zéro version active. |
| Runtime | Job Object : affectation avant reprise, plafond 2 Gio, 20 % CPU, 32 processus, 300 s maximum et arrêt du groupe possédé. Descendant de test réellement arrêté. |
| Modèle | Qwen local/digest épinglé, contexte réel 64 000, sortie bornée 768, thinking désactivé ; six appels/180 s/98 304 tokens au plus par mission, aucun crédit distant autorisé. |
| Fenêtre globale | Réservation contrôleur verrouillée, 24 appels/4 missions/30 min, échecs inclus sans remboursement aveugle. Fenêtre fermée en fin d'essai. Fermeture/épuisement bloque le prochain lancement Windows avant création de processus. |
| Arrêt | Trois runtimes puis Ollama arrêtés, quatre ports Windows et tunnels libérés. Le snapshot canonique après arrêt passe integrity_check=ok et conserve la candidate. |

Les quatre transferts SSH fixent les deux extrémités à loopback, avec clé d'hôte déjà vérifiée, identité séparée, sans agent forwarding. Ollama sert 127.0.0.1:11434. Hermes sert 127.0.0.1:8643. Le MCP atteint la mémoire Proxmox par tunnel ; SQLite canonique et registre des missions/compétences ne quittent pas le contrôleur. Les identités mémoire/bridge/modèle/runtime sont distinctes.

Ollama utilise l'installation et les poids existants, sous l'identité opérateur historique, dans son propre Job borné. Ce processus de confiance a des accès plus larges que Hermes. Le compte standard ne doit pas être présenté comme une sandbox parfaite ; un runtime compromis pourrait joindre d'autres services loopback, dont Ollama directement. Ce risque interdit une autonomie générale ou l'exécution de code expérimental dans ce montage. Seuls les outils MCP fermés du pilote sont validés. Aucune règle physique HA ne dépend du jugement de Qwen.

Le compteur PeakJobMemory a dépassé 2 Gio pendant la tentative synthétique d'allocation refusée de 3 Gio, tandis que MemoryError est effectivement retourné et la limite relue vaut 2 Gio. Ne pas interpréter ce compteur comme une preuve RSS. La sémantique de refus de commit est documentée par [Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information).

Le modèle conserve les deux échecs de sécurité observés en phase 3. Le succès de cette procédure limitée ne valide pas ses décisions de permissions ni une compétence physique. La protection repose sur les contrôles hôtes, les ACL et les outils autorisés, indépendants de ses réponses. Les essais n'ont activé aucun minage, automatisme, pompe, chauffage ou commande électrique.

Avant production : authentifier les routes gateway concernées, démontrer les ACL par espace, isoler l'exécuteur Codex distinct, revoir les accès loopback et les approbations humaines, puis valider annulation/reprise avec le vrai runtime. Qdrant exige une autorisation distincte, sauvegarde vérifiée et collection jarvis_knowledge_experimental_v1 ; jarvis_memory_v1 reste intouchée. Aucun de ces travaux de production n'est implicitement autorisé par le pilote.
