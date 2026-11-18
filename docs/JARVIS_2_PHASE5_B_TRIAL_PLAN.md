# Phase 5 — Pilote Windows : résultat B et proposition B2

B a été explicitement autorisé à 50 000 tokens. Son essai réel du 14 novembre a
échoué avant inférence sur la réserve minimale de 64 000 tokens ; tous les
processus possédés ont été arrêtés. Voir `JARVIS_2_PHASE5_B_RESULTS.md`.
**B2 a ensuite été explicitement autorisé et exécuté.** Trois missions réussies,
critère strict zéro FTS non atteint par Hermes. Voir `JARVIS_2_PHASE5_B2_RESULTS.md`.
Ce plan ne vaut pas autorisation de nouveaux essais.

## Proposition B2

Machines : contrôleur Codex/Proxmox, CT205 pour les seuls points/vecteurs
synthétiques expérimentaux, PC Gamer pour les processus temporaires Hermes/Ollama
existants. Aucun téléchargement, installation, compte, règle réseau, service
permanent ou changement de RAM. Aucune intervention Kryptex, Gemini Live ou HA.

1. Revérifier les ports libres, protections Windows, manifeste et empreintes des
   25 615 fichiers de l'archive Hermes épinglée. Écart → refus sans correction.
2. Vérifier GPU et minage. Kryptex actif, télémétrie inconnue, VRAM <8 500 Mio ou
   charge incompatible → report ; ne jamais arrêter un processus préexistant.
3. Nouvelle fenêtre, nouvelle SQLite synthétique et nouveaux identifiants, sans
   reprise de la mission échouée ni renouvellement automatique des quotas.
4. Indexation dans `jarvis_knowledge_experimental_v1`, SQLite canonique sur Proxmox.
5. Mission 1 : correction DoseLab, recherche sans hit FTS, historique et provenance.
6. Arrêt du runtime possédé ; mission 2 dans un nouveau runtime : proposer puis
   évaluer une compétence candidate, trois cas fixes et 16 cas étendus par l'hôte.
7. Nouvel arrêt/redémarrage du runtime ; mission 3 : retrouver la même compétence,
   son empreinte et une expérience enregistrée par une mission précédente.
8. Arrêt des Jobs/tunnels possédés, fenêtre fermée et résultats conservés.

## Limites proposées, imposées par les services

- **98 304 tokens partagés** au lieu de 50 000, sans autre hausse de ressources.
  Réserve conservatrice de 64 000 par appel, puis consommation réelle comptabilisée.
  Plafond 50 000 toujours appliqué par défaut et refusé avant démarrage car incompatible.
- **20 minutes**, **3 missions**, **16 appels locaux**, une mission à la fois,
  maximum 6 appels et 180 s par mission. Aucun nouvel essai automatique.
- Contexte servi/annoncé 64 000, modèle/digest Qwen3.5:4b déjà validés, pas de
  fournisseur distant ou fallback ; **0 CHF** de coût API supplémentaire.
- Job Hermes : 2 Gio/20 % CPU/32 processus/300 s. Job Ollama : 12 Gio/80 % CPU/
  32 processus, TTL borné par la fenêtre. Gardes Windows/GPU phase 4 conservées.
- Aucun shell arbitraire, contrôle physique, import personnel ou publication.
  Propositions et compétences candidates restent soumises aux contrôles externes.

Les réservations persistantes, le budget partagé entre missions et le refus de
traverser un mois comptable empêchent le renouvellement implicite du plafond.
98 304 couvrirait les appels du scénario phase 4 observé (maximum de réserve
simultanée 94 637) ; cela ne garantit pas le succès du nouveau scénario. Épuisement
ou erreur → arrêt et rapport, sans accroissement automatique.

## Commande B2 effectivement exécutée après accord

```
python3 -m scripts.pilot_phase5_windows --approved-b \
  --local-token-limit 98304 \
  --private-state /var/lib/jarvis-memory/phase5-a2/20261114T184704Z-65701471 \
  --artifact 06b237c33b5ff8824befda657bc3c210751771a4138c3af54b12367ae8ba4c7f
```

## Arrêt, risques et retour arrière

Charge temporaire CPU/RAM/GPU Windows ; le modèle peut échouer à choisir les outils
ou à produire le résultat attendu. Les protections et quotas sont indépendants de
ses consignes. Un compte dédié n'est pas une sandbox parfaite.

Demander l'arrêt aux seuls superviseurs créés pour cette fenêtre, fermer leurs
Jobs et tunnels ; ne pas tuer les processus par leur nom. Le TTL garde une borne
en cas de contrôleur indisponible. Une mission ambiguë reste en revue sans rejeu.
Conserver les bases et points synthétiques ; aucun prune ni restauration historique.
Les services A2 restent inchangés. Aucune activation de la gateway ou de Gemini.
