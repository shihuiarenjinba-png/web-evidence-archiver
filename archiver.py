from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Request, Route, sync_playwright


def runtime_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def configure_playwright_browser_path() -> Path | None:
    bundled = runtime_base_dir() / "browsers"
    if bundled.is_dir():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(bundled)
        return bundled
    return None


def browser_self_test() -> dict:
    bundled = configure_playwright_browser_path()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content("<html><body><h1>self-test</h1></body></html>")
            if page.locator("h1").inner_text() != "self-test":
                raise RuntimeError("Chromium self-test page did not render as expected.")
        finally:
            browser.close()
    return {"status": "pass", "bundled_browser": bool(bundled), "browser_folder_name": bundled.name if bundled else None}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_url(url: str, allow_hosts: list[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        raise ValueError("HTTPS URLのみ許可されています。")
    if not parsed.hostname:
        raise ValueError("URLにホスト名がありません。")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL内のユーザー名/パスワード指定は許可されていません。")
    allowed = {host.casefold().strip() for host in allow_hosts if host.strip()}
    if not allowed:
        raise ValueError("allow_hostsを1件以上指定してください。")
    if parsed.hostname.casefold() not in allowed:
        raise ValueError(f"allow_hosts外のホストです: {parsed.hostname}")


def _safe_name(text: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._")
    return (name or "page")[:90]


def _unique_run_dir(parent: Path) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = parent / f"web_evidence_{stamp}"
    count = 1
    while candidate.exists():
        candidate = parent / f"web_evidence_{stamp}_{count}"
        count += 1
    candidate.mkdir()
    return candidate


def _normalize_target(item: object) -> dict:
    if isinstance(item, str):
        return {"url": item.strip(), "name": "", "selector": "", "ignore_text_regexes": []}
    if isinstance(item, dict):
        return {
            "url": str(item.get("url", "")).strip(),
            "name": str(item.get("name", "")).strip(),
            "selector": str(item.get("selector", "")).strip(),
            "ignore_text_regexes": [str(v) for v in item.get("ignore_text_regexes", [])],
        }
    raise ValueError("urlsはURL文字列または設定objectで指定してください。")


def load_config(path: str | Path) -> dict:
    config = json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))
    allow_hosts = list(config.get("allow_hosts", []))
    targets = [_normalize_target(item) for item in config.get("urls", [])]
    targets = [t for t in targets if t["url"]]
    if not targets:
        raise ValueError("urlsを1件以上指定してください。")
    for target in targets:
        validate_url(target["url"], allow_hosts)
        for pattern in target["ignore_text_regexes"]:
            re.compile(pattern)
    timeout = int(config.get("timeout_seconds", 30))
    if timeout < 1 or timeout > 120:
        raise ValueError("timeout_secondsは1〜120秒で指定してください。")
    settle = int(config.get("settle_milliseconds", 750))
    if settle < 0 or settle > 15000:
        raise ValueError("settle_millisecondsは0〜15000で指定してください。")
    config["targets"] = targets
    config["max_diff_lines"] = max(50, min(int(config.get("max_diff_lines", 1500)), 10000))
    config["settle_milliseconds"] = settle
    return config


def normalize_visible_text(text: str, ignore_regexes: list[str]) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    for pattern in ignore_regexes:
        normalized = re.sub(pattern, "<IGNORED>", normalized, flags=re.MULTILINE)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in normalized.splitlines()]
    return "\n".join(line for line in lines if line)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _capture_map(run_dir: Path) -> dict[str, dict]:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        return {}
    manifest = _read_json(manifest_path)
    return {str(item.get("original_url", "")): item for item in manifest.get("captures", []) if item.get("original_url")}


def _latest_previous_run(output_dir: Path, current: Path) -> Path | None:
    candidates = []
    for path in output_dir.glob("web_evidence_*"):
        if path == current or not path.is_dir() or not (path / "manifest.json").exists():
            continue
        candidates.append(path)
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def _write_evidence_chain(current: Path, previous: Path | None) -> dict:
    manifest_path = current / "manifest.json"
    if not manifest_path.exists():
        raise ValueError("Current run has no manifest.json")
    previous_manifest_sha = None
    previous_entry_sha = None
    previous_run_name = None
    if previous is not None:
        prev_manifest = previous / "manifest.json"
        if prev_manifest.exists():
            previous_manifest_sha = sha256_file(prev_manifest)
            previous_run_name = previous.name
        prev_chain = previous / "evidence_chain.json"
        if prev_chain.exists():
            try:
                previous_entry_sha = _read_json(prev_chain).get("entry_sha256")
            except Exception:
                previous_entry_sha = None
    payload = {
        "format_version": 1,
        "run_name": current.name,
        "created_at": datetime.now().astimezone().isoformat(),
        "manifest_sha256": sha256_file(manifest_path),
        "previous_run_name": previous_run_name,
        "previous_manifest_sha256": previous_manifest_sha,
        "previous_entry_sha256": previous_entry_sha,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["entry_sha256"] = sha256_text(canonical)
    (current / "evidence_chain.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def verify_run_integrity(run_dir: str | Path) -> dict:
    run = Path(run_dir).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    checked = 0
    manifest_path = run / "manifest.json"
    if not manifest_path.exists():
        return {"status": "fail", "checked": 0, "errors": ["missing:manifest.json"], "warnings": []}
    manifest = _read_json(manifest_path)
    for capture in manifest.get("captures", []):
        folder = run / str(capture.get("folder", ""))
        for label, item in (capture.get("files") or {}).items():
            rel = item.get("path")
            expected = item.get("sha256")
            if not rel or not expected:
                errors.append(f"invalid_manifest:{capture.get('folder')}:{label}")
                continue
            path = folder / rel
            if not path.exists():
                errors.append(f"missing:{capture.get('folder')}/{rel}")
                continue
            checked += 1
            if sha256_file(path) != expected:
                errors.append(f"hash_mismatch:{capture.get('folder')}/{rel}")
        metadata_file = capture.get("metadata_file")
        if metadata_file:
            metadata_path = folder / str(metadata_file.get("path", "metadata.json"))
            expected = metadata_file.get("sha256")
            if not metadata_path.exists():
                errors.append(f"missing:{capture.get('folder')}/metadata.json")
            elif expected:
                checked += 1
                if sha256_file(metadata_path) != expected:
                    errors.append(f"hash_mismatch:{capture.get('folder')}/metadata.json")

    chain_path = run / "evidence_chain.json"
    if chain_path.exists():
        chain = _read_json(chain_path)
        if chain.get("manifest_sha256") != sha256_file(manifest_path):
            errors.append("chain_manifest_hash_mismatch")
        entry_hash = chain.get("entry_sha256")
        base = {k: v for k, v in chain.items() if k != "entry_sha256"}
        canonical = json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if entry_hash != sha256_text(canonical):
            errors.append("chain_entry_hash_mismatch")

        previous_name = chain.get("previous_run_name")
        if previous_name:
            previous = run.parent / str(previous_name)
            if not previous.is_dir():
                warnings.append("previous_run_not_available_for_chain_verification")
            else:
                prev_manifest = previous / "manifest.json"
                if not prev_manifest.exists():
                    errors.append("previous_manifest_missing")
                elif chain.get("previous_manifest_sha256") != sha256_file(prev_manifest):
                    errors.append("previous_manifest_hash_mismatch")
                expected_prev_entry = chain.get("previous_entry_sha256")
                if expected_prev_entry:
                    prev_chain = previous / "evidence_chain.json"
                    if not prev_chain.exists():
                        errors.append("previous_chain_missing")
                    elif _read_json(prev_chain).get("entry_sha256") != expected_prev_entry:
                        errors.append("previous_chain_entry_mismatch")
    else:
        warnings.append("evidence_chain_missing")
    return {"status": "pass" if not errors else "fail", "checked": checked, "errors": errors, "warnings": warnings}


def compare_runs(previous_dir: str | Path, current_dir: str | Path, *, max_diff_lines: int = 1500) -> dict:
    previous = Path(previous_dir).resolve()
    current = Path(current_dir).resolve()
    before_map = _capture_map(previous)
    after_map = _capture_map(current)
    rows = []
    for url in sorted(set(before_map) | set(after_map)):
        before = before_map.get(url)
        after = after_map.get(url)
        if before is None:
            rows.append({"url": url, "status": "added_target", "changed": True})
            continue
        if after is None:
            rows.append({"url": url, "status": "removed_target", "changed": True})
            continue
        before_folder = previous / before["folder"]
        after_folder = current / after["folder"]
        before_text_path = before_folder / "normalized_text.txt"
        after_text_path = after_folder / "normalized_text.txt"
        before_text = before_text_path.read_text(encoding="utf-8", errors="replace") if before_text_path.exists() else ""
        after_text = after_text_path.read_text(encoding="utf-8", errors="replace") if after_text_path.exists() else ""
        diff_lines = list(difflib.unified_diff(before_text.splitlines(), after_text.splitlines(), fromfile="before", tofile="after", lineterm=""))
        truncated = len(diff_lines) > max_diff_lines
        kept_diff = diff_lines[:max_diff_lines]
        added_lines = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        removed_lines = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
        before_files = before.get("files", {})
        after_files = after.get("files", {})
        text_changed = before_files.get("normalized_text", {}).get("sha256") != after_files.get("normalized_text", {}).get("sha256")
        html_changed = before_files.get("html", {}).get("sha256") != after_files.get("html", {}).get("sha256")
        screenshot_changed = before_files.get("screenshot", {}).get("sha256") != after_files.get("screenshot", {}).get("sha256")
        if text_changed:
            status = "content_changed"
        elif screenshot_changed:
            status = "render_changed"
        elif html_changed:
            status = "html_only_changed"
        else:
            status = "unchanged"
        diff_name = _safe_name(after.get("target_name") or url) + ".diff.txt"
        diff_path = current / "diffs" / diff_name
        if text_changed:
            diff_path.parent.mkdir(exist_ok=True)
            diff_path.write_text("\n".join(kept_diff) + ("\n... DIFF TRUNCATED ...\n" if truncated else "\n"), encoding="utf-8")
        rows.append({
            "url": url,
            "target_name": after.get("target_name", ""),
            "status": status,
            "changed": status != "unchanged",
            "text_changed": text_changed,
            "html_changed": html_changed,
            "screenshot_changed": screenshot_changed,
            "added_text_lines": added_lines,
            "removed_text_lines": removed_lines,
            "diff_file": str(diff_path.relative_to(current)) if text_changed else None,
            "diff_truncated": truncated,
            "before_capture": before["folder"],
            "after_capture": after["folder"],
        })
    report = {
        "compared_at": datetime.now().astimezone().isoformat(),
        "previous_run": previous.name,
        "current_run": current.name,
        "changed_targets": sum(bool(row.get("changed")) for row in rows),
        "total_targets": len(rows),
        "targets": rows,
        "notice": "Differences are technical evidence snapshots, not a guarantee of legal evidentiary status or semantic importance.",
    }
    (current / "change_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown_change_report(current / "change_report.md", report)
    return report


def _markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _write_markdown_change_report(path: Path, report: dict) -> None:
    lines = [
        "# Web Change Evidence Report", "",
        f"Compared: `{report['previous_run']}` → `{report['current_run']}`",
        f"Changed targets: **{report['changed_targets']} / {report['total_targets']}**", "",
        "| Target | Status | Text +/- | Screenshot | HTML |",
        "|---|---|---:|---|---|",
    ]
    for item in report["targets"]:
        label = _markdown_cell(item.get("target_name") or item.get("url"))
        delta = f"+{item.get('added_text_lines', 0)} / -{item.get('removed_text_lines', 0)}"
        lines.append(f"| {label} | {item.get('status')} | {delta} | {item.get('screenshot_changed', '')} | {item.get('html_changed', '')} |")
    lines.extend(["", "> 本レポートは技術的な取得・差分記録であり、法的証拠能力や変更の重要性を保証するものではありません。", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


class WebEvidenceArchiver:
    def __init__(self, config_path: str | Path):
        self.config = load_config(config_path)
        self.allow_hosts = list(self.config["allow_hosts"])
        self.targets = list(self.config["targets"])
        self.output_dir = Path(self.config.get("output_dir", "web_evidence")).expanduser().resolve()
        self.timeout_ms = int(self.config.get("timeout_seconds", 30)) * 1000
        self.viewport = self.config.get("viewport", {"width": 1440, "height": 1000})

    def _route_guard(self, route: Route, request: Request) -> None:
        parsed = urlparse(request.url)
        if parsed.scheme in {"data", "blob", "about"}:
            route.continue_()
            return
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            route.abort()
            return
        allowed = {host.casefold().strip() for host in self.allow_hosts if host.strip()}
        if parsed.hostname.casefold() not in allowed:
            route.abort()
            return
        route.continue_()

    def capture_all(self, *, compare_previous: bool = True) -> Path:
        configure_playwright_browser_path()
        run_dir = _unique_run_dir(self.output_dir)
        previous = _latest_previous_run(self.output_dir, run_dir)
        manifest = {"format_version": 3, "created_at": datetime.now().astimezone().isoformat(), "allow_hosts": self.allow_hosts, "captures": []}
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": int(self.viewport.get("width", 1440)), "height": int(self.viewport.get("height", 1000))})
                page = context.new_page()
                page.route("**/*", self._route_guard)
                try:
                    for index, target in enumerate(self.targets, start=1):
                        manifest["captures"].append(self._capture_one(page, run_dir, index, target))
                finally:
                    context.close()
                    browser.close()
        except Exception as exc:
            (run_dir / "capture_error.json").write_text(json.dumps({"failed_at": datetime.now().astimezone().isoformat(), "error_type": exc.__class__.__name__, "message": str(exc)}, ensure_ascii=False, indent=2), encoding="utf-8")
            raise
        manifest_path = run_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "manifest.json.sha256").write_text(f"{sha256_file(manifest_path)}  manifest.json\n", encoding="utf-8")
        _write_evidence_chain(run_dir, previous)
        verification = verify_run_integrity(run_dir)
        (run_dir / "verification.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8")
        if verification["status"] != "pass":
            raise RuntimeError(f"Evidence verification failed: {verification['errors']}")
        if compare_previous and previous is not None:
            compare_runs(previous, run_dir, max_diff_lines=int(self.config["max_diff_lines"]))
        return run_dir

    def _capture_one(self, page, run_dir: Path, index: int, target: dict) -> dict:
        url = target["url"]
        validate_url(url, self.allow_hosts)
        parsed = urlparse(url)
        label = target.get("name") or f"{parsed.hostname}_{parsed.path.strip('/') or 'home'}"
        folder_name = f"{index:03d}_{_safe_name(label)}"
        page_dir = run_dir / folder_name
        page_dir.mkdir()
        response = page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        page.wait_for_timeout(int(self.config.get("settle_milliseconds", 750)))
        final_url = page.url
        validate_url(final_url, self.allow_hosts)
        html_path = page_dir / "page.html"
        screenshot_path = page_dir / "screenshot.png"
        pdf_path = page_dir / "page.pdf"
        text_path = page_dir / "visible_text.txt"
        normalized_path = page_dir / "normalized_text.txt"
        html_path.write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(screenshot_path), full_page=True)
        page.pdf(path=str(pdf_path), format="A4", print_background=True)
        selector = target.get("selector", "")
        try:
            visible_text = page.locator(selector).inner_text(timeout=3000) if selector else page.locator("body").inner_text(timeout=3000)
        except Exception:
            visible_text = page.locator("body").inner_text(timeout=3000)
        normalized_text = normalize_visible_text(visible_text, target.get("ignore_text_regexes", []))
        text_path.write_text(visible_text, encoding="utf-8")
        normalized_path.write_text(normalized_text, encoding="utf-8")
        metadata = {
            "folder": folder_name,
            "target_name": target.get("name", ""),
            "selector": selector,
            "ignore_text_regexes": target.get("ignore_text_regexes", []),
            "original_url": url,
            "final_url": final_url,
            "title": page.title(),
            "http_status": response.status if response is not None else None,
            "captured_at": datetime.now().astimezone().isoformat(),
            "files": {
                "html": {"path": "page.html", "sha256": sha256_file(html_path)},
                "screenshot": {"path": "screenshot.png", "sha256": sha256_file(screenshot_path)},
                "pdf": {"path": "page.pdf", "sha256": sha256_file(pdf_path)},
                "visible_text": {"path": "visible_text.txt", "sha256": sha256_file(text_path)},
                "normalized_text": {"path": "normalized_text.txt", "sha256": sha256_file(normalized_path)},
            },
        }
        metadata_path = page_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest_entry = dict(metadata)
        manifest_entry["metadata_file"] = {"path": "metadata.json", "sha256": sha256_file(metadata_path)}
        return manifest_entry


def main() -> None:
    parser = argparse.ArgumentParser(description="Web Change Evidence Monitor")
    parser.add_argument("config", nargs="?")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--verify-run")
    parser.add_argument("--no-compare", action="store_true")
    parser.add_argument("--compare", nargs=2, metavar=("PREVIOUS_RUN", "CURRENT_RUN"))
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(browser_self_test(), ensure_ascii=False, indent=2)); return
    if args.verify_run:
        print(json.dumps(verify_run_integrity(args.verify_run), ensure_ascii=False, indent=2)); return
    if args.compare:
        print(json.dumps(compare_runs(args.compare[0], args.compare[1]), ensure_ascii=False, indent=2)); return
    if not args.config:
        parser.error("config is required unless --self-test, --verify-run, or --compare is used")
    print(WebEvidenceArchiver(args.config).capture_all(compare_previous=not args.no_compare))


if __name__ == "__main__":
    main()
