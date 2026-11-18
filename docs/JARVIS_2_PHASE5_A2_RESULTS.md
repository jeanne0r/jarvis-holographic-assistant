# Phase 5 — A2 : embeddings et Qdrant expérimental réels

14 novembre 2026. **A2 autorisé et réalisé. B non exécuté.** Preuve :
`JARVIS_2_PHASE5_A2_REAL.json`. Aucun démarrage Hermes/Ollama/RTX, aucun import
personnel dans le Memory Manager, aucune modification gateway ou Home Assistant.

## Activation observée

- Source du service sauvegardé, unité sauvegardée et intégrité du snapshot A1
  revérifiée avant intervention. Aucune nouvelle sauvegarde historique créée.
- Modules minimaux déposés dans la release
  `/opt/jarvis-memory/phase5/releases/20261114T184704Z-65701471/`.
- Configuration additionnelle :
  `/etc/systemd/system/jarvis-embeddings.service.d/80-phase5-a2.conf`.
- État privé et jeton distinct :
  `/var/lib/jarvis-memory/phase5-a2/20261114T184704Z-65701471/`.
  Le jeton n'a pas été copié sur le contrôleur, dans Git ou dans les rapports.
- Prévol dans le vrai venv/FastAPI avec un faux modèle : auth, JSON invalide et
  admission concurrente (200/429), sans charger une seconde instance de modèle.
- Redémarrage sans relance automatique pendant l'intervention, gardien de rollback
  indépendant borné. Après contrôle de santé et premier vecteur réel, gardien
  arrêté et politique initiale `Restart=on-failure` restaurée.
- Le déploiement complet a duré **6,47 s**, prévol inclus. La durée exacte de
  l'interruption HTTP n'a pas été instrumentée séparément.

Le modèle reste MiniLM multilingue ONNX quantifié, 384 dimensions, mêmes cinq
artefacts poids/tokenizer/config. Le démarrage utilise le snapshot local explicite,
`local_files_only=True` et les flags offline. Aucun téléchargement ni installation
de dépendance. Le modèle chargé et le verrou existants sont réutilisés ; un
Tokenizer séparé compte les tokens sans modifier celui du service historique.

Empreinte du pipeline :
`06b237c33b5ff8824befda657bc3c210751771a4138c3af54b12367ae8ba4c7f`.
Source déployé :
`25244dc0ff24d9f61357fa8620d721d4ff9df4709272e0164be6def72fdfcf87`.
Runtime conservé : FastEmbed 0.9.1, ONNX Runtime 1.31.1, Tokenizers 0.23.3.

Le service était et reste celui du compte `jarvis-memory`. L'état privé est
root-owned, groupe jarvis-memory, mode **0710** : le service peut accéder à son
jeton/manifeste 0600, mais ne peut pas remplacer par renommage les scripts et
sauvegardes de contrôle root. Ce refus d'écriture a été testé avec `runuser`.
Aucune modification d'ACL ou de compte Windows.

## Collection historique préservée

Qdrant principal est resté **PID 11122**, vert, **41 428 points** avant/après,
avec la même configuration et les mêmes index de payload. Aucune écriture de
points, de configuration ou de prune sur `jarvis_memory_v1` par cette intervention.

Le nouveau démarrage du service n'effectue qu'un GET sur la collection historique,
sans réémettre de PUT d'index. Ses handlers historiques n'ont pas été remplacés.
`/health` avec l'identité historique fonctionne ; la recherche historique avec
contenu privé n'a pas été appelée exprès pour ces tests.

## Essai réel sur données synthétiques

Une **nouvelle SQLite sur la VM Codex**, sous
`data/phase5/a2/validation-20261114T185019Z-601ae421/`, reste canonique pour cet essai.
Il n'y a pas de nouvelle base canonique sur Windows ou CT205.

La collection `jarvis_knowledge_experimental_v1` a été créée puis reçoit **6 points** :
fragments de trois connaissances actives et d'une ancienne révision conservée.
Le contrôle SSH permet seulement les opérations exactes d'embeddings et de cette
collection ; les clés restent lues dans CT205. Aucun listener/tunnel public créé.

**12 contrôles réussis :** lot borné ; reprise/idempotence ; historique conservé ;
rejet de l'ancienne référence ; recherche vectorielle réelle sans FTS ; correction
actuelle ; isolation d'un autre utilisateur ; outil mémoire contrôlé ; masquage
logique ; retour de visibilité ; reconstruction avec mêmes IDs ; récupération via
une nouvelle connexion SQLite.

La requête **« masse nominale identique »** produit **0 résultat FTS**. Avec les
vrais embeddings/Qdrant, la première connaissance retournée est la configuration
actuelle **[1,1,1,1] kg**, source `synthetic://a2/correction`, statut
`user_confirmed`. Deux connaissances synthétiques sans rapport servent de distracteurs.
Une déclaration de fixture reste une déclaration utilisateur, pas une mesure réelle.

L'interruption a été **simulée par exception**, après un upsert distant réel et
avant le checkpoint SQLite. Après fermeture/réouverture et reprise, aucun doublon ;
la reconstruction explicite conserve les mêmes IDs et le même nombre de points.
Ce test n'est pas un arrêt brutal du CT ni un redémarrage réel d'Hermes.

Une correction de classement a également été apportée côté contrôleur : un
souvenir découpé en plusieurs fragments ne reçoit qu'une contribution vectorielle
par révision, celle du meilleur fragment. Un test empêche un long document de
prendre artificiellement la priorité sur un meilleur résultat court.

## Sécurité réellement vérifiée

**11 contrôles HTTP réels réussis** : refus sans jeton ; refus de l'identité
historique sur le nouvel endpoint ; refus du nouveau jeton sur l'ancien health ;
health historique préservé ; modèle différent rejeté ; contexte >128 tokens rejeté ;
champ de permission rejeté ; JSON malformé rejeté ; query/document en 384 dimensions ;
résultat répété déterministe ; artefact cohérent.

Le plafond d'un appel expérimental concurrent a été testé sur le vrai FastAPI
avec le modèle simulé au prévol, pas par un test de charge du modèle réel.
Les listes d'outils, validations et publications demeurent indépendantes d'un LLM.
Les deux sorties dangereuses de Qwen restent des régressions enregistrées : aucun
nouvel essai Qwen n'a été effectué dans A2.

## Performances et ressources : mesures indicatives

Sur trois appels HTTP loopback dans CT205, entrée synthétique de 11 tokens :
**8,68 à 9,20 ms**. Cela inclut API/comptage/inférence/sérialisation, pas le coût du
transport SSH depuis Codex. Le scénario contrôleur a duré environ **45,30 s** avec
plusieurs connexions SSH, validations et réindexations. Ce n'est pas un benchmark
statistique ou une mesure énergétique.

Au relevé après activation : RSS du service **929 918 976 octets (~886,84 Mio)**,
cgroup **980 877 312 octets (~935,44 Mio)**, mémoire CT disponible
**646 436 864 octets (~616,49 Mio)**. Avant intervention, MemAvailable était
921 396 224 octets ; cet écart (~262 Mio) peut inclure cache et allocations de
startup. Le RSS avant activation n'a pas été capturé : pas d'attribution précise
au Tokenizer cloné ni de comparaison RSS avant/après revendiquée.

Le service reste sain, mais la marge CT doit être surveillée avant d'élargir le
corpus ou la concurrence. Aucune limite RAM Proxmox/CT modifiée, aucune seconde
instance lourde de modèle lancée. Consommation électrique non mesurée. Coût API
distant supplémentaire : **0 CHF**.

## Retour arrière préparé et limites

La fenêtre de démarrage possédait un gardien indépendant qui aurait remplacé le
source par `fallback-service.py`, limité aux handlers legacy et au GET de démarrage,
puis effectué un seul redémarrage de récupération. Le gardien a été démarré et
arrêté au succès ; **le chemin d'échec/rollback n'a pas été déclenché sur le service
réel** pour éviter une interruption supplémentaire. Le fallback a été compilé et
la logique préparée/testée localement, sans prétendre à une validation de panne réelle.

Pour une désactivation opérateur future, après accord correspondant : sauvegarder
l'état actif, activer temporairement `Restart=no`, appliquer le fallback privé et
son drop-in `JARVIS_EXPERIMENTAL_EMBEDDINGS=0` avec readonly=1, redémarrer une fois,
vérifier health puis restaurer la politique de restart. Ne pas restaurer et
redémarrer aveuglément l'ancien source : il réémet les PUT d'index historiques.
Conserver la collection expérimentale et les données ; aucun prune/suppression.

Les scripts de contrôle sont arrêtés ; le nouvel endpoint reste actif dans le
service existant, conformément à l'autorisation A2. La sauvegarde A1 reste locale
à CT205. Le corpus est minuscule : aucune fiabilité générale des embeddings ou du
modèle Qwen ne découle de cet essai. La révision retrouvée est canonique et sourcée,
mais les autres résultats peuvent rester peu pertinents, faute de seuil calibré.

Le premier cycle **Hermes + RTX + mémoire sémantique réelle** reste à exécuter.
Son lanceur est préparé dans `JARVIS_2_PHASE5_B_TRIAL_PLAN.md` ; B attend un accord distinct.
