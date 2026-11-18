# État réel au 16 novembre 2026

## Observations nouvelles en lecture seule

| Élément | Observation |
|---|---|
| Gateway utilisateur | `codex-gateway.service` active, PID **2538966** |
| Service privé | `jarvis-hermes-pilot-system.service` actif, PID **2750771**, UID `jarvis-pilot` |
| Superviseur | `jarvis-hermes-supervisor.service` failed, PID **0**, ancien `ExecMainStatus=200` (CHDIR) |
| Attestation | `jarvis-hermes-confinement.service` failed, PID 0, statut 1 |
| Autostart superviseur | unité `disabled` ; service privé `static` |
| Ports privés VM | **127.0.0.1:8796 et :8797** écoutent |
| Jarvis HTTPS | `/jarvis/` et JS panneau répondent 200 |
| Refus anonyme | session et liste missions sous `/api/jarvis/hermes-panel/` répondent **401** sur l'origine correcte ; Host/origine incorrects : 403 |
| Moteur vocal | GET `/api/jarvis/live/status` : **hybrid**, `speechOnly=true` ; aucun appel fournisseur |
| Windows | SSH diagnostics accessible ; Windows 11 Professionnel ; `C:\JarvisHermesLab` présent |
| Windows runtime | aucun listener détecté sur 8643/11434/8792/11436 ; aucun processus nommé exactement Hermes/Ollama détecté |
| GPU | RTX3080, 10 240 Mio, 1 045 Mio utilisés, utilisation 0 %, pilote 621.24 ; pas de mineur détecté par la sonde bornée |
| Proxmox | 9.2.25 ; VM100/103/201 actives, VM102 arrêtée ; CT205 actif |
| CT205 | **jarvis-qdrant.service** actif, processus qdrant PID11122 ; `jarvis-embeddings.service` actif PID112398, UID jarvis-memory ; ports 6333/6334/6335 en écoute |

Attention : `qdrant.service` est inactif parce que **ce n'est pas le nom du service utilisé**. Ne pas annoncer Qdrant arrêté sur cette seule interrogation. Les ports CT205 écoutent sur toutes interfaces du CT ; l'accès réseau effectif/pare-feu n'est pas réaudité ici.

Le HTTPS a été interrogé par loopback avec le Host/origine attendu. La vérification TLS a été désactivée uniquement dans cette sonde locale de contenu ; cela ne valide pas la confiance du certificat sur Mac/iPhone et ne doit pas être repris comme politique client.

## Tableau fonctionnel

| Fonctionnalité | Développée | Testée | Installée | Active | Blocages |
|---|---|---|---|---|---|
| Jarvis texte/voix hybrid | Oui | historique + statut actuel | Oui | Oui | sécurité globale des routes non finalisée |
| Big Boss / panneau intégré A | Oui | navigateur historique + HTTPS actuel | Oui | Oui | identité Hermes distincte de Jarvis |
| SSO B | Oui | HTTP/navigateur simulés | Non activé | Non | garde global, identité humaine, isolation Codex |
| Texte C | Oui | simulation + mission GPU réelle historique | Oui | saisie/queue validées par opérateur | citations historiques insuffisantes |
| Correction citations | Oui | tests synthétiques | release privée installée ; patches Windows provisionnés selon opération antérieure | nouveaux résultats pas encore démontrés | pas d'essai GPU supplémentaire demandé |
| Audit mémoire | Oui | synthétique, sans mutation | code privé livré | invocation réelle non vérifiée | périmètre personnel non autorisé |
| File à la demande | Oui | SQLite/HTTP/navigateur | Oui, résultat root fourni | acceptation validée ; flags actuels non relus | aucune lecture de config secrète |
| Superviseur accord 3 | Oui | 42 tests ciblés actuels + contrôles historiques | Partiel | **Non** | correctif lecteur config à appliquer/vérifier |
| Hermes Windows / RTX / MCP | Oui | vrais cycles synthétiques | Oui historiquement + dossier observé | arrêté au contrôle | lancement uniquement supervisé/autorisé |
| Compétence doselab_freshness | Oui | 3 puis16 fixtures, récupération après redémarrage processus | registre labo historique | candidate seulement | aucune publication |
| Qdrant expérimental | Oui | vrai service/embeddings, C1 strict historique | CT205 historique, services actifs | accès du superviseur non activé | transport/permissions séparés |
| Délégation vocale Hermes | Oui | P6-L2 réel en préproduction | code préparé | **Non en production** | activation distincte après fiabilisation |
| Broker Codex isolé global | Oui | fixtures/local | pas de bascule démontrée | Non démontré | fournisseur/identité/raccordements |
| Mémoire personnelle Hermes | mécanismes préparés | fixtures | pas d'import autorisé réalisé | Non | sélection, accords, confidentialité |

## Accord 3 : état exact, pas une promesse

Sauvegarde du commissionnement : `/var/backups/jarvis-hermes/executor-20261116T164844Z-0716bfb1` (chemin fourni par opérateur, contenu root non relu).

Le provisionnement a créé l'identité Linux dédiée et les unités/configurations, déposé le code, les règles réseau dédiées et trois correctifs MCP Windows. Le démarrage du superviseur a échoué ; le code de rollback a restauré le service privé en acceptation seule. Les permissions de dossiers code/config ont ensuite été corrigées selon la reprise ciblée, sans élargir les permissions des secrets. Le diagnostic opérateur suivant refuse encore la **configuration** depuis les deux répertoires de travail.

`fe589cc` corrige le lecteur : 213 empreintes représentent plus de 22 Ko ; le fichier principal dépassait16 Kio. Limite principale128 Kio, limite des autres JSON16 Kio, ownership/0600/symlink toujours contrôlés. Le correctif et son mécanisme de sauvegarde sont committés ; **aucune sortie root de reprise réussie n'a été fournie ensuite**. Le code installé du superviseur est inaccessible à l'UID de développement : son empreinte actuelle ne peut pas être certifiée ici.

L'ancien statut CHDIR conservé dans systemd ne prouve pas la cause actuelle du diagnostic Python ; il n'y a pas eu de nouveau démarrage réussi. Ne pas réinstaller tout le lot, ne pas assouplir BPF, ne pas effacer les checkpoints.

## Missions et preuves, sans nouveau contenu privé

| Preuve synthétique historique | État établi | Limite |
|---|---|---|
| Fenêtre `20261115T200950Z-29e0e47e` | mission persistée completed,3 appels/15 027tokens/0 CHF ; expérience et reçus canoniques | rapport global **passed=false**, contrôle de préfixe historique échoué |
| Fenêtre `20261115T214641Z-0f2a81f1` | mission completed,3 appels/19 838tokens/0 CHF ; provenance SQLite, persistance après restart privé | **passed=false**, `model_cites_source_ref=false` |
| C1 troisième essai | recherche vectorielle zéroFTS, historique vrai memory_id, source.ref explicite, persistance | succès strict distinct ; ne remplace pas B2/C1 précédents |
| Mission personnelle/projet réel | aucun import ni transmission autorisé pour ce dossier | aucune lecture de contenu |
| Mission en attente récente de l'utilisateur | déclarée dans l'échange précédent | son état exact actuel/expiration ne sont pas vérifiés |

Pas d'inventaire direct de SQLite privée : droits 700/600 et absence de sudo dans la session. Ne pas inventer les comptes/états courants depuis les rapports. Un futur inventaire doit être borné aux seules métadonnées synthétiques sous accès administratif autorisé, sans jetons/session IDs ni contenu personnel.
