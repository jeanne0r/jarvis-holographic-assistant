# Phase 5 — B réel : arrêt sur budget avant inférence

14 novembre 2026, accord explicite B reçu. **Essai réel non réussi.**
Preuve : `JARVIS_2_PHASE5_B_WINDOWS_REAL_20261114T192826Z-d47f26b7.json`.
Précontrôles et état final : `JARVIS_2_PHASE5_B_PREFLIGHT_REAL.json`.

## Ce qui a réellement eu lieu

- Protections Windows conformes : règles réseau du compte dédié, profils pare-feu,
  interfaces physiques ; aucune règle ou configuration Windows modifiée.
- Archive Hermes épinglée sur `4959268e312a21a361f248e49030d5f5df3984d5` :
  manifeste SHA256 `5938500e2801bb2157ec04cc14da0fd2fee7d8b693cccdeca94ec4f257ecec0d`,
  **25 615 fichiers vérifiés**, en 11 lots bornés, aucun fichier ignoré.
- RTX 3080 10 Go disponible : 9 172 Mio libres, utilisation 0 %, Kryptex non actif.
  Pilote NVIDIA 621.24. Aucun réglage du mineur changé.
- Nouvelle SQLite synthétique `data/phase5/windows-20261114T192826Z-d47f26b7/`.
  Les vrais embeddings ont indexé **5 nouveaux points**, sans suppression.
- Ollama puis runtime Hermes réellement démarrés dans leurs Jobs existants.
- Le bridge a admis une seule mission, qui a échoué au premier appel au relais.
  Fenêtre : **1 mission, 1 tentative d'appel**, puis fermée définitivement.
- **Aucune inférence générative envoyée à Ollama**, aucun token consommé,
  aucune expérience ni compétence créée ; aucune requête sémantique par Hermes.

Le service Windows a présenté un message générique « API key rejected » parce que
le relais a renvoyé HTTP 403. Ce n'est pas une preuve de secret invalide : la trace
contrôleur indique précisément **PermissionError: System budget exhausted**.

## Cause et correction préparée

Le relais existant réserve **64 000 tokens** avant chaque appel, puis remplace la
réserve par les tokens effectivement mesurés. La capacité de contexte requise par
Hermes reste 64 000. Le nouveau plafond partagé de **50 000** était donc incompatible
avec le tout premier appel, même avec une courte entrée. Le test de budget partagé
antérieur ne couvrait pas cette interaction avec le véritable relais.

La protection a fonctionné ; elle n'a pas été réduite à une estimation heuristique
du nombre de tokens. `check_token_limit()` refuse désormais cette configuration
**avant toute sonde Windows, indexation ou ouverture de fenêtre**. Un test de
non-régression vérifie l'absence d'appel distant lors de ce refus. Le plafond
50 000 reste la valeur par défaut et **n'est pas augmenté automatiquement**.

Le précontrôle initial supposait aussi à tort un Git local et un checkout `.git`.
L'installation réelle provient de l'archive revue de phase 4. Le contrôle utilise
maintenant le manifeste épinglé et les empreintes de tous les fichiers. La première
vérification monolithique a échoué au voisinage de son délai de 50 s ; ses logs
étaient masqués, donc la classe précise de cette erreur n'est pas démontrée.
La vérification complète par lots a ensuite réussi. Ces deux précontrôles échoués
n'avaient démarré aucun service ni mission.

## Arrêt et ressources réellement observés

Le pilote a duré **19:28:26–19:29:06 UTC**, 40 s, sans relance automatique.
Arrêt demandé uniquement aux superviseurs possédés :

| Processus | Pic mémoire Job | Pic mémoire processus | Arrêt confirmé |
|---|---:|---:|---|
| Hermes | 376 463 360 octets | 328 937 472 octets | oui |
| Ollama | 1 284 100 096 octets | 637 673 472 octets | oui |

Ces mesures Windows de Job/processus ne sont pas un RSS Linux ni une mesure
représentative d'une mission avec modèle chargé. Les plafonds Hermes 2 Gio et
Ollama 12 Gio restent inchangés. Les tunnels et serveurs contrôleur sont fermés.
Sondes finales : aucun listener Hermes 8643 ni Ollama 11434 ; GPU à 0 %, 9 172 Mio
libres, Kryptex toujours non actif. Fenêtre fermée, anciennes missions non rejouées.

La collection expérimentale contient désormais **11 points synthétiques** (6 A2
et 5 B). Aucun accès d'écriture à `jarvis_memory_v1`, aucune modification CT205 de
service pendant B, aucun accès aux conversations personnelles ou à Home Assistant.
Budget distant **0 CHF**. Énergie non intégrée ; pas de benchmark GPU d'inférence.

## Nouvel essai à autoriser séparément

Proposition : nouveau budget partagé de **98 304 tokens**, dans le plafond déjà
accepté par le relais, toujours 20 min / 16 appels / 3 missions / coût distant nul.
Ce nouveau plafond **n'est pas autorisé ni exécuté** par l'accord B à 50 000.

Justification : les trois missions phase 4 réussies avaient consommé 34 596 tokens
sur 8 appels ; leur maximum « usage déjà consommé + prochaine réserve de 64 000 »
aurait été **94 637**. 98 304 couvre ce scénario observé. Les nouveaux outils/textes
peuvent toutefois consommer davantage : le contrôle restera bloquant, sans hausse
ni seconde fenêtre automatique si ce plafond ne suffit pas.

Ne pas relancer la mission échouée : créer de nouveaux IDs et une nouvelle SQLite.
Le plan et la commande proposés sont dans `JARVIS_2_PHASE5_B_TRIAL_PLAN.md`.
Le cycle Hermes + RTX + recherche sémantique + apprentissage reste à démontrer.
