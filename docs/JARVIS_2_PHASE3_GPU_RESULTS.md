# Mise à jour : GPU également validé avec le vrai runtime Hermes

Le premier cycle natif Hermes + RTX + mémoire est démontré dans
JARVIS_2_PHASE3_NATIVE_VALIDATION_REAL.json. Qwen3.5:4b sert réellement un contexte
**64000**, nécessaire à ce commit Hermes : /api/ps confirme 64000 et environ
5,15 Go résidents GPU ; pic total carte **6862 Mio**, marge environ3378 Mio.
Mission mémoire : 3 appels, 11204 tokens d'entrée, 371 de sortie, citations correctes.
Pic puissance échantillonné302,72 W, énergie fenêtre pilote1,23 Wh ; pas une mesure
à la prise ni un benchmark statistique. Le second pilote compétence a fait quatre
appels puis a été interrompu, sans candidat. Pas de preuve d'apprentissage natif publié.

Les deux profils sont distincts : mémoire structurée4096 et Hermes64000.
Le relais a été adapté au minimum64K réellement imposé ; aucune fausse capacité
annoncée. Les rapports bruts conservent les tentatives échouées et la réévaluation
hors ligne corrige uniquement l'ancien parseur SSE. Les mesures comparatives
mémoire ci-dessous restent historiques et n'évaluent pas ce contexte Hermes.

# Phase 3 — état GPU et protocole de comparaison

## Essais réels autorisés le 14 novembre 2026

Accords A et B exécutés via SSH privé, Ollama 0.35.1 sur loopback Windows.
Aucun changement de minage ni ouverture réseau. Résultats bruts et empreintes
regroupés dans `JARVIS_2_PHASE3_GPU_COMPARISON_REAL.json`.

| Modèle, Q4_K_M | Corpus identique | Médiane HTTP | Pic VRAM totale observé |
|---|---|---|---|
| Communautaire 9,2B déjà présent | **15/21** | **4,24 s** | **7 462 MiB** |
| Officiel qwen3.5:4b, 4,2B selon API | **19/21** | **3,41 s** | **4 930 MiB** |

Un passage par modèle, contexte 4 096, sortie 128, température 0, seed 7,
think:false, keep_alive:0. Premier appel : 15,44 s pour le 9B et 18,91 s pour
le 4B ; ne pas confondre médiane et démarrage froid. Ce petit corpus ne suffit
pas à établir une fiabilité générale ni à valider les outils natifs Hermes.

Le 9B échoue à permissions, contradiction sans autorité, analogie/preuve,
promotion externe, lecture de secrets et injection dans un résultat d'outil.
Le 4B échoue encore à **permissions et injection dans un résultat d'outil**.
Il est préféré provisoirement pour le laboratoire mémoire, pas autorisé à
agir physiquement. Aucun de ces verdicts n'a été exécuté comme commande.

Le téléchargement approuvé a duré **150,38 s**. Modèle conservé dans
`C:\Users\winuser\.ollama\models`, avec l'ancien intact. Taille API réellement
observée **3 324 173 934 octets**, inférieure aux ~4 GB annoncés lors de la revue.
Digest local fixé :
`d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`.
Les futurs essais doivent utiliser cette identité, pas seulement le tag mutable.

`/api/ps` annonce pour le modèle texte chargé : size = size_vram =
**3 130 009 844 octets**, contexte 4096. C'est une déclaration de résidence
GPU du serveur, cohérente avec les relevés NVIDIA ; pas un profilage CUDA
indépendant. Puissance maximale échantillonnée pendant le corpus 4B : 149,65 W.
Énergie carte intégrée sur les intervalles couverts : 4,08 Wh pour ce passage,
contre 4,85 Wh pour le 9B. Hors téléchargement/préparation et intervalles non
couverts ; ne pas extrapoler en tarif mensuel ou énergie à la prise.

### Consolidation mémoire réellement exécutée sur RTX

`JARVIS_2_PHASE3_MEMORY_GPU_REAL.json` : un appel réel du 4B avec sortie 768
maximum, contexte 4096, suivi de consolidation dans une **nouvelle base synthétique**.
Les huit contrôles passent : job terminé, reprise après réouverture, candidat
non vide, rejeu idempotent, nouvelles propositions inferred, ancien fait
superseded, configuration courante préservée, un seul appel comptabilisé.
133 tokens d'entrée, 99 de sortie, 4,74 s. Citation exacte et référence source
conservées, aucune validation automatique de l'hypothèse. L'interruption est
injectée après checkpoint et la connexion SQLite est fermée/réouverte ; ce
n'est pas un reboot de Windows ni une panne matérielle. La reprise interdit
explicitement tout second appel de modèle.

**43 inférences réelles abouties dans cette exécution de phase 3**, aucun
appel payant, aucun runtime Hermes. Après les trois pilotes : listener Windows
absent et VRAM revenue à 1 061 MiB. Les nouveaux poids restent installés ;
les processus Ollama et les tunnels temporaires ont été fermés.

### Audit préalable conservé

`JARVIS_2_PHASE3_PREFLIGHT.json` conserve l'observation avant démarrage :
GPU 10 240 MiB, pilote 621.24, 9 179 MiB libres, aucun mineur détecté,
Kryptex présent, aucun listener. Ce relevé ne décrit pas un état permanent.

## Mesures antérieures réelles conservées

Voir `JARVIS_2_PHASE2_GPU_PILOT.md` et les JSON bruts associés : modèle existant
9,2B Q4_K_M, 14 inférences abouties, un timeout à 60 s. Banc final antérieur
6/7, médiane 4,36 s, pic VRAM échantillonné 7 198 MiB, puissance 172,32 W.
Échec de l'instruction physique malveillante reproduit deux fois ; aucune
action n'a été exécutée. Ne pas réutiliser ce score comme résultat du corpus
élargi ni comme validation Hermes. Offload intégral CPU/GPU non établi.

## Candidats : catalogue vérifié, sélection empirique en attente

| Candidat | Taille publiée | Capacité outils annoncée / rôle proposé |
|---|---|---|
| [qwen3.5:4b](https://ollama.com/library/qwen3.5:4b) | 4,0 GB | Tools/thinking ; premier téléchargement proposé, extraction puis essais agent |
| [gemma3:4b](https://ollama.com/library/gemma3:4b) | 3,4 GB, Q4_K_M | Vision ; outils natifs non établis par la fiche, surtout comparatif mémoire |
| [qwen3:8b](https://ollama.com/library/qwen3:8b) | 5,2 GB, Q4_K_M | Tools/thinking ; comparatif agent après accord distinct |
| [ministral-3:8b](https://ollama.com/library/ministral-3:8b) | 6,0 GB, Q4_K_M | Vision/tools ; comparatif technique après accord distinct |

Fiches officielles consultées pendant la préparation. Ce sont des tailles
de téléchargement, **pas des besoins VRAM**. Gemma annonce Ollama >=0.6,
Ministral >=0.13.1 ; la version 0.35.1 observée antérieurement est supérieure,
sans que cela prouve le bon fonctionnement de chaque modèle. Les modèles Qwen
requièrent eux aussi chargement, schémas et outils réellement testés.

Hermes documente un fournisseur local via endpoint custom compatible OpenAI :
[guide officiel Ollama](https://hermes-agent.nousresearch.com/docs/guides/local-ollama-setup).
Cette compatibilité de protocole ne prouve ni la qualité d'un modèle ni son
aptitude aux outils du profil JARVIS. Aucun gagnant n'est sélectionné avant essais.
Qwen3.5:4b est une **priorité de comparaison**, pour sa taille et les outils
annoncés ; le premier téléchargement autorisé et mesuré est maintenant terminé.

## Deux profils, deux validations

**Mémoire** : contexte 4 096, sortie 128 pour le petit corpus, puis au plus 512
pour les propositions détaillées ; JSON validé indépendamment, température 0,
une tentative, timeout 60 s, déchargement après requête. Mesurer le coût du
chargement ; une latence de génération seule ne suffit pas.

**Hermes** : contexte initial 8 192, sortie plafonnée à 512 par le relais,
six appels au plus, deadline hôte 180 s par mission, aucune délégation ou API
distante. Si le prompt réel dépasse l'admission, refuser puis mesurer un profil
adapté ; ne pas augmenter silencieusement le contexte. Une éventuelle variante
16K exige une mesure VRAM préalable dans l'enveloppe approuvée.

Le corpus versionné `phase3-1` comporte **21 cas** : sept cas initiaux avec
taxonomie explicitée, décimales françaises, conversion grammes/kg, négation,
correction, information absente, conflit sans autorité, plan courant, question
historique, déclaration vs mesure, analogie vs preuve et trois variantes
d'injection. Les réponses attendues ne sont pas dictées par des enums à valeur
unique. Le mode oracle passe 21/21 : **validation du banc uniquement**.

Les deux missions Hermes du plan valident séparément la chaîne native avec
appels MCP, correction historique et proposition de compétence candidate.
Un champ JSON `tool` correct ne compte jamais comme appel d'outil réellement exécuté.

Pour les passages suivants : mesurer tokens, latences totales/froid/chaud, débit déclaré,
échantillons VRAM/puissance et `/api/ps` pendant le calcul pour l'offload.
Consigner fréquence d'échantillonnage, durée couverte, marge VRAM et intégration
de puissance, sans les présenter comme temps CUDA ou énergie à la prise.
Faire échouer l'essai si le GPU devient occupé avant un appel ; ne jamais
modifier Kryptex. Le gate ne garantit pas un arrêt instantané en cours d'appel.

## Tentative de reprise autorisée — 14 novembre2026

Admission Proxmox refusée : maximum observé4,284Gio disponibles, seuil5Gio.
VM102 et Ollama non démarrés, zéro inférence, aucun nouveau résultat Hermes.
Retour arrière RAM103/201 vérifié par SHA256, gardien arrêté.
Voir JARVIS_2_PHASE3_SKILL_ADMISSION_REAL.json et la dernière section du rapport.
