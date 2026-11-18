# Interface Hermes v2 (dev)

`hermes-embedded.js` / `.css` remplacent les fichiers servis par la gateway
(`/home/user/gateway/public/jarvis/`). Déploiement : `ops/demand-simple/prod-run.sh ui-update`
(étape `frontend-update-2` de `frontend_update.py`, empreintes épinglées : après toute
modification ici, mettre à jour les deux empreintes `after` de l'étape, le test
`FrontendUpdate.test_pinned_steps_match_reviewed_sources` le rappelle).

L'archivage est local au navigateur (localStorage, identifiants seulement) : il masque
une mission, n'efface et ne modifie rien côté serveur.

Aperçu sur jarvis-dev, données synthétiques uniquement :

    node ops/hermes-ui/preview/server.mjs ops/hermes-ui 18790 &   # fausse API, code « demo »
    node ops/hermes-ui/preview/drive.cjs                           # scénarios + captures (SHOTS=dir)

`drive.cjs` utilise Playwright installé dans `~/tooling/browser` (variable PLAYWRIGHT).
