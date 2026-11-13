# Architecture and boundaries

## Request lifecycle

1. `server.mjs` serves the frontend and delegates `/api/jarvis/*` to `backend.mjs`.
2. Written text and transcribed speech enter the same `/ask` route with recent history and a profile ID.
3. `hybrid-brain.mjs` asks Gemini to classify the current request. History resolves references but must not reactivate old tasks.
4. Public/general tasks use `fast-brain.mjs`: Gemini emits structured tool requests, the server validates/executes tools, then Gemini answers from observations.
5. Local/HA/LAN tasks use `codex-worker.mjs`: a warm Codex app-server process with isolated ephemeral turns and a scoped private MCP tool bridge.
6. Tool-batch preflight catches local media targets, HA locations and private URLs before public tool effects. It hands the original question and context to Codex.
7. Answers return display text, separate spoken text and validated optional interface effects. The browser applies content-specific actions.

The router uses semantic inference, not a guaranteed classifier. An unclear request may need a clarification. It is not an authorization boundary against a hostile signed-in user.

## Voice

The active hybrid path uses PCM capture, local voice activity gating, Gemini transcription, the common reasoning route and streamed Gemini speech. Output audio levels come from actually rendered PCM. The hologram reacts to input/output audio and real lifecycle events.

Natural mode permits spoken barge-in. Dictation automatically holds capture during processing and until rendered audio drains. Manual mute overrides both: it disables the capture track and discards local input frames without aborting reasoning or clearing playback. Ending the session is a separate action. Tab exit/profile change/new conversation still perform cleanup.

The legacy native Gemini Live adapter is retained but is not the default hybrid path. It has different provider semantics and cost characteristics.

## Memory

SQLite is canonical for conversations, facts, corrections and local usage. Qdrant stores derived multilingual embeddings and payloads. Retrieval validates vector hits against current SQLite source/version/profile data. The index may lag new messages; lexical retrieval remains available. This is retrieval and validated preference storage, not neural model training or guaranteed autonomous self-improvement.

The 3D memory view samples vectors and projects them in the browser-compatible view. It represents an index projection, not a literal map of a model's mind.

## Local tools and code changes

Codex can inspect local services/files and run tools within the requested task. HA controls require actual entity/service resolution. Commands with unknown outcomes are not automatically replayed. The isolated evolution path prepares drafts in a Git worktree; a ready draft does not prove behavior or mean it was deployed.

The public release ships all these mechanisms but no personal infrastructure inventory, saved network credentials, prefilled memories or deployment scripts for someone else's LAN.
