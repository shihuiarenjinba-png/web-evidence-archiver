# Windows real-device QA handoff — 2026-11-20

Product: **Web Evidence Archiver**

## Frozen GitHub checkpoint
- Branch: `codex/store-p0-web-evidence-20261023`
- Source HEAD before this handoff document: `8d0448a205151eb120631a8b0725183de0d93ec4`
- Latest Windows Actions run at that checkpoint: `44685714145` — **SUCCESS**
- QA_UNSIGNED MSIX artifact: `web-evidence-QA_UNSIGNED-validation-msix-44685169251-1`
- Artifact ID: `14605912850`

## Important package scope
The QA_UNSIGNED MSIX is for package structure / manifest / payload verification only. It is **not Store-certified and not a production install package**. Do not weaken Windows security policy or install a certificate merely to force this package to install.

For immediate real-device functional/UI testing, use the verified portable EXE from the same workflow/source checkpoint. Installed-MSIX lifecycle testing belongs after a trusted/test-signed or Store-signed package route is explicitly authorized.

## Required Windows 11 matrix
- Windows 11 x64
- 100% DPI
- 125% DPI
- 150% DPI
- Test at a normal desktop resolution and, where practical, 1024×768-class constrained layout.
- JA and EN UI where the product exposes both languages.

For every matrix cell record:
- OS build
- resolution / DPI
- source HEAD
- EXE SHA-256
- launch result
- core operation result
- error-path result
- screenshot path/name
- PASS / REVIEW / FAIL
- short note for any clipping, unreadable text, disabled control, crash or unexpected file write

## Product functional cases
1. Capture one simple static HTTPS page.
2. Capture a JavaScript-heavy page allowed by the product policy.
3. Try an unreachable/invalid URL and confirm truthful failure reporting.
4. Verify produced HTML/PNG/PDF/hash outputs that the current branch claims to create.
5. Confirm partial capture never appears as complete success and prior evidence is not silently overwritten.

## Common safety acceptance
1. Launch succeeds without developer/debug controls exposed in normal UI.
2. Primary action is reachable and understandable.
3. Invalid input does not crash the app.
4. Original user input is not overwritten unless a feature explicitly says otherwise.
5. Output location and success/failure state are clear.
6. Close and relaunch once; stale/corrupt UI-state must not prevent startup.
7. No unexpected network access for products documented as local-only.
8. Capture Store screenshots only from real app UI with synthetic/non-personal fixtures.

## Exit condition
Mark this product `WINDOWS_REAL_DEVICE_QA_PASS` only if all required matrix cells and product functional cases pass or have an explicitly accepted limitation. Any crash, incorrect output, hidden overwrite, misleading privacy result, or unusable DPI layout is a release blocker.

Formal Store candidate generation remains separately blocked until the exact approved Store version and final brand assets are recorded. Never substitute the QA workflow-generated version for that approval.
