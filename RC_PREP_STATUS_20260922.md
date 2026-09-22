# Windows direct-delivery RC preparation — 2026-09-22

## State

**RC preparation only — NOT SALES-READY.**

This branch changes the Windows delivery model from a bundled Playwright Chromium
folder to a one-file executable that uses the Microsoft Edge installation already
present on supported Windows systems.

## RC changes

- Playwright launches the installed `msedge` channel.
- The configured browser channel is restricted to `msedge` for this Windows RC.
- The packaged application supports `--self-test-browser` for a no-network
  Playwright/Edge runtime check.
- The Windows build collects Playwright runtime assets into the one-file EXE.
- The build fails if the packaged browser runtime self-test fails.
- Source unit tests, credential-marker scans, GUI startup smoke testing, SHA-256,
  and a dependency snapshot are configured.

## Delivery model

Customer-facing delivery is intended to be separate files rather than a ZIP:

- `Web-Evidence-Archiver.exe`
- `config.example.json`
- product documentation as a separate downloadable file

No OAuth client JSON, token file, API key, or other credential may be included.

## Remaining blockers

- A successful GitHub-hosted Windows build has not yet been recorded.
- Manual Windows 10/11 and display-scale acceptance remains required.
- Edge availability/launch behavior must be confirmed on the supported Windows matrix.
- Formal product LICENSE, third-party NOTICE, and SBOM remain to be completed.
- Authenticode is deferred.

Do not label this branch or its outputs as sales-ready yet.
