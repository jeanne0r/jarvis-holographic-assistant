# Contributing

1. Fork and clone the repository.
2. Install Node 22.6+, Python 3.10+ and dependencies with `npm ci`.
3. Run `npm run setup`. Use your own ignored `.env` only if testing live integrations.
4. Create a focused branch and preserve the default hybrid routing, privacy controls and microphone lifecycle.
5. Add a meaningful regression check for behavior you change. Run `npm test`.
6. For audio/UI changes, run the relevant Playwright check with mocked providers. Do not send personal audio or paid cloud requests in CI.
7. Run `git diff --check` and `npm run scan:public` on staged files.
8. Describe the problem, final behavior, validation and any remaining limits in your pull request.

Never attach runtime databases, tokens, full environment dumps or household screenshots. Keep upstream vendor notices intact. Documentation is maintained in English; the current UI and assistant persona are French.
