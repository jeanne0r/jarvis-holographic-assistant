# Validation and release scope

This release is tested as a sanitized standalone application, separately from the original personal deployment. The private production application's history and databases are not distributed.

## Release verification

The standalone release passed 21 JavaScript suites, 26 Python application tests and 9 Python semantic tests on Linux with Node 22.23.5. The browser speech regression passed against the standalone server on its own test port. The actual WebGL scene was rendered in desktop (1440 px) and mobile (390 px) screenshots with no page errors or horizontal overflow. Screenshots use generic profiles and empty memories. The optional embedding containers were not started in this build environment, which does not provide Docker.

The holographic projection refresh also passed WebKit desktop/mobile rendering and non-WebGL fallback checks. Injected event fixtures verified input/output level response, interruption and bounded camera-proximity scaling. These are event/rendering checks, not physical camera/microphone certification.

## Automated checks

- JavaScript unit/integration tests: routing, tool loops, real/unknown HA states, command validation, retries, media and URLs, scoped memory, grounded user corrections, metering and cancellation. Providers are simulated.
- Python checks: conversation archives, spaces, SQLite memory, usage/billing calculations and semantic source validation/projection. Fresh temporary databases are used.
- Browser speech regression: microphone lifecycle, same reasoning endpoint for text/voice, manual mute during a pending answer and playback, uninterrupted output, drain, dictation priority, same-session unmute, explicit stop retaining messages and stale-answer rejection. Capture/playback worklets use a test clock; provider audio is simulated.
- Standalone server checks: health, UI/assets, private-file denial, authentication and a fresh empty-memory install.
- Publication checks: fresh Git history, excluded runtime data, credential-pattern scan and review of staged files.

The public release is not yet a cross-platform certification. Physical iPhone audio/acoustics, every Home Assistant integration, provider model access, optional cloud billing permissions and the Docker embedding stack need verification in the installer's environment. A successful mocked browser test does not prove those external services are configured.

Do not use the original deployment's measured timings or spending as a benchmark guarantee for a new installation. Network, models, provider load, context and tools affect both.
