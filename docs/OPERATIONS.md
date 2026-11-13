# Operations

## Start and stop

Run `npm start` from the project directory. Stop it with Ctrl+C. In a service manager, use the same OS user and project directory as your Codex login, and an absolute Node 22 executable. Treat `.env` as a private file, not a system-wide shell script.

After a code/configuration update:

```bash
git pull --ff-only
npm ci
npm test
# stop your running Jarvis process, then:
npm start
```

Never restart the host gateway from inside the response worker that is answering the current request.

## Backups

Stop Jarvis and any indexing process before copying SQLite files, or use SQLite's supported backup facility. Keep a protected backup of `data/`, your optional `memory/` files, and any Docker volume snapshots you need. Back up credentials separately and securely. Do not commit backups.

SQLite is the source of truth. If Qdrant is lost, restore SQLite and rebuild the semantic index rather than treating vectors as the only memory copy. Empty/new SQLite data means empty/new memory.

## Indexing

With semantic services running:

```bash
npm run memory:index
```

For automatic updates, schedule the same command from your service manager or cron, with the correct project directory and Node executable. It reads `.env` through the npm script. The indexer uses a file lock, tracks source versions and indexes changed documents. Do not copy an old index-status JSON as a substitute for indexing.

Qdrant's dashboard is available locally at `http://127.0.0.1:6333/dashboard` when provided by the image. It needs your Qdrant key. Keep its port private; do not expose your memory index publicly. See the [Qdrant quickstart](https://qdrant.tech/documentation/quickstart/).

## Troubleshooting

| Symptom | Checks |
| --- | --- |
| The page loads but AI fails | Run doctor; check your provider model IDs/access and server-side keys. |
| Mic/camera unavailable on iPhone | Use trusted HTTPS, the server's LAN hostname, and browser permissions. |
| TLS record error | Confirm the port really serves HTTPS; changing the address scheme alone is insufficient. |
| Audio cuts off | Try dictation or manual mute; check speaker echo, browser audio permissions and network stability. |
| Slow local question | Check Codex/model/tool timing; more CPU cores do not guarantee faster cloud inference. |
| Wrong HA entity | Ask a precise question, check its actual HA name and correct the association. Fresh values require a new HA read. |
| Empty semantic/3D memory | Wait for the first model download, check services/key, then run indexing. |
| Radio/YouTube silent | Tap the player to satisfy Safari's media gesture policy; check the verified stream is reachable. |
| Website cannot embed | Open its new-tab link; many sites block iframes. |
| Cost differs from Google | Local figures are estimates; billing exports lag and provider pricing can change. |

For logs, prefer status/timing metadata. Do not publish full prompts, conversation exports, URLs with credentials, raw environment files or authentication responses.
