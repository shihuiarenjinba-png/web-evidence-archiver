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


## GitHub Actions execution note

Push-triggered workflow runs were created, but the jobs failed before any runner
steps started. The job records contain no step list and no job log URL, so these
runs do not provide evidence of a source-test, PyInstaller, or runtime failure.
Automatic push triggering is paused on this branch; the workflow remains
available for manual dispatch when the Windows runner environment is available.


## Local Windows RC evidence — 2026-09-22

- Web Evidence Archiver 1.0.0: source tests, Python compile/build path, one-file EXE build, and automated startup smoke passed locally on Windows 11 with Python 3.12.10.
- SHA-256: $sha
- Release dependency lock, CycloneDX SBOM candidate, and installed-metadata third-party notice candidate were generated with the build.
- Customer artifact credential filename scan: PASS.
- Authenticode: DEFERRED until Microsoft approval (current signature state: NotSigned).
- **Not UPLOAD-READY:** product LICENSE approval and Windows 10/11 manual UI/DPI acceptance remain open. For API products, a customer-authorized live endpoint/OAuth test is also not represented by this automated result.
