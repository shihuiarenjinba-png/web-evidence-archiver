# Group C — GitHub completion / code-owner handoff

Date: 2026-10-24  
Product: **Web Evidence Archiver**  
Repository: `shihuiarenjinba-png/web-evidence-archiver`  
Work branch: `codex/store-p0-web-evidence-20261023`  
Code HEAD before this handoff-document commit: `73d3ce8b7973144aab3948f85159b52ae6b43404`

## Store identity evidence

- Store reserved DisplayName: `Web Evidence Archiver`
- Store ID: `9NNT1B142ZWV`
- Package Identity Name: `OkinawaDesktopTools.WebEvidenceArchiver`
- Publisher: `CN=46263F21-A700-41DB-8C9B-114C22FB82FC`
- PublisherDisplayName: `Okinawa Desktop Tools`
- Evidence: owner-provided Microsoft Partner Center **View product identity** screenshot shared in this conversation.
- Store Version: **UNKNOWN / HOLD**. Do not infer a value from historical builder defaults.

## GitHub-side work completed

- Store identity metadata updated on this work branch.
- Existing MSIX builder structure preserved and hardened with repository/origin/fetch/branch/local-vs-origin HEAD/dirty checks.
- MSIX candidate source commit is embedded as `SOURCE_GIT_COMMIT.txt`.
- Unpacked manifest path verifies Identity Name, Publisher, Version, x64, PublisherDisplayName and Store DisplayName before success.
- Old implicit `1.0.0.0` Store-version default is not accepted where it previously existed.
- UI-only improvements were kept separate from processing logic, with Store-name/layout/path-privacy changes where applicable.
- No `main` / `release` merge was performed.
- No certificate, signing, Defender, certificate-store or OS-security setting changes were performed.
- No Partner Center upload, certification submission or publish action was performed.

Build entry: `store/build-msix.ps1`

Playwright/Chromium payload version, redistribution/license evidence, browser payload SHA-256 and Windows QA remain additional HOLD gates.

## Latest GitHub Actions evidence

- Run ID: `40027409103`
- Jobs: 120666951644 inspect steps=0 failure; 120666970558 build-unsigned-candidate skipped
- Runner: **not assigned**
- Executed steps: **0**
- Result must be reported as **NOT RUN**, not test PASS.
- MSIX artifact: **none verified**
- MSIX size / SHA-256: **UNKNOWN**
- Windows UI/functional QA: **NOT RUN**

## Remaining HOLD gates before code-owner upload handoff

1. Obtain and record the product-specific approved Store Version in `A.B.C.0` form.
2. Provide approved Store logo assets and verified resource languages.
3. On a real Windows x64 repository clone, run the common 10-command Git start gate and confirm clean local HEAD == `origin/codex/store-p0-web-evidence-20261023`.
4. Run existing unit/smoke tests and portable EXE build; record commands, exit codes, test counts and EXE SHA-256.
5. Run the existing unsigned MSIX builder and preserve package path, size, SHA-256, source commit and unpacked manifest evidence.
6. Run real Windows UI QA, including 1024x768 and DPI checks, with non-personal test data.
7. Only after those gates pass should the code owner prepare the Partner Center package-upload step. Upload/submission/publication remain outside this instruction.

## Code-owner start commands

```text
git rev-parse --show-toplevel
git config --get remote.origin.url
git fetch origin
git branch --show-current
git status --short
git rev-parse HEAD
git rev-parse "origin/codex/store-p0-web-evidence-20261023"
git log --oneline --decorate -8
git diff --name-status
git ls-files --others --exclude-standard
```

If the repository/remote/branch is wrong, the tree is dirty, or local/origin HEAD cannot be explained, stop without reset, discard or stash.
