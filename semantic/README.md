# Jarvis semantic memory

SQLite is canonical: `data/brain.sqlite` holds conversations/notes, `data/voice-memory.sqlite` holds explicit durable facts and HA aliases. Qdrant is a rebuildable index. Audio is not saved. New written exchanges and voice transcriptions are now archived automatically in the selected space; explicit stable facts/aliases remain separately managed through `memoire_jarvis`. Browser retries contain redacted text only.

- Proxmox CT205 `jarvis-memory`, unprivileged Debian12, 2 CPU, 1536MiB RAM, 256MiB swap, 8GiB SSD thin disk. Autostart on, included in `backup-other-vms`.
- Static IPv4 `192.0.2.238`. DHCP initially assigned `.41`, already used by another MAC: DNS replies went to that device. Three ARP probes found no owner for `.238` before assignment. No other device configuration changed.
- Qdrant1.20.0, official x86_64 musl binary, SHA256 verified using release metadata in `qdrant-release.json`. GNU build needs newer glibc than Debian12.
- `jarvis-qdrant.service` and `jarvis-embeddings.service` run as `jarvis-memory`, not root. Qdrant collection `jarvis_memory_v1`: 384 dimensions, cosine, vector/payload on disk; `space`, `doc_id`, `version` keyword indexes.
- Local FastEmbed `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, quantized ONNX distribution maintained by Qdrant. Multilingual, 128 input tokens; 400-character overlapping chunks and title prefix. Large blocks can be truncated by the model. No embedding API charges and no texts sent to an embedding provider.
- HTTP6333 (Qdrant + dashboard) is allowed from LAN192.0.2.0/24; data API requires the existing secret. HTTP6335 (embedding/search bridge) remains limited to Codex VM192.0.2.16 and requires its secret. No public forwarding. gRPC6334 is blocked. DNS reply rules limited to LAN resolvers.
- Credentials: `/home/user/workspace/_secrets/jarvis-qdrant.env` on Codex, `/etc/jarvis-memory.env` in CT205. Never copy their contents into logs or memory. `.238` is configured in the private Codex file, not the old DHCP hostname.

The CPU embedding model runs in the CT and handles both query/document vectors. The bridge binds localhost Qdrant calls and authenticates all its routes. It never receives arbitrary URLs, SQL or shell commands. The model downloads its public weights once to `/var/lib/jarvis-memory/models`.

`jarvis-semantic-index.timer` runs a resumable incremental index five minutes after the prior pass finishes. `index.py` reads a snapshot of source rows, hashes title+body, upserts new chunk versions before deleting old versions, and removes deleted source IDs. `data/semantic-index.sqlite` tracks completed documents; `data/semantic-index-status.json` is a private progress file. Initial indexing may take several minutes; future passes only update changes. An empty collection resets the local manifest for rebuilding.

`knowledge.mjs` bridges the chat and voice tools to `search.py`. Searches combine SQLite FTS5 keyword candidates with Qdrant semantic candidates using reciprocal ranks. Structured voice facts are also searched directly in SQLite. Every vector hit is checked against canonical SQLite for space, existence and content version before any excerpt is returned. Deleted/changed facts or documents cannot be resurrected by a stale vector. Active-person and shared-space filters are applied in Qdrant and rechecked on the server. Existing person separation is classification, not authentication.

When Qdrant is unavailable, keyword search and SQLite facts remain available. The original full texts are retained. Relevant excerpts from either retrieval path are sent to the existing answer provider: OpenAI for written chat, Google for Gemini voice. Old excerpts are not treated as current HA states or as instructions.

Operate from Codex:

```bash
systemctl --user status jarvis-semantic-index.timer jarvis-semantic-index.service
systemctl --user start --no-block jarvis-semantic-index.service
python3 semantic/test_search.py
python3 test_voice_memory.py
node test_live.mjs
```

Inspect CT services through the existing private Proxmox SSH key and `pct exec 205`. To rebuild the index, stop the index job, recreate the collection and clear the incremental manifest, then rerun. Do not remove canonical SQLite files. Installed dependencies are pinned in `requirements.lock`. The bootstrap script expects this file, service.py, release metadata and the private environment file to be staged in the CT.

Official references: https://qdrant.tech/documentation/overview/ and https://qdrant.tech/documentation/embeddings/fastembed/.


## Continuous conversations (2026-11-11)

User explicitly authorized automatic archiving. `store.py` stores conversation session bindings and versioned turn snapshots in the canonical brain SQLite, projecting each turn into the existing docs/FTS5 library. Written questions and answers (including deterministic quick replies) are saved on the server; the browser also mirrors local confirmations/actions. Shared IDs/revisions avoid duplicates. Voice session person/channel bindings are created server-side and survive gateway restarts. Voice transcript snapshots use that trusted binding regardless of a caller-supplied space. Interrupted replies are labelled because generated transcription may exceed what was heard.

`public/archive.js` keeps only redacted pending snapshots in localStorage, retries on reconnect and reload, and flushes at pagehide with beacon/keepalive. Server-side cleaning runs before both journal and document writes. No API credentials, raw audio or tool results are archived. The voice path snapshots at800ms, completion, interruption, stop and pagehide. Long turns split into16000-character segments. Hard browser/device termination before any snapshot can still lose the latest not-yet-transmitted fragment; the UI reports queued/failing saves instead of claiming everything was saved. Successful records appear as Jarvis sources in the library and are immediately searchable by words. Current partial turns are excluded from retrieval for60 seconds to avoid the model citing its own just-asked question as evidence.

The indexer prioritizes fresh Jarvis exchanges and explicit voice facts every20 seconds between document indexing operations, even during initial indexing. It re-reads canonical IDs before pruning so new additions survive. Otherwise incremental passes remain five minutes after prior completion. Qdrant can therefore lag SQLite; latest changes remain canonically checked before retrieval.

Tests: `python3 test_conversations.py` covers persistence, revisions/idempotency, scope binding across processes, interruption labels, invalid requests and secrets. `verify-archive.cjs` covers written Enter, durable queue retry across reload and browser redaction on LAN HTTP. `verify-gemini.cjs` also checks interrupted voice transcription capture. An actual written API exchange and voice record were verified in SQLite; the written exchange automatically reached Qdrant during initial indexing. Synthetic verification records were removed from journal/docs/FTS/Qdrant afterward.

`memoire_jarvis` forgets a structured fact; it does not erase whole historical conversation transcripts. Session/turn revisions prevent late retry packets from overwriting newer saved text. Text archiving relies on received Google transcripts, which can contain speech recognition errors; it does not retrain Gemini or imply its old answers were true.

Web dashboard installed at user request on 11 November 2026: http://192.0.2.238:6333/dashboard/. Official qdrant-web-ui v0.2.20 release ZIP, SHA256 checked against GitHub asset digest (metadata in web-ui/release.json). Static files in CT205 /opt/jarvis-memory/static, explicitly configured with service.static_content_dir and enable_static_content. Matching Qdrant1.20.0 openapi.json included. Static UI accessible without key; API data still returns401 without key. Use QDRANT__SERVICE__API_KEY from the existing private credential file in the UI password field, never in a URL. No key embedded in assets. Browser test authenticated privately and verified jarvis_memory_v1 appears; LAN test from Proxmox returned200. Qdrant and embeddings services active. Pre-change config /opt/jarvis-memory/qdrant.yaml.before-web-ui in CT; firewall backup /root/205.fw.before-web-ui on Proxmox. Port6335 restriction unchanged.
