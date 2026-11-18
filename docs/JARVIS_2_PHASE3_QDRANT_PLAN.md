# Qdrant réel — préparation séparée

Aucun appel CT205 ni Qdrant exécuté pour ce travail. Écritures interdites sans
accord spécifique ; la preuve compétence native précède ce raccordement.

## Contrat conservé et durci

SQLite reste canonique. Collection unique autorisée par le transport :
jarvis_knowledge_experimental_v1, vecteurs384 et distanceCosine. Aucun create,
delete, prune ou remplacement de collection dans le prototype. jarvis_memory_v1
est refusée par construction. Les points conservent modèle et empreinte exacte
d'embeddings ; les résultats d'un autre modèle/artefact sont écartés, même si
leur dimension correspond. Ensuite chaque hit est relu dans SQLite : ACL,
révision courante, statut et validité ; aucune charge utile Qdrant n'autorise un fait.

La fonction vector.preflight(driver, embeddings), non appelée automatiquement,
effectue GET de la collection expérimentale et une seule requête d'embeddings
synthétique. Elle vérifie384/Cosine et l'identité modèle/artefact sans écrire
Qdrant. Testée uniquement avec transports simulés. Le contrat /v1/embeddings
attend model, artifact_sha256 et dimensions : vérifier le service réel et
préparer une façade d'attestation si ces métadonnées n'existent pas. Ne pas
inventer l'empreinte à partir du seul nom annoncé par le serveur.

## Étape C1 proposée : inventaire en lecture seule, à autoriser séparément

Sur CT205 : versions/services, origine réseau privée, authentification et rôle,
chemin du modèle réellement chargé, SHA256 des artefacts et métadonnées de
collection expérimentale si elle existe ; espace libre et mécanisme de sauvegarde.
Ne pas copier de secrets ni de données privées ; aucun redémarrage/installation.
Relever les exigences d'adaptation du service d'embeddings et les limiter hors
production d'abord. Inventorier le mécanisme de snapshots Qdrant sans le lancer.

## Étape C2 : sauvegardes puis écritures, nouvelle validation explicite

- Accord précisant machine CT205, chemins, espace et durée. Un snapshot lui-même
  écrit sur disque ; il n'est pas couvert par une inspection en lecture seule.
- Sauvegarde cohérente SQLite par backup API, integrity_check, SHA256, permissions
  privées et réouverture/restauration sur copie de laboratoire.
- Si collection expérimentale existante : snapshot Qdrant ciblé, téléchargement
  privé et SHA256, vérification par restauration isolée avant toute modification.
  Si absente : création384/Cosine uniquement après accord, jamais remplacement.
- Pour tout changement de service CT205 : sauvegarde des configurations et
  artefacts concernés, plan de restauration et arrêt de l'essai sans redémarrer
  les services de production à l'improviste. Aucun snapshot/élagage global de
  jarvis_memory_v1 ; aucune écriture dans cette collection.
- Identité restreinte à la collection expérimentale via mécanisme réellement
  disponible (clé à permissions ciblées ou proxy local allowlist). Aucune clé
  administrateur Qdrant confiée à Hermes ; accès seulement via Memory Manager.

Essai futur : données synthétiques, correction puis indexation idempotente,
recherche sémantique réelle avec sources ; injection d'un ancien hit et d'un hit
mauvais modèle pour vérifier leur exclusion ; interruption de consolidation et
reprise, réouverture SQLite et preuve d'absence de doublons. Conserver les
manifestes, empreintes, compteurs et résultats sans données privées.
Retour arrière : arrêter seulement l'indexeur de laboratoire et couper son
identité ; conserver preuves/SQLite. Aucune suppression automatique de points.
