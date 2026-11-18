# Phase 5C — Troisième essai C1 : validation réelle stricte

14 novembre 2026, **20:54:30–20:55:26 UTC**. Nouvel accord explicite reçu pour
un seul scénario synthétique. **`passed=true` pour ce troisième essai seulement.**
B2, premier et deuxième C1 restent inchangés, avec leurs verdicts négatifs.

## Critères démontrés simultanément

| Critère | Observation réelle |
|---|---|
| Recherche vectorielle sans FTS | Appel Hermes `jarvis_memory_knowledge`, requête exacte « masse nominale identique », filtre knowledge, `fts_count=0` |
| Canonique SQLite | Résultat actuel revalidé : mémoire `bfcf1e61-3388-4b2a-9d6e-74084a5e922a`, révision `6ab457b5-f345-43b3-8694-ff6d020705f5`, `canonical=true` |
| Historique | Appel accepté avec **ce même memory_id stable**, sources ancienne et actuelle renvoyées ; événement natif de succès de l'outil |
| Provenance finale | Réponse Hermes citant littéralement `synthetic://doselab/correction` et `synthetic://doselab/old` |
| Persistance | Après arrêt du laboratoire, nouvelle connexion SQLite en lecture seule : mission completed, sortie terminale identique et expérience conservées, quick_check=ok |
| Arrêt | Jobs Hermes/Ollama fermés et processus possédés arrêtés ; ports Windows et contrôleur tous fermés ; fenêtre closed=true |

Mission : `bbda2068-ab44-4dbe-a85d-2a61938a4238`.
Run natif : `run_b711249fe9ec46f48e22b3739b735c07`.
Expérience conservée : `747475aa-bbf5-4771-80f8-6d2ad7453d8f`.
Le modèle a rapporté les quatre cellules identiques de 1 kg et l'ancien ensemble
[1,2,5,10] remplacé, avec ces deux références synthétiques explicites.
Le contrôleur n'a ajouté aucune citation à sa réponse.

## Changement appliqué

Un seul fichier de laboratoire Windows, `memory_manager/phase2/mcp.py`, descriptions
MCP uniquement. Empreinte attendue vérifiée avant sauvegarde et remplacement.
Sauvegarde : `C:/JarvisHermesLab/staging/phase5c-20261114T205350Z-e7349b33`.
Reçu distinct : `JARVIS_2_PHASE5C_C1_THIRD_PATCH_REAL.json`.
Les autres modules, Hermes épinglé et les dépendances n'ont pas été réinstallés.
Les critères précédents sont conservés, avec contrôle supplémentaire du véritable
identifiant historique. Aucune résolution permissive de source.ref/id en memory_id.

Hermes officiel : `4959268e312a21a361f248e49030d5f5df3984d5`, 25 615 fichiers vérifiés.
Modèle existant Qwen3.5:4b :
`d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`.
Contexte servi observé 64 000 tokens, résidence GPU 5 154 285 812 octets.

## Bornes et ressources

- 56 secondes de fenêtre totale ; une mission, **3 appels / 6**, **12 853 / 98 304 tokens**.
- 12 690 tokens d'entrée, 163 de sortie, **0 CHF**, aucun téléchargement/fournisseur distant.
- Admission bridge : 16 ms ; aucun traitement long dans la voix de production.
- Pic VRAM échantillonné 6 627 Mio ; maximum de puissance échantillonné 199,41 W.
  Ces mesures ne sont ni un pic continu garanti ni une énergie intégrée.
- Pic mémoire Job Hermes 378 830 848 octets, limite 2 Gio ; Ollama 8 247 771 136,
  limite 12 Gio. Gardiens existants maintenus, aucun changement de RAM Proxmox.
- GPU final : 1 068 Mio utilisés, 9 172 Mio libres, utilisation 0 % ; Kryptex jamais
  interrompu, détecté non actif aux contrôles.
- Fenêtre fermée ; ports Windows 8643/11434 et contrôleur 8792/11436/8643/11435 fermés.

Preuves séparées :
`JARVIS_2_PHASE5C_SEMANTIC_REAL_20261114T205430Z-dd06b0c3.json`,
`JARVIS_2_PHASE5C_C1_THIRD_PERSISTENCE_REAL.json`,
`JARVIS_2_PHASE5C_C1_THIRD_CLEANUP_REAL.json`.

## Portée et limites

C'est une validation matérielle réelle du scénario strict synthétique, pas une
preuve de fiabilité générale de Qwen ni un pilote personnel. La persistance a été
vérifiée par réouverture SQLite après arrêt des processus, sans redémarrage Windows
ou deuxième mission GPU. Aucune compétence publiée, zéro compétence active dans
ce laboratoire. Données et points synthétiques uniquement dans l'expérimental.
Gemini, gateway, Home Assistant, bases personnelles et `jarvis_memory_v1` inchangés.

## C2 — Inventaire de métadonnées autorisé seulement

Un lecteur distinct interdit au niveau SQLite les colonnes user/assistant/body,
l'index FTS et les écritures. Les titres existants servent uniquement à repérer
les documents : S19/Antminer ET Hydro/refroid ; aucun titre/extrait n'est exporté.
Les dates sont des dates de stockage, pas des mesures techniques.

Résultat : **trois documents repérés par métadonnées, zéro tour normalisé
adressable avec session_id/turn/revision** parmi ces correspondances. Il n'est
donc pas possible de proposer honnêtement une liste de vingt tours exacts à partir
de ces seules métadonnées. Ce filtre n'établit pas l'absence d'autres discussions
dans les corps, qui n'ont pas été consultés.

Rapports privés 0700/0600, ignorés Git :

- `data/phase5c/metadata-only-20261114T205522Z-79aa8756/SELECTION.md` : sélection
  vide et limites, aucun tour fictif ajouté.
- Même dossier, `DOCUMENT_CANDIDATES.md` : identifiants exacts, dates et espaces
  des trois documents, explicitement **pas** des références de tours.
- `inventory.json` et `document-metadata.json` : métadonnées structurées privées.

L'ancienne réserve et le rapport C2 restent bloqués et inchangés. Ce dossier est
un inventaire, pas une nouvelle autorisation de lire/importer vingt sources.
Aucun contenu de tour, conversation exportée ou mémoire personnelle lu ; aucun
modèle/Windows/index privé destinataire. Seuls compteurs et chemins publics.

Prochaine décision C2 : revue privée des trois références documentaires ; si elles
sont pertinentes, définir puis autoriser séparément une procédure de découpage
local borné des exports concernés. Ne pas présumer que leur lecture intégrale
respecterait vingt tours. Aucun découpage, import ou transmission autorisé ici.
C3/C4/C5/C6 demeurent non autorisés.

## Tests locaux après préparation de l’inventaire

`python3 scripts/evaluate_memory.py --phase5c` : **17 commandes réussies**,
dont **21 tests phase 5C** ; fixtures synthétiques uniquement, aucun nouvel appel
GPU. Le nouvel authorizer refuse user/assistant/body, l’index FTS et les écritures.
Les permissions des rapports privés ont été vérifiées : dossier 0700, fichiers 0600.
