# JARVIS 2.0 — Phase 6 : intégration préparée et testée en laboratoire

## Résultat et obstacle à l'activation

Le raccordement expérimental est développé : session serveur et ACL, panneau
holographique, admission asynchrone, liste/états/résultats, annulation, canal humain
d'approbation et expérience idempotente dans le Memory Manager. La délégation par
l'outil **Gemini Live natif** traverse le vrai bridge HTTP/SQLite en laboratoire,
avec Google et Hermes simulés. Les résultats gardent leur provenance et leur
statut non vérifié ; aucune publication ni commande physique possible par ce canal.

**Découverte importante : le moteur réellement actif est `hybrid`.** Le routeur
vocal utilise /ask via codex-voice.js, alors que la branche native Live est présente
mais non sélectionnée. Aucun moteur ni routeur changé. La protection de départ
refuse /ask, dont le worker Codex conserve des droits shell/réseau larges.

En conséquence, le patch est **prêt à la revue et aux essais de préproduction**,
mais **pas à une activation transparente sur le Jarvis actuel**. Il faudrait soit
compléter/revoir la délégation dans le chemin hybride avec confinement adapté,
soit décider d'un pilote Live natif en copie de préproduction. Ne pas modifier la
production pour résoudre cet écart sans décision explicite. Le panneau seul
permet de préparer un premier pilote sans confondre les chemins vocaux.

## Travaux réellement effectués

- Audit en lecture seule de server.js/backend/routage/config moteur, empreintes
  conservées. Requête anonyme sans données privées confirme l'absence de garde
  d'authentification générale à l'entrée des routes Jarvis.
- Session humaine opaque distincte du gateway master token, cookie privé,
  expiration, Origin, rôles et espaces serveur ; contrôles complémentaires sur
  mémoire commune, déplacement et archivage vocal.
- Template DoseLab synthétique fixe, idempotence issue du couple session/appel,
  réponse d'admission sans boucle d'agent ; lecture des résultats à la demande.
- Interface existante enrichie, sans changement de son moteur graphique/audio :
  liste/états/progression, résultats texte, erreurs, approbations et notifications
  visuelles discrètes. Pas de parole automatique pour les notifications.
- Réutilisation du worker de disponibilité et du registre canonique ; expérience
  inferred référant l'événement terminal, sans double écriture au fil des ticks.
- Switch indépendant : désactive Hermes à la prochaine requête sans retirer
  l'authentification. Les runs déjà partis nécessitent l'annulation contrôlée.
- Patch concret de **16 fichiers cibles**, empreintes avant/après ; application
  répétée seulement dans une copie temporaire et résultat exact vérifié.

## Tests

**22 commandes réussies** : `python3 scripts/evaluate_memory.py --phase6-integration`.
Inclut régressions, API/SQLite réelles locales, fournisseur et runtime simulés,
contrôles d'accès/approbations, panne du serveur local, persistance et UI headless
desktop/mobile. Preuve séparée : `JARVIS_2_PHASE6_INTEGRATION_TEST_RESULTS.json`.
Détails et limites dans `JARVIS_2_PHASE6_TEST_RESULTS.md`.

Aucun test GPU/Hermes réel phase 6, dépense distante, démarrage de service Windows,
changement Proxmox/CT205, déploiement gateway ou import personnel. C1 reste clos et
ses preuves/historiques sont conservés ; C2 reste au stade de procédure non activée.
C3/C4/C5/C6 demeurent non autorisés.

## Revue et prochaines actions

1. Examiner SECURITY et le diff exact, puis choisir la stratégie compatible avec
   le **mode hybride actif**, sans accorder son worker à Hermes.
2. Revoir comptes, origine privée, espaces et credentials distincts ; aucun secret
   d'exemple utilisable. Services et base synthétique du contrôleur à nommer.
3. Autoriser séparément un pilote réel borné en **préproduction**, éventuellement
   d'abord via panneau. Ce sera une validation de phase 6, pas une relance C1.
4. Uniquement après ces points, examiner la demande d'application du patch actif
   avec sauvegarde vérifiée et interruption gateway explicitement consentie.

Blocs d'accord P6-L/P6-I/P6-G, ressources, arrêt et restauration :
`JARVIS_2_PHASE6_INTEGRATION.md`. Liste exacte des fichiers et SHA :
`phase6/patch-manifest.json`. Aucun opérateur d'application automatique fourni.

La production reste dans son fonctionnement précédent, y compris ses lacunes
connues tant que le correctif n'est pas revu et autorisé. Budget distant
supplémentaire maintenu à **0 CHF**.
