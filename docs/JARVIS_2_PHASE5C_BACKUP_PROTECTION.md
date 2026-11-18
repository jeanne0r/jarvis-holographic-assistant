# Phase 5C — C5 reporté : protection proposée des sauvegardes

**Proposition uniquement. Aucun chiffrement, transfert, changement de disque ou
création de clé effectué.** Le snapshot A1 actuel reste privé dans CT205.

## Choix recommandé

Chiffrer **avant la sortie de CT205** une nouvelle archive de sauvegarde destinée
à une clé publique dédiée au backup. Le HDD `/mnt/hdd` ne reçoit que le chiffré
et un reçu minimal. Aucun reformatage/LUKS du disque existant, qui contient déjà
des données. Root seul : dossiers 0700, fichiers 0600, pas d'accès par les comptes
Hermes ou les identités des modèles.

L'audit en lecture seule trouve un exécutable GnuPG dans CT205 ; sa version et
son comportement de chiffrement ne sont pas encore qualifiés. C'est l'option à
examiner en premier pour éviter une installation. GnuPG chiffre vers une ou plusieurs
clés publiques, le déchiffrement utilisant la clé secrète correspondante.
[Documentation officielle GnuPG](https://www.gnupg.org/documentation/manuals/gnupg/Operational-GPG-Commands.html).

Alternative si la complexité OpenPGP n'est pas souhaitée : `age`, actuellement
absent de CT205, avec une identité dédiée et plusieurs destinataires de récupération.
Son adoption exigerait une autorisation d'installation/version vérifiée ; pas de
réutilisation des clés SSH d'administration comme clés de backup.
[Documentation officielle age](https://github.com/FiloSottile/age#readme).

## Conservation des clés

- Générer les clés sur une machine personnelle de confiance choisie par l'utilisateur,
  hors Hermes, hors PC Gamer de laboratoire et hors Proxmox. Rien n'est généré ici.
- CT205 ne reçoit que la clé publique relue et son empreinte complète vérifiée par
  un autre canal ; trousseau public dédié, aucune récupération automatique réseau.
- Clé privée principale protégée par une phrase de passe dans un coffre chiffré
  indépendant ; copie de secours chiffrée sur un support hors serveur, conservé
  séparément. Le moyen d'ouvrir cette copie ne doit pas être perdu avec le coffre.
- Aucun secret, phrase de passe, clé privée ou export de coffre dans Git, chat,
  journaux, variables de service Hermes, fichier mémoire ou sur le HDD de backup.
- Une seconde clé de récupération peut être ajoutée seulement après vérification
  de sa garde. Chaque destinataire supplémentaire peut déchiffrer : ce n'est pas
  un schéma à deux personnes obligatoires.

Sans accès à une clé de déchiffrement utilisable, la sauvegarde est irrécupérable.
Une clé publique seule permet de nouvelles copies sans fournir ce pouvoir aux agents.

## Intégrité, restauration et rétention proposées

1. Après accord C5 révisé : qualifier outil/version, clé publique et espace. Vérifier
   taille et SHA256 de l'archive A1 originale, sans toucher à ses points Qdrant.
2. Chiffrer dans un répertoire privé CT205 avec nom temporaire exclusif. Embarquer
   archive et manifeste source dans l'enveloppe chiffrée ; aucune copie en clair
   supplémentaire sur le HDD. Vérifier le retour du chiffreur et fsync.
3. Copier le chiffré vers un nouveau dossier HDD, vérifier taille/SHA256 du chiffré
   aux deux extrémités avant publication sous un nom neuf. Ne rien écraser.
4. Sur la machine détenant la clé privée, déchiffrer un exemplaire réellement relu
   depuis le HDD, vérifier le SHA256 du clair, puis restaurer dans un Qdrant 1.20.0
   isolé avec réseau privé, authentification dédiée et limites de ressources.
   Vérifier 41 428 points du snapshot et schéma/index, sans exposer les payloads.
   L'environnement et le transfert vers cette machine doivent être approuvés avant
   ce test ; ne pas rapatrier la clé privée sur Proxmox pour faciliter l'opération.
5. Le chiffrement ne remplace pas la preuve de restauration : conserver un reçu
   privé de déchiffrement/restauration et un résumé public sans données personnelles.
6. Première copie complète conservée ; futures copies datées immuables, rotation
   et durée à décider ultérieurement. **Aucune suppression automatique** des anciens
   snapshots/clairs ni nettoyage du HDD dans cette phase. La copie A1 en clair dans
   CT205 reste une limite connue de la protection et conserve ses droits privés.

Un SHA256 stocké à côté d'une archive ne prouve pas à lui seul l'authenticité contre
un administrateur compromis. Conserver aussi une empreinte ou un reçu signé hors
serveur. La signature devra être faite par une identité extérieure approuvée.

## Limites et décisions avant C5

Le HDD et CT205 sont sur des disques physiques différents mais dans le même hôte :
incendie, vol de serveur et compromission root restent des risques communs.
Prévoir à terme une seconde copie **chiffrée hors hôte**, autorisée séparément.
Le chiffrement au repos ne protège pas la mémoire de production déjà accessible
à root et ne rend pas sûr un poste de déchiffrement compromis.

À décider : GnuPG existant ou age après installation approuvée ; machine de garde
et de test de la clé ; clé principale et récupération ; environnement de restauration ;
politique de conservation et éventuelle copie hors site. Aucun accord C5 n'est demandé
comme préalable à C1/C2 et rien n'est transféré sur la base de cette proposition.
