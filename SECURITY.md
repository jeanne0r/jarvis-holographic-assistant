# Security and privacy

## Intended deployment

Jarvis is a private, trusted-household assistant. It can start an authenticated coding agent and control devices. Keep it on localhost, a private LAN, or a private VPN. Do not expose it anonymously to the Internet.

The standalone server binds to loopback by default. Non-loopback binding requires HTTPS and a configured password. Browser authentication uses username `jarvis` and `JARVIS_ACCESS_PASSWORD`; use a long random value. This is one shared household login, not a multi-user identity/access-control system. If you need strong tenant isolation, this release does not provide it.

Codex runs unattended requested tasks with configured workspace-write sandboxing and network access. Those tools are powerful. Run under an OS account whose permissions match the trust you place in household users and the agent. Prompt rules and input filters do not make arbitrary local tool use risk-free. Review code changes and test before deployment.

## Data flow

- Google sees transcribed requests/recent context for routing, public reasoning/search requests, microphone phrases for transcription, and text for speech.
- OpenAI receives local/HA requests and the context/tools needed by Codex.
- SQLite stores conversation text, facts and local usage. The app does not persist raw microphone audio.
- Optional Qdrant/embedding services store derived memory representations and text payloads locally.
- Camera face detection is local in the browser; camera frames are not sent to the AI provider by the face-tracking implementation.
- External media/maps/web providers see requests needed to provide their content.

## Keep out of Git

Never commit `.env`, API keys, passwords, access tokens, Codex/Google OAuth files, certificates/private keys, SQLite data, Qdrant snapshots, conversation exports, screenshots with private information, or production logs. Exclusions and the publication scanner help but cannot guarantee complete redaction.

Secrets are configured on the server. The explicitly designated Maps browser key is a deliberate exception and must have appropriate origin/API restrictions. If a real secret was ever committed or published, deleting the current line is insufficient: revoke/rotate it and assess the history.

The public initial commit was created from reviewed source files rather than from the private deployment's Git history. No runtime backups or memories were exported.

## Reporting

Do not include credentials, conversations or exploitable household details in public issues. Use GitHub's private vulnerability reporting channel if enabled on the repository; otherwise contact the maintainer privately before sharing sensitive reproduction material.
