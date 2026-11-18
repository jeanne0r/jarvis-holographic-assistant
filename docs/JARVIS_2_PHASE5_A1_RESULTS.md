# Phase 5 — A1 : sauvegarde et restauration réelles validées

14 novembre 2026, accord explicite reçu dans la conversation pour **A1 uniquement**.
A2 (embeddings/collection expérimentale), B (Windows) et l'accès personnel par un
modèle ne sont pas autorisés par cet accord et n'ont pas été exécutés.

## Résultat

| Vérification | Observation réelle |
|---|---|
| Binaire existant | Qdrant 1.20.0, `/usr/local/bin/qdrant` |
| Snapshot unique | 168 229 376 octets, environ 160,44 Mio |
| SHA256 archive/API/copie | `92f138189be20e3256d150b744f15cb12ee46240aae4b29e1f3935c09b1d0a9f` |
| Comptage exact restauré | **41 428 points** |
| Vecteurs | Cosine, 384 dimensions, schéma identique |
| Index de payload | doc_id, space, version, identiques à la source |
| Requête sur la copie | vecteur synthétique, 3 résultats, scores finis, sans payload ni vecteur retourné |
| Authentification | accès non authentifié refusé |
| Production | PID Qdrant 11122 conservé, vert, 41 428 points avant/après |
| Embeddings | service actif, source SHA256 initial inchangé |
| Arrêt | vérificateur arrêté, aucune unité A1 active |

La différence avec les 41 407 points de l'audit initial était déjà présente **avant**
la création du snapshot A1. Le lanceur n'a aucune écriture de points autorisée sur
l'instance principale.

Le vecteur de requête est artificiel : cela démontre que la copie restaurée répond
à l'API vectorielle, pas une pertinence sémantique, une consolidation ou un cycle
Hermes. Aucun contenu personnel n'a été transmis à un modèle ou publié.

## Conservation privée

Dans CT205 :

- Archive et manifeste : `/var/lib/jarvis-memory/phase5-backup/20261114T181811Z-3eb75693/`.
- Copie restaurée réussie : `/var/lib/jarvis-memory/phase5-restore/20261114T182330Z-0b504a9b/`.
- Le snapshot original Qdrant est conservé ; ses permissions ont été restreintes
  uniquement sur ce nouveau fichier. Aucun ancien snapshot supprimé ou modifié.
- Répertoire privé 0700, archive/manifeste 0600. SHA256 revérifié après les essais.

Les copies restaurées et diagnostics des deux échecs sont conservés pour audit.
Aucun nettoyage destructif. Environ 4,69 Gio libres dans CT après l'essai réussi.
**La sauvegarde est locale à CT205 : elle ne protège pas encore contre la perte
complète du CT ou de son stockage. Une copie hors CT/hôte reste à préparer.**

## Ressources et isolation effectivement contrôlées

Lecture des contrôleurs noyau, pas uniquement des paramètres de systemd :

```
memory.max      268435456
memory.swap.max 0
cpu.max         50000 100000
RuntimeMaxSec   600
```

L'essai réussi a duré environ **2,43 secondes** hors création initiale du snapshot.
Temps CPU du cgroup relevé avant arrêt : environ **0,344 seconde**.

Le pic `memory.peak` relevé atteint **256 Mio**, donc le plafond a réellement été
sollicité. `memory.events` : **max=72**, **oom=0**, **oom_kill=0** au dernier relevé.
`max` indique des rencontres du plafond, pas 72 OOM. Le RSS du processus au dernier
échantillon était **175 792 128 octets (167,65 Mio)**, contre un cgroup qui compte
aussi le cache de fichiers. Pas de marge sous le plafond revendiquée ; aucune
augmentation des limites effectuée.

Minimum de mémoire CT disponible dans les échantillons du succès : environ
**847,92 Mio**, au-dessus du seuil d'arrêt de 256 Mio. Le contrôle préalable de
l'hôte Proxmox relevait environ 3,74 Gio disponibles. Aucune allocation VM modifiée.

L'instance réussie utilisait un **espace réseau privé effectif**, loopback 16333,
gRPC désactivé, télémétrie désactivée, une clé distincte et un environnement vidé
avec pins explicites. Les contrôles HTTP entraient dans cet espace via `nsenter` ;
aucun service de test n'était exposé sur le LAN. `ProtectSystem=strict`, seul le
répertoire de restauration était inscriptible ; stockage principal et fichier de
secrets historique masqués au vérificateur. Aucun service permanent installé.

## Deux défauts du lanceur corrigés

1. Première tentative `20261114T181811Z-3eb75693` : le fichier JSON n'a pas été
   chargé par le binaire ; repli sur la configuration par défaut, puis arrêt sur
   port REST occupé. Les logs signalaient aussi la télémétrie par défaut activée ;
   son émission éventuelle n'a pas été mesurée. Aucun message d'écouteur démarré
   observé. Correction : YAML, pins explicites et espace réseau privé vérifié
   avant toute nouvelle restauration.
2. Deuxième tentative `20261114T182147Z-245508ef` : avec le `temp_path` explicite,
   le renommage final vers `storage/collections/...` échouait, faute de parent de
   destination. Correction : création privée explicite du parent et utilisation
   du chemin temporaire adjacent par défaut.
3. Troisième tentative `20261114T182330Z-0b504a9b` : tous les contrôles réussis,
   arrêt confirmé. Même snapshot réutilisé, aucun `force_snapshot`, aucun
   écrasement d'une destination, aucune hausse de ressources.

Les échecs étaient des sorties avec erreur, pas des OOM. Leurs unités restent
référencées comme failed dans systemd, sans processus ; aucune unité A1 active.

Le code officiel décrit la restauration CLI et l'exigence d'une cible absente :
[Qdrant snapshots](https://qdrant.tech/documentation/snapshots/).
Le code de récupération explique le renommage du chemin temporaire vers la
collection : [source Qdrant v1.20.0](https://github.com/qdrant/qdrant/blob/v1.20.0/src/snapshots.rs).

## Code, tests et preuves

- `ops/phase5-qdrant-a1.py` : lanceur A1 explicite, allowlist d'écriture de snapshot
  seulement sur la production, vérification SHA256/taille, réutilisation possible
  d'un manifeste privé, isolation et arrêt dans le finally.
- `memory_manager/phase5/test_qdrant_a1.py` : 6 tests sûrs sur autorisation, refus
  d'écriture de points, fichier exclusif/privé, ressources, YAML/réseau et redirects.
- Commande locale : `python3 -m unittest memory_manager.phase5.test_memory memory_manager.phase5.test_qdrant_a1 -v` → **23/23**.
- Preuve réelle complète avec les trois tentatives, commandes sans secrets,
  mesures, état final et sortie des tests : `JARVIS_2_PHASE5_A1_QDRANT_REAL.json`.

Aucun démarrage Hermes/Ollama, aucune création de collection expérimentale, aucun
patch/redémarrage du service d'embeddings, aucune modification gateway, HA, minage
ou RAM. Budget API distant supplémentaire : **0 CHF**.

## Étape suivante à autoriser : A2

Le patch de l'endpoint brut d'embeddings reste dans le worktree. A2 permettrait
son installation contrôlée sur CT205, la création de la collection expérimentale
et des essais synthétiques. Il nécessite un **accord distinct pour le redémarrage
de jarvis-embeddings**, avec interruption temporaire possible de la recherche
sémantique. Aucun redémarrage de la gateway, de Qdrant principal ou de Gemini Live.
Détails et retour arrière dans le bloc A2 du rapport principal.
