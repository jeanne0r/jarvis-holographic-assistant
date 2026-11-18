# Résolution limitée du blocage réseau

Le pilote reste arrêté. `sudo -n -l` exige un mot de passe : aucune élévation disponible, aucun mot de passe demandé ni secret utilisé. Le cgroup du pilote arrêté n’existe plus. Le journal avertit que le filtrage IP est demandé dans une unité non root ; cela ne prouve pas à lui seul son absence. La valeur déclarative IPAddressDeny ne prouve pas l’attachement eBPF. Le marqueur systemd `-BPF_FRAMEWORK` ne suffit pas non plus à conclure sur le filtrage IP interne.

## Vérification administrateur proposée, non exécutée

1. Inspection en lecture seule des programmes effectifs sur les cgroups parents avec `bpftool cgroup show ... effective`, et de la configuration noyau/cgroup. Ne pas démarrer le pilote pour recréer son cgroup.
2. Après autorisation spécifique : exécuter `sudo python3 ops/pilot-network/check-system-filter.py --approved-root-probe`. Ce script crée une seule unité système transitoire, sous le compte existant nobody, avec les restrictions réseau candidates. Deux récepteurs TCP vides et temporaires utilisent exactement le loopback et l’adresse locale de cette VM, sans bind wildcard, requête applicative, accès distant ou modification de pare-feu. Il vérifie la disponibilité des deux témoins hors confinement, puis exige loopback autorisé, adresse non loopback bloquée, filtres ingress/egress effectifs et témoins récepteurs contrôlés avant/après. Arrêt et suppression transitoire via --collect ; aucune activation du pilote. L’unité dure au maximum 15 secondes. Le succès de ce test démontre le chemin système testé, pas rétroactivement celui de l’ancienne unité utilisateur.

Les essais réseau réels ne sont pas réalisés : manque de privilèges, et création d’une unité temporaire soumise à accord. La syntaxe Python et la syntaxe de l’unité système sont vérifiées. Les empreintes des préparatifs figurent dans docs/pilot-interactive/network-preparation.json.

## Repli système préparé, non installé

`jarvis-hermes-pilot-system.service` conserve les ports 127.0.0.1:8796 et 127.0.0.1:8797, l’environnement vide, la limite mémoire 384 Mio et les restrictions initiales. Le compte `jarvis-pilot` sera un compte système sans connexion, sans privilèges et sans capacités. Aucun droit Codex, SSH, Home Assistant ou Windows. Code vérifié et propriété root dans `/opt/jarvis-hermes-pilot`, état privé du compte dans `/var/lib/jarvis-hermes-pilot`.

Une installation nécessitera une autorisation distincte : création de ce seul compte/groupe, copie des seuls fichiers de la release épinglée (36 fichiers du manifeste plus le manifeste lui-même), copie cohérente de l’état existant avec sauvegarde/restauration et contrôle des empreintes, propriété ajustée sur la copie uniquement, installation de cette seule unité système. Les sources et l’état originaux restent conservés, l’unité utilisateur reste arrêtée. Aucun déplacement, écrasement, nouvelle clé ni modification du manifeste nécessaire. Vérifier le refus des chemins personnels sous le nouvel UID avant mise en service.

Après le test transitoire réussi, vérifier l’unité définitive : mêmes filtres effectifs, autorisation loopback, refus hors loopback, chemins inaccessibles, auth et ACL. Cette vérification doit se faire dans le cgroup définitif avant le lancement du processus applicatif (barrière de pré-démarrage supervisée par l’administrateur). Aucun démarrage automatique ni reprise de mission ; pas de redémarrage tant que cette barrière n’est pas validée. La barrière est maintenant implémentée par `startup-guard.py` : le panneau ne peut démarrer qu’après une approbation root fraîche correspondant au nonce de ce démarrage. Un `systemctl start` sans coordinateur échoue volontairement.

Retour arrière : arrêter uniquement la nouvelle unité système et retirer son fichier après accord, conserver compte et état pour inspection ; ne jamais réactiver automatiquement l’ancienne unité utilisateur. Gateway, services existants et état original inchangés.

## Résultat transmis du premier test administrateur

Le résultat historique reste `passed=false`. Ingress et egress sont effectivement attachés au test système ; le loopback aboutit, la connexion hors loopback n’aboutit pas, sans errno. Ce résultat est compatible avec un abandon silencieux de paquets. Il ne démontre pas un échec du filtrage, mais le test initial exigeait à tort un retour EPERM/EACCES pour tous les modes de rejet. Aucun changement des restrictions IP n’est nécessaire pour corriger cette mesure.

Le lecteur du test distingue maintenant explicitement TimeoutError des autres erreurs. Un timeout ne peut réussir que si les deux hooks BPF sont effectifs, les témoins hors cgroup sont joignables et acceptés avant **et** après le test, le récepteur observe le véritable port source de la connexion loopback et n’observe aucune connexion provenant du port source de l’essai interdit. ECONNREFUSED, erreur inconnue, témoin en panne ou connexion interdite acceptée restent NO-GO. Huit vérifications hors ligne du verdict réussissent ; le nouvel essai administrateur n’a pas été exécuté. Aucun redémarrage du pilote.

## Deuxième résultat administrateur transmis

`passed=true` : loopback connecté et observé par le récepteur ; tentative hors loopback en timeout et jamais acceptée ; témoins non confinés sains avant/après ; hooks ingress et egress effectifs. Preuve : `docs/pilot-interactive/network-second-root-result.json`. Le premier verdict false reste conservé. Le chemin système testé est validé ; ni l’unité utilisateur arrêtée ni une future unité définitive ne sont validées par substitution. Aucun pilote démarré. Installation du compte et de l’unité système soumise à accord distinct, avec validation dans le cgroup définitif avant lancement applicatif.

## Installation système autorisée, commande prête

L’utilisateur a autorisé le compte applicatif, les copies vérifiées, l’unité système et son démarrage conditionnel. L’agent n’a pas d’authentification sudo disponible : aucune installation root n’a été exécutée. À lancer depuis le terminal administrateur :

```bash
sudo python3 /home/user/workspace/jarvis-2-memory/ops/pilot-network/install-system-pilot.py --install-approved
```

L’installateur refuse toute installation/compte/état cible existant. Il vérifie le manifeste d’origine et les fichiers d’installation, les permissions et la provenance synthétique, puis la sauvegarde restaurée existante. Il crée `jarvis-pilot` sans connexion, installe la release en lecture seule sous propriété root et copie l’état privé dans `/var/lib/jarvis-hermes-pilot`. Les originaux restent conservés et leurs empreintes sont recontrôlées. La copie possède sa propre sauvegarde et restauration comparées. Aucun token affiché, renouvelé ou transmis ; le code d’accès existant reste identique.

L’unité définitive attend en ExecStartPre. La sonde s’exécute alors sous le compte applicatif dans **son cgroup définitif**, avant tout panneau/bridge ; le coordinateur root vérifie les hooks BPF effectifs, les témoins hors cgroup avant/après et les connexions acceptées/refusées. Seule cette réussite autorise le lancement. L’approbation disparaît après contrôle ; aucun démarrage non supervisé ultérieur ne peut la réutiliser. Les tests temporaires sont nettoyés ; le service, s’il est validé, reste durable sans limite de cinq minutes. Aucun enable, Restart, timer, mission ni processus Windows.

Après démarrage conditionnel : health loopback, refus anonyme, historique authentifié, refus hors espace, refus des anciennes routes, dispatch inactif, UID applicatif, masquage des secrets gateway et absence d’autostart. Tout échec arrête seulement cette unité ; aucune répétition automatique, aucun retrait de protection. Le PID de la gateway est comparé avant/après. Résultat sûr imprimé et conservé dans l’état privé.

Reprise manuelle ultérieure, après accord approprié : même script avec `--start-approved`, sans réinstallation ni copie ; il répète la barrière réseau et vérifie les empreintes installées. Arrêt/retour arrière : `sudo systemctl stop jarvis-hermes-pilot-system.service`, puis retrait de cette seule unité sur accord ; conserver les comptes et copies pour inspection. Ne pas démarrer l’ancienne unité utilisateur. Pas de pare-feu ou de configuration gateway à restaurer : ces éléments ne sont pas modifiés.

Vérifications locales : compilation Python, syntaxe systemd, vérification du manifeste depuis une release déplacée temporaire, refus d’installation sans root, refus de démarrage non supervisé. Aucun de ces contrôles n’est présenté comme une installation ou un test du cgroup définitif. Empreintes et résultats : `docs/pilot-interactive/system-installation-preparation.json`.

## Installation système réalisée et validée

L’administrateur a exécuté l’installateur : verdict `passed=true`, preuve `docs/pilot-interactive/system-installation-result.json`. La barrière du cgroup définitif a validé BPF ingress/egress, loopback et blocage non loopback avec témoins. Identité non root, secrets gateway masqués, historique authentifié disponible, accès anonyme/hors espace/route historique refusés. Dispatch désactivé et zéro mission créée.

L’agent a constaté indépendamment : unité active/running sous jarvis-pilot, ports 8796/8797 uniquement sur 127.0.0.1, health 200, accès missions anonyme 401. Gateway PID 2033987 et date de démarrage inchangés. L’unité est static, sans activation au boot. Aucun appel GPU, Windows ou modèle.

Accès depuis une autre machine : `ssh -N -L 8796:127.0.0.1:8796 user@192.0.2.16`, puis http://127.0.0.1:8796/. Le justificatif opérateur demeure identique et disponible dans le fichier privé original data/phase6/pilot-interactive/operator.token ; ne pas le copier dans Git ou un rapport. Le panneau permet historique synthétique, admission du template DoseLab et annulation. L’exécution de nouvelles missions reste inactive.
