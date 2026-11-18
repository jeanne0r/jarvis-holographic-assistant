# P6-L2 — Délégation hybride réelle en laboratoire

Autorisation distincte reçue le 15 novembre 2026 pour P6-L2 après clôture de P6-L1.
Périmètre : une nouvelle mission DoseLab synthétique, 300 secondes, six appels
modèle maximum, quota partagé de 98 304 tokens, aucun crédit distant.
Aucun microphone réel, aucune gateway active, mémoire personnelle ou action physique.

## Préparation

Réutilisation du cycle Windows, de la copie minimale à empreintes vérifiées, du
panneau, de SQLite et des gardiens de P6-L1. Nouvelle base et nouveaux identifiants;
aucune reprise de son ancienne mission, aucun changement de ses preuves.
Le lanceur possède une entrée/autorisation `--approved-p6-l2` distincte de L1.

L2 active le flag hybride **dans sa copie seulement**. Le backend /ask, la façade,
le bridge et les outils mémoire restent les composants réels du patch minimal.
Le bouton de création du panneau n’est pas utilisé; il sert au suivi du résultat.
La requête part de `window.jarvisAsk` avec un canal voice et un texte synthétique
simulant une transcription. Aucune capture ou émission audio n’est déclenchée.

## Fournisseurs ordinaires simulés, runtime Hermes réel

Un loader strictement réservé à la copie du laboratoire intercepte uniquement
l’import du fournisseur `ai.mjs` par son backend. Il réutilise le vrai routeur
hybride avec classificateur/Gemini/Codex simulés pour les deux demandes ordinaires.
Il ne remplace ni /ask, ni son admission Hermes, ni l’archive SQLite, ni le moteur
configuré, ni le Memory Manager, ni le runtime Windows, ni Ollama.

Cette séparation garantit un coût distant nul et rend les appels fournisseur
observables. La mission admise doit laisser les compteurs inchangés, avant/après;
une régression qui tomberait dans une branche conversationnelle échoue sans jamais
hériter du shell/réseau du worker Codex réel. Ce loader n’appartient pas au patch
production et n’est jamais installé sur la gateway active.

## Vérifications avant l’unique mission

- Anonyme : 401; session expirée : 401; usurpation d’espace : 403.
- Approbation avec le compte opérateur non approbateur : 403.
- Instruction mêlant Hermes et une commande physique : 422, sans worker.
- Flag de laboratoire éteint : 503, sans repli ni admission.
- Deux demandes ordinaires : Gemini simulé et Codex simulé, routage hybrid réel.
- Demande DoseLab : HTTP 202, état queued, execution.engine=hermes-admission,
  execution.routing=hybrid, asynchronous=true; compteurs inchangés.
- Aucun POST de création directement au panneau; mission unique issue de /ask.

Deux tests avec Chromium réel, façade et SQLite réelles, runtime/SSH simulés ont
réussi avant l’essai matériel :
`python3 -m unittest memory_manager.phase6.test_panel_pilot -v`.
Ils exigent un verdict de preuve matérielle faux en l’absence d’appels modèle réels.

## Essai matériel et arrêt

Le préflight en lecture seule précède l’ouverture de l’unique fenêtre de ressources.
Le lancement autorisé est :
`python3 -u -m scripts.pilot_phase6b_hybrid --approved-p6-l2`.
Les résultats et la revue de qualité sont consignés ci-dessous après l’arrêt.

## Résultat réel — P6-L2 réussi

**15 novembre 2026, 06:13:58 à 06:14:48 UTC**, soit 50 secondes pour le cycle
supervisé. Preuve brute :
[JARVIS_2_PHASE6B_P6_L2_REAL_20261115T061358Z-8c0c8df5.json](JARVIS_2_PHASE6B_P6_L2_REAL_20261115T061358Z-8c0c8df5.json).

| Critère | Observation |
|---|---|
| Entrée | Vrai window.jarvisAsk, channel=voice, texte synthétique sans audio |
| Admission | **HTTP 202 en 80 ms**, état queued, identifiant persistant |
| Contrôle serveur | engine=hermes-admission, routing=hybrid, asynchronous=true |
| Classificateur / Gemini / Codex | Compteurs ordinaires avant/après mission **identiques : 2 / 1 / 1**; aucun appel fournisseur pour son admission |
| Création | Une seule mission dans la nouvelle SQLite; **zéro POST direct** de création depuis le panneau |
| Runtime et modèle | Véritable Hermes Windows épinglé, qwen3.5:4b sur la RTX via Ollama loopback et tunnels SSH |
| Mémoire | Recherche MCP réelle puis deux historiques avec les vrais memory_id, trois outils terminés sans erreur |
| Retour | Quatre cellules identiques de 1 kg, ancien [1,2,5,10], références correction/old et expérience visibles dans le panneau |
| Persistance | Résultat terminal canonique et une expérience inferred, aucune duplication |
| Quotas | Une mission, **3 appels modèle**, **13 470 tokens**, **0 CHF distant** |
| Sécurité | Refus avant mission tous conformes; aucune permission shell ou réseau du worker Codex transmise à Hermes |
| Arrêt | Jobs Hermes/Ollama, panneau, serveur et tunnels fermés; fenêtre close et switch off |

Les sept réponses /ask observées par le navigateur incluent les refus et les deux
routages ordinaires simulés; seule l’une admet une mission. Le refus anonyme est
également testé par un client HTTP hôte séparé, sans cookie. Ces requêtes HTTP ne
sont pas des appels modèle : les trois générations réelles sont exclusivement
celles du runtime Hermes. Les demandes ordinaires ne prouvent pas une exécution
réelle de Gemini ou du worker Codex : ces fournisseurs sont volontairement simulés.

L’admission est observée avant le premier tick du worker. La valeur 80 ms est une
mesure locale du lancement de window.jarvisAsk à sa réponse d’admission, sans
microphone/transcription/synthèse. Elle ne représente pas une latence vocale totale.
Le résultat est rendu comme texte dans le panneau existant, sans HTML exécutable
ni notification vocale automatique. Capture conservée dans le dossier privé.

### Matériel et consommation

- Contexte Ollama **64 000**, digest local attendu vérifié.
- Tokens par appel : 3 387, 4 388 et 5 695; latences complètes du relais environ
  4,26 s, 5,05 s et 5,68 s. Pas de mesure indépendante de débit pur.
- Pic VRAM échantillonné **6 873 Mio / 10 240 Mio**; puissance maximale
  échantillonnée **327,7 W**, pas une mesure d’énergie à la prise.
- Hermes Windows : pic processus environ **315 Mio**, Job **359 Mio**, limite
  indépendante conservée à 2 Gio; durée supervisée environ 36,9 secondes.
- Aucune installation, nouveau modèle ou modification de Kryptex.

### Revue de qualité séparée

[JARVIS_2_PHASE6B_P6_L2_QUALITY.json](JARVIS_2_PHASE6B_P6_L2_QUALITY.json)
compare les éléments synthétiques demandés à SQLite. Les capacités, références,
identifiants et horodatages testés sont conformes. Le modèle restitue cette fois
les timestamps **1700000000** et **1700000100** directement; il ne reproduit pas
la date calendaire incorrecte observée dans P6-L1. Cela ne démontre pas que la
conversion de dates est fiabilisée en général : aucun changement de modèle,
aucune correction de prompt ni nouvelle génération pour améliorer le verdict.
La réserve et toutes les preuves P6-L1 restent inchangées.

La connaissance conserve seulement ses deux révisions synthétiques d’origine.
L’expérience nouvelle reste **inferred / unreviewed_report_not_verified_fact**;
aucune hypothèse promue en fait, aucune compétence publiée, aucun accès personnel.

### Vérification finale et limites

- Windows : écouteurs 8643, 11434, 8792 et 11436 fermés après nettoyage.
- GPU : retour à **1 072 Mio utilisés / 9 168 Mio libres**, charge 0 %, minage
  non détecté avant/après; aucun arrêt de Kryptex demandé.
- Tous les fichiers actifs du manifeste sont inchangés; gateway active, même
  **PID 2033987**, aucun redémarrage ni modification de RAM Proxmox.
- Base/capture/audit et configurations privées conservés hors Git sous
  data/phase6/p6-l2-20261115T061358Z-8c0c8df5. Aucun secret dans les rapports.
- Aucune modification CT205/Qdrant, aucune répétition des essais C1.
- La jonction **copie UI → vrai /ask → bridge → véritable Hermes/RTX → MCP →
  SQLite → résultat dans le panneau** est démontrée. Ce n’est ni une activation
  de production, ni un essai de microphone ou de conversation vocale complète.

Les deux blocs approuvés P6-L1 et P6-L2 sont terminés. Aucun service Windows
permanent, raccordement de gateway active, import personnel ou nouvel essai
matériel n’est autorisé par ces validations. Une suite doit préciser son propre
périmètre; les correctifs restent dans le worktree isolé.
