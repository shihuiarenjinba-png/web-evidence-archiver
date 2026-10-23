# Group C P0: Web Evidence Archiver — MSIX handoff, 2026-10-23

**Designated working branch:** `codex/store-p0-web-evidence-20261023`, from clean audited branch `audit/store-release-hardening-20261019` SHA `1ee1d822537c4adbce89578caed86f8ba99400fa`.

**Owner-confirmed Store ID candidate:** `9NNT1B142ZWV` — confirmed numerically by user, NOT live-verified in Partner Center. Formal Identity Name/Publisher/PublisherDisplayName/PFN, reserved display name, package version/languages and approved logos remain unknown.

**Added:** `store/msix_preflight.py` and its synthetic safety tests; identity record provenance; `store/build-msix.ps1` dedicated candidate builder; conditional Windows Actions preflight and browser-bundled MSIX candidate packaging. No source application code or existing build scripts modified.

## Browser-specific release gates
- This app uses **Playwright Chromium** to produce HTML, screenshot and PDF. It cannot be shipped as a bare Python executable while expecting Chromium to be present in an unapproved local cache.
- Python Playwright's official PyInstaller instructions support hermetic Chromium via `PLAYWRIGHT_BROWSERS_PATH=0` before `python -m playwright install chromium` and freezing. Documentation: https://playwright.dev/python/docs/library#pyinstaller
- `store/browser_bundle_approval.json` is required, with `product_key: "web-evidence-archiver"`, `status: "OWNER_APPROVED"`, `playwright_version`, `chromium_version`, `browser_payload_sha256`, `license_review_reference`, and `bundling_qa_reference`. The SHA is **not a single EXE's SHA**: it is the SHA-256 of UTF-8 newline-delimited lines `relative/path|file_sha256`, with slash-normalized file paths sorted lexically, taken from the packed app's `.local-browsers` tree.
- Chromium license/notices and redistribution, browser version reproducibility, frozen executable launch, network egress/approved host restrictions and GUI real I/O all need independent proof. A matching SHA is not sufficient for real-run QA.

## Other missing inputs / blocking evidence
1. Live Partner Center verification of the product's exact Store ID, Name, Publisher, PublisherDisplayName, PFN and reserved DisplayName; set explicit verification states only with evidence.
2. Owner-approved MSIX `A.B.C.0` version and resource languages, three product-owned PNG logos plus `store/assets/approval.json` with `status: "OWNER_APPROVED"`, `product_key: "web-evidence-archiver"`, `approval_reference`.
3. Clean work branch with HEAD matching origin, passing actual Windows runner logs, EXE/MSIX hash, unpacked manifest equality and packaged browser payload fingerprint.

Run `python store/msix_preflight.py --strict` for a strict readiness check (exit code 2 while blocked) or `./store/build-msix.ps1 -PreflightOnly` on a clean Windows x64 working branch for a JSON report. Conditional GitHub workflow can only build unsigned candidate when ready.

Latest at review: [GitHub Actions run 39922251525](https://github.com/shihuiarenjinba-png/web-evidence-archiver/actions/runs/39922251525) had 0 executed steps, no runner; MSIX candidate job skipped, not verified. Recheck fresh runs.

**MSIX:** NOT PRODUCED. **Windows real install/launch:** NOT VERIFIED. **Certification/submission:** NOT AUTHORIZED. **Sales:** HOLD.