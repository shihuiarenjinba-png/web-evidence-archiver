# Market / OSS reference audit — 2026-11-20

Product: **Web Evidence Archiver**

## References reviewed
- ArchiveBox: stores web snapshots in multiple durable formats including HTML, PNG, PDF, JSON and WARC and records per-snapshot outputs.
  - https://github.com/ArchiveBox/ArchiveBox
- SingleFile: saves a faithful complete page as one self-contained HTML file.
  - https://github.com/gildas-lormeau/SingleFile

## Decisions for this product
- Keep the current small Windows-local scope instead of reproducing a self-hosted archive server.
- Preserve independent capture results: HTML/PDF/PNG/hash generation must not hide a partial failure.
- Keep a machine-readable manifest/hash record so an archived bundle can be checked later.
- Re-capture should be an explicit user action; do not silently replace previous evidence.
- Surface failures in plain language and preserve successfully produced evidence when truthful partial capture is supported.
- Treat this document as design evidence only; no third-party code was copied.

## Remaining release evidence
- Real Windows capture against representative static, JS-heavy and invalid/unreachable URLs.
- Output inspection for HTML/PNG/PDF/SHA and partial-failure behavior.
- Windows DPI/visual QA, exact Store version/assets, QA_UNSIGNED MSIX and manifest/hash evidence.
