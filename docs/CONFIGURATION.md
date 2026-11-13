# Configuration

Copy `.env.example` using `npm run setup`, edit `.env`, and restart the process after changes. The Node 22 `--env-file` loader reads it; existing process environment values take precedence. Never put private credentials in `public/`.

## Required settings

For complete text/voice operation, provide a Gemini key and models that support the adapters in this release. Install/authenticate the Codex CLI as the service user for local requests. Gemini does not get shell or HA tools in the public path.

`JARVIS_ENGINE=hybrid` is recommended. Legacy `codex`, `gemini-fast` and `gemini-live` modes remain available, but do not have identical routing. The engine environment value overrides the ignored `data/core-engine.json` setting. The default local Codex model is configurable independently.

The voice adapters use Google's Interactions API and streaming audio. Consult the [Google model catalog](https://ai.google.dev/gemini-api/docs/models) for your account and compatible API. No arbitrary model swap is promised to work. The optional native Live path uses the Live API instead.

## Paths and credentials

- The project directory is resolved from the module path, not a developer's home directory.
- `CODEX_BIN`: executable name or absolute path; default `codex`.
- `JARVIS_WORKSPACE_ROOT`: optional path for your installation; tool instructions keep operations scoped to the request.
- `CODEX_HOME`: optional Codex configuration directory. When using a nondefault one, ensure it is also available to the Codex service process.
- `data/` contains all application SQLite databases, index bookkeeping, drafts, usage snapshots and generated content.
- `memory/` contains optional Markdown reference files. It is ignored by Git.
- `JARVIS_IMPORT_CODEX_SESSIONS=false` is the default. Set it to `true` only if you deliberately want to index this OS user's Codex session logs. These may contain sensitive material; the built-in text filter is not an exhaustive redactor.

Profiles are `member1`, `member2`, `member3`, `member4`, and `shared`. Rename their display labels in `public/app.js` and `public/index.html` if desired. Changing identifiers requires changing every corresponding backend/Python schema; it is more than changing a label. Profiles are not logins.

## Home Assistant and travel

Set the HA URL/token pair. For personal travel destinations, configure `HA_HOME_ZONE` (default `zone.home`) and `HA_WORK_ZONE_MEMBER1`, `HA_WORK_ZONE_MEMBER2`, etc., with actual HA zone entity IDs. The default work-zone examples are `zone.work_member1` and `zone.work_member2`; create or override them. No real household zone IDs are shipped.

A route between explicit public addresses does not require an HA lookup. A route to your saved workplace does.

## Maps and YouTube

The designated `GOOGLE_MAPS_BROWSER_KEY` is intentionally returned to the browser. Restrict it by allowed website origins and API scopes in Google Cloud. Keep Gemini, YouTube server keys and HA credentials server-side. A private server key is never inferred to be a browser key.

Provider API availability, project permissions, referrer restrictions and billing must all be configured for the APIs your route implementation uses. Without a Maps key, external map links remain possible. A route estimate is only shown when the provider returns it.

## External gateway applications

Create ignored `data/app-links.json`:

```json
[
  {"id":"astro","title":"My astronomy app","url":"https://astronomy.example.test/"},
  {"id":"allemand","title":"Language practice","url":"https://language.example.test/"},
  {"id":"verbes","title":"Verb practice","url":"https://verbs.example.test/"}
]
```

Replace the example URLs with your own reachable sites. Links appear in Usage & memory. These three IDs also work with the existing `open_app` interface action. Extra IDs can be link-only entries. The separate astronomy/language/fridge/crypto apps from the original personal deployment are not part of this repository. Some sites refuse embedding; use the new-tab link in that case.

## Semantic service

`JARVIS_SEMANTIC_URL` is the embedding/search service; `QDRANT_URL` is Qdrant itself. `QDRANT__SERVICE__API_KEY` authenticates both. Compose uses internal container networking while host URLs stay on loopback. The model cache is a named volume. A bare new index contains no memories; indexing creates vectors from your local canonical SQLite records.
