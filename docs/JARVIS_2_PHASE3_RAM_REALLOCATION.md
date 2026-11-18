# RAM Proxmox — diagnostic réel et changement proposé

Audit initial en lecture seule, 14 novembre 2026. La tentative autorisée et son retour arrière sont consignés ci-dessous.
Les compteurs QMP `guest-stats` fournissent MemAvailable et caches même sans
QEMU Guest Agent ; les valeurs UINT64_MAX signifient inconnues, pas une mesure.

| Invité | Allocation | Mémoire disponible observée dans l'invité | Conclusion |
|---|---|---|---|
| VM100 Home Assistant | 4 Gio | environ 1,66 Gio ; swap presque entièrement utilisé | Ne pas réduire pour ce pilote |
| VM103 Codex/gateway | 4 Gio | environ 2,44 Gio, dont cache disque ~1,86 Gio | Une réduction temporaire par balloon est envisageable, sous contrôle |
| VM201 Tailscale | plafond 2 Gio, minimum balloon déjà 1 Gio | environ 1,53 Gio ; cache ~1,17 Gio | Candidat pour une cible temporaire de 1 Gio, sans reboot |
| CT202 AdGuard | limite 512 Mio | ~429 Mio disponibles | Réduire sa limite ne récupérera presque rien |
| CT203 InfluxDB3 | limite 4 Gio | ~3,79 Gio disponibles | Limite élevée mais mémoire peu engagée ; réduire ne libère pas 3 Gio physiques |
| CT204 Catflap | limite 4 Gio | ~3,83 Gio disponibles | Même distinction limite / consommation ; ne pas toucher au GPU ou au service |
| CT205 mémoire | limite 1,5 Gio | ~0,86 Gio disponibles | Hors périmètre de modification autorisée |

Proposition **autorisée par « Ok go », puis exécutée avec retour arrière** :

1. Sauvegarder les configurations 103 et 201 sur l'hôte Proxmox, en root-only.
2. VM103 : conserver le maximum 4096 Mio, autoriser un minimum balloon de
   **2816 Mio**, puis demander cette cible effective (2,75 Gio) à chaud.
3. VM201 : maximum 2048 Mio et minimum 1024 Mio déjà configuré conservés ;
   demander temporairement une cible effective de **1024 Mio** à chaud.
4. Contrôler la RAM réellement récupérée, les MemAvailable invités, la santé
   de la gateway et la réponse de Tailscale. Aucun reboot ni arrêt prévu.
5. Ne démarrer la VM Hermes de **4 Gio** que si l'hôte dispose d'au moins
   **5 Gio disponibles**, afin de garder au moins 1 Gio de marge au démarrage.
   Les gains restent estimés, pas garantis ; l'auto-balloon Proxmox peut varier.

Commandes de mutation prévues : `qm set 103 --balloon 2816`, puis QMP
`balloon` avec `value=2816*1024*1024` sur 103 et `value=1024*1024*1024` sur 201.
Le script `ops/phase3-reclaim-ram.py` a été exécuté avec `--approved` après accord.
La commande HMP équivalente a aussi été vérifiée avec `help balloon`, sans
changement effectif.

Refuser l'opération si la réduction prévue laisserait moins de 1 Gio disponible
dans Codex ou 512 Mio dans Tailscale selon des statistiques fraîches. Vérifier
après récupération. Le cache peut être évincé et les performances varier ;
une lecture au repos ne prouve pas les besoins au pic.

Retour arrière : arrêter **uniquement jarvis-lab** si déjà démarrée, restaurer
le réglage balloon initial de 103 (absent/default), demander 4096 Mio à 103 et
2048 Mio à 201, puis recontrôler services et ressources. Ne modifier aucun
paramètre Home Assistant, CT203, CT204, CT205 ou de minage.

Cette réduction est proposée pour le pilote. À sa fin, préserver l'installation
Hermes sur disque mais arrêter sa VM et rétablir les allocations initiales des
deux VM existantes. Une allocation permanente demanderait une décision séparée.

## Résultat de la tentative autorisée

Commande exécutée depuis le worktree :

```bash
ssh -i /home/user/.ssh/proxmox_codex -o BatchMode=yes \
  -o StrictHostKeyChecking=yes -o ConnectTimeout=4 root@192.0.2.200 \
  'python3 - --approved' < ops/phase3-reclaim-ram.py
```

Sauvegardes vérifiées dans `/mnt/hdd/jarvis-phase3/ram-20261114T064838Z`.
La mémoire disponible initiale était 3 404 845 056 octets (3,17 Gio).
Une observation pendant la tentative atteint 4 813 725 696 octets (4,48 Gio),
sous le seuil de 5 Gio. Les cibles QMP sont réajustées par Proxmox : une
observation montre 3216 Mio pour Codex et 1224 Mio pour Tailscale malgré les
cibles demandées 2816/1024. Le code local de pvestatd et la configuration du
nœud confirment un auto-ballooning visant 80 % d'utilisation, par incréments
limités à 100 Mio. Cette politique globale n'a pas été modifiée.

Après 20 contrôles, le script refuse la création du laboratoire et exécute
le retour arrière automatique. Les deux configurations correspondent **octet
pour octet aux sauvegardes**, SHA256 vérifiés. QMP confirme ensuite 4096 Mio
pour Codex et 2048 Mio pour Tailscale. Aucun reboot, aucune VM créée, aucune
installation Hermes. La RAM disponible après restauration reste variable :
4 869 423 104 octets (4,53 Gio) au contrôle final, encore sous le seuil.

Gateway HTTP 200 et bannière SSH de la VM Tailscale vérifiés après l'opération.
L'état du daemon tailscaled n'est pas vérifié indépendamment, faute d'accès
administrateur à cet invité. La joignabilité SSH n'est pas présentée comme
un contrôle complet du VPN.

Preuve : `JARVIS_2_PHASE3_RAM_ATTEMPT_REAL.json`. Le contrôle de capacité
a arrêté cette tentative ; aucune réduction supplémentaire, aucun arrêt
d'invité ou changement de la politique d'auto-ballooning n'a été entrepris. Pour garantir les
4 Gio demandés avec la marge prévue, prévoir de la RAM physique supplémentaire
ou un autre hôte disposant d'une réserve suffisante. Une autre réallocation
de production demanderait un nouveau plan et un accord distinct.

## Variante ensuite autorisée et appliquée : cibles fixes pour les deux VM

La lecture de `/usr/share/perl5/PVE/AutoBalloon.pm` sur cet hôte confirme
qu'une VM avec `shares=0` est exclue de l'ajustement automatique, tout en gardant
son pilote balloon actif. Cette option permettrait de tenir les cibles déjà
proposées sans changer la politique globale, sans reboot et sans réduire les
plafonds 4/2 Gio. Ce n'est pas encore une preuve que la RAM physique récupérée
atteindrait 5 Gio.

Opérations supplémentaires soumises à accord, sur Proxmox uniquement :

1. Sauvegarder à nouveau les configurations 103 et 201 et leurs valeurs shares.
2. `qm set 103 --balloon 2816 --shares 0` et `qm set 201 --shares 0`.
3. Demander les mêmes cibles QMP 2816/1024 Mio ; vérifier les marges invités
   1 Gio / 512 Mio et les services. Refuser le laboratoire si 5 Gio disponibles
   ne sont pas atteints. Les maxima restent 4096/2048 Mio.
4. Limiter la fenêtre à 30 minutes, avec une surveillance indépendante sur PVE.
   Si une marge mémoire est franchie ou au terme de la fenêtre, arrêter seulement
   `jarvis-lab` si créée, puis restaurer shares, minimum et cibles des deux VM.
5. Vérifier les configurations restaurées et les services. Ne jamais arrêter
   Codex/Tailscale/HA ni intervenir sur les autres invités.

**Risque supplémentaire par rapport au premier accord** : les deux VM ne
pourraient plus recevoir automatiquement davantage de RAM de Proxmox pendant
cette fenêtre. Ce mécanisme contribue à leur protection lors d'un pic de
charge ; son exclusion temporaire exige donc un accord distinct et un gardien
indépendant. `shares=0` a ensuite été appliqué avec accord, puis restauré à l'identique. Une augmentation de RAM physique
ou un autre hôte restent les options sans ce changement temporaire.

## Résultat de la fenêtre autorisée avec cibles fixes

La fenêtre suivante a été autorisée par « Oui ». Sauvegarde vérifiée dans
/mnt/hdd/jarvis-phase3/ram-held-20261114T074643Z. Shares=0 a maintenu les cibles ;
plus de 5 Gio étaient disponibles avant création et démarrage de VM102.
Le minimum hôte observé pendant la fenêtre est 2,43 Gio, supérieur à la marge1.
La fenêtre active de 1800 secondes s'est terminée par l'arrêt gracieux de cette
seule nouvelle VM et la restauration exacte des configurations 103/201. SHA256
identiques, maxima et shares initiaux rétablis. Voir HELD_RAM_REAL.json.

Un pilote Hermes réel a terminé la mission mémoire ; le pilote compétence a été
interrompu à l'échéance, sans candidat. VM102 est conservée arrêtée, onboot=0.
Le mode --reuse-lab a été ajouté ensuite et testé localement pour reprendre cette
VM à partir du dossier gardien précédent vérifié, sans recréation. Il n'a pas
encore été exécuté sur PVE. La fenêtre de 30 minutes ne se renouvelle pas implicitement.

## Essai autorisé — admission refusée le 14 novembre 2026

Après l'accord explicite « Oui go », la fenêtre A/B a été engagée à 2026-11-14T15:31:48.427249+00:00
et refermée avant son échéance : restauration confirmée à 2026-11-14T15:32:56.972207+00:00.
Les configurations103/201 ont été sauvegardées en root-only avec SHA256 vérifié.
Le mode de réutilisation du gardien a été réellement exécuté pour VM102 existante,
sans création de VM ni changement de son allocation4Gio.

Les cibles autorisées103=2816Mio et201=1024Mio, shares0, ont été appliquées.
Les marges invitées sont restées au-dessus de1Gio et512Mio dans les échantillons.
Cependant le maximum hôte observé pendant cet ajustement n'a été que
**4.284Gio**, contre **5Gio requis avant boot102**.
Huit échantillons gardien pendant l'ajustement ; aucun ready.json créé.
Le changement de cible balloon ne garantit pas un gain équivalent de mémoire
physique disponible. La cause précise du faible gain n'a pas été isolée ; ne pas
l'attribuer arbitrairement à un service ou confondre plafond alloué et RAM résidente.

L'appel SSH du contrôleur a atteint son timeout60s pendant apply. La commande
d'admission distante et le gardien sont indépendants de cette connexion ; la
restauration distante a ensuite été vérifiée. Aucun processus apply restant,
gardien inactif, configurations byte-à-byte identiques aux sauvegardes, allocations
103=4096Mio et201=2048Mio restaurées, VM102 toujours arrêtée.
Le timeout du contrôleur n'est pas présenté comme une preuve de marge ni comme
un résultat Hermes ; une future commande de contrôle devra laisser assez de temps
aux observations et à la restauration, sans prolonger la fenêtre du gardien.

Gateway : HTTP200 après restauration. VM Tailscale : SSH joignable, ce qui ne
prouve pas l'état applicatif du démon Tailscale. Windows : RTX libre sans mineur
au précontrôle, Ollama absent après l'essai ; aucune tentative de démarrage.

**Aucun appel modèle, démarrage Hermes ou VM102, nouvelle compétence, installation,
téléchargement, intervention CT205 ou action physique. Coût distant0CHF.**
La première preuve mémoire native reste valide ; le nouveau cycle compétence
n'a pas été exécuté. Les journaux natifs stockés dans la VM arrêtée n'ont donc
pas pu être lus. Les deux missions neuves restent à lancer après admission RAM.

Preuve : [JARVIS_2_PHASE3_SKILL_ADMISSION_REAL.json](JARVIS_2_PHASE3_SKILL_ADMISSION_REAL.json),
SHA256 `c0c9b5d1ede460aa6324cb6020401938cf341eda1c97f554ddca4a07b7036299`.
La fenêtre est close, ses marqueurs ne doivent pas être réutilisés.
Suite : obtenir réellement>=5Gio disponibles avec les mêmes garanties et une
nouvelle fenêtre, ou choisir un hôte de laboratoire offrant la RAM nécessaire.
Aucune réduction supplémentaire d'invité ni baisse de seuil n'est autorisée.
