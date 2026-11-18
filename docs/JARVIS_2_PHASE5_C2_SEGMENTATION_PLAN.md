# C2 — Découpage déterministe préparé, aucune nouvelle lecture personnelle

## Périmètre effectivement examiné

Uniquement le code isolé de `store.py` et les métadonnées du catalogue privé déjà
créé. Les trois documents sont classés **un ChatGPT et deux Codex**. Aucun corps,
export original, nouvelle conversation ou index FTS personnel ouvert. Aucun
contenu personnel envoyé à Windows, Hermes ou un modèle. Ancienne réserve C2 et
rapport bloqué conservés, sans nouvelle sélection de contenu.

Les identifiants documentaires restent dans le catalogue privé existant :
`data/phase5c/metadata-only-20261114T205522Z-79aa8756/DOCUMENT_CANDIDATES.md`.
Aucun titre, extrait ni identifiant privé n'est recopié dans Git.

## Structure observée dans le code des importeurs

| Format | Structure technique observée | Limite de provenance |
|---|---|---|
| Jarvis normalisé | session_id, turn, revision, rôles user/assistant, updated et espace de session | Pas de tour normalisé correspondant dans le précédent inventaire par titres ; updated est une date de stockage |
| ChatGPT original | mapping de nœuds, parents, current_node ; message.author.role et content.parts ; importeur suit la branche active | La mise à plat dans docs ne préserve pas tous les identifiants/dates de chaque message ; branche active à expliciter |
| Codex original | JSONL avec session_meta, response_item/message, role et phase ; chemin alternatif event_msg | L'importeur privilégie assistant final, exclut les sous-agents et nettoie le texte ; dates de fichiers et empreintes ne sont pas des dates de mesure |
| docs.body stocké | Texte joint par marqueurs Toi:/ChatGPT:/Codex:, parfois tronqué à 250 000 caractères | Ambiguïtés de citations, frontières et métadonnées perdues ; découpage par regex refusé |

Cette description est fondée sur le **code**, pas sur une inspection des exports
personnels. Leur existence/accessibilité et leur version exacte ne sont pas encore
confirmées. Ne pas importer `store.py` pour un audit : il ouvre et migre la base à
l'import. Ne pas appeler sync, listing/get ou les importeurs pour cette préparation.

## Procédure proposée en deux approbations distinctes

### A — Autorisation d'établir les frontières structurées

Après revue privée du catalogue, désigner précisément les documents pertinents et
leurs exports structurés d'origine, avec emplacement et version. Autoriser ensuite
un inventaire structurel local limité à ces exports : IDs de messages, rôles,
parent/branche, phases, dates, révisions ou positions stables. Aucun texte ne doit
être projeté dans le rapport ou envoyé à un modèle.

**Cet accès aux exports n'est pas couvert par l'accord actuel.** Un inventaire
structurel de JSON/JSONL peut néanmoins devoir parcourir les octets contenant le
texte pour localiser des champs/limites. Ce n'est pas une lecture purement SQL de
métadonnées : le périmètre, le volume et ce parcours doivent être explicitement
acceptés avant ouverture. Si cela n'est pas acceptable, fournir un export de
métadonnées séparé ou les références de messages déjà indexés. Aucun scan récursif
de toutes les sessions, aucun élargissement aux fichiers cités par les messages.

Utiliser les rôles structurés, jamais les chaînes de locuteur du texte. Pour
ChatGPT : branche active seulement, cycles/doublons rejetés. Pour Codex : un seul
flux de messages choisi, assistants finaux, pas de doublonnage response_item/event_msg.
Un tour est un message utilisateur et ses réponses finales associées, jusqu'au
prochain utilisateur ; les réponses multiples sont conservées distinctement.
Un tour incomplet/ambigu n'est pas remplacé silencieusement. Aucun système/outils
intercalés n'est promu en instruction ni injecté dans le corpus technique.

Le noyau pur `memory_manager/phase6/turn_plan.py` reçoit seulement des métadonnées
explicites déjà structurées ; il ne lit aucun fichier/base/réseau. Il refuse les
formats aplatis, champs text/content, IDs ambigus et dates invalides. Les adapters
vers les exports privés et leur lecteur de corps ne sont **pas branchés**.

### B — Autorisation de lire le lot précis pour import à blanc

Présenter un manifeste privé d'au plus **20 tours au total pour ce pilote**, tous
documents confondus, avec :

- Document, espace, branche, ID utilisateur et IDs des réponses finales.
- Version/empreinte de la source et révisions/positions des messages.
- Dates originales disponibles ; inconnues laissées nulles. Date d'import/de
  fichier présentée séparément, jamais substituée à une date de message/mesure.
- Empreinte du manifeste et raison de sélection issue des métadonnées.

Obtenir l'accord sur **ce manifeste exact**. La réserve de l'ancien C2 reste
bloquée ; cette reprise doit être explicitement approuvée comme nouveau périmètre,
avec son lien d'audit à l'incident. Aucun cumul automatique de lots de vingt.
Réserver une seule fois l'ensemble du lot avant lecture ; sources ensuite écartées
et tentatives interrompues comptent. Pas de remplacement ou de 21e tour.

Avant toute extraction : vérifier l'intégralité du manifeste, l'espace et la
version de chaque source, puis seulement lire les messages sélectionnés. Si une
source a changé ou n'autorise pas une extraction ciblée démontrable : arrêter
avant de lire les corps, ne pas retomber sur le chargement complet de docs.body.
Une révision native absente reste absente : empreinte de snapshot clairement
distinguée d'une révision du fournisseur ; aucune révision inventée.

Rapport privé local 0700/0600, sources en lecture seule, rôle et provenance par
segment ; déclarations/hypothèses/mesures séparées, aucune validation automatique.
Aucune écriture dans SQLite/Qdrant de production ou expérimental personnel, aucun
import canonique, transmission Windows ou modèle. Une éventuelle ingestion et
transmission exigeront encore les accords correspondants (C3/C4 non autorisés).

## Refus et reprise

Après interruption, garder la réserve et le manifeste : aucun nouveau lot, aucune
remise à zéro du nombre de sources examinées. Reprendre seulement les références
réservées sous un accord clair, sans élargissement. Le journal privé distingue
métadonnées inventoriées, corps réellement lus et sources écartées. Aucun journal
public contenant le texte. Les sources originales et anciens rapports ne sont
jamais corrigés pour masquer l'incident.

## Tests exécutables sans donnée personnelle

Fixtures structurées : vingt tours, refus de vingt-et-un/doublons/tour incomplet,
refus de texte dans l'entrée metadata, empreinte stable, nouvelle révision invalidant
le manifeste, absence de date non remplacée par updated_at. Le test de citation de
locuteur démontre que ce texte n'est pas accepté comme frontière structurée.
Ces tests ne prouvent ni la compatibilité d'un export privé précis ni une extraction
personnelle réelle. Aucun nouveau contenu personnel n'a été lu pour les écrire.
