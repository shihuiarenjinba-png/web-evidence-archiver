from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

from playwright.sync_api import Request, Route, sync_playwright


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_url(url: str, allow_hosts: list[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        raise ValueError("HTTPS URLのみ許可されています。")
    if not parsed.hostname:
        raise ValueError("URLにホスト名がありません。")
    if parsed.username or parsed.password:
        raise ValueError("ユーザー名・パスワードをURLへ埋め込むことはできません。")
    for key, _value in parse_qsl(parsed.query, keep_blank_values=True):
        if any(term in key.casefold() for term in ("token", "secret", "password", "api_key", "credential")):
            raise ValueError("URLのクエリに認証情報を含めないでください。")

    allowed = {host.casefold().strip() for host in allow_hosts if host.strip()}
    if not allowed:
        raise ValueError("allow_hostsを1件以上指定してください。")
    if parsed.hostname.casefold() not in allowed:
        raise ValueError(f"allow_hosts外のホストです: {parsed.hostname}")


def _safe_name(url: str) -> str:
    parsed = urlparse(url)
    raw = f"{parsed.hostname or 'page'}_{parsed.path.strip('/') or 'home'}"
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._")
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


def load_config(path: str | Path) -> dict:
    config = json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))
    allow_hosts = list(config.get("allow_hosts", []))
    urls = [str(url).strip() for url in config.get("urls", []) if str(url).strip()]
    if not urls:
        raise ValueError("urlsを1件以上指定してください。")
    for url in urls:
        validate_url(url, allow_hosts)
    timeout = int(config.get("timeout_seconds", 30))
    if timeout < 1 or timeout > 120:
        raise ValueError("timeout_secondsは1〜120秒で指定してください。")
    return config


class WebEvidenceArchiver:
    def __init__(self, config_path: str | Path):
        self.config = load_config(config_path)
        self.allow_hosts = list(self.config["allow_hosts"])
        self.urls = list(self.config["urls"])
        default_parent = Path.home() / "Documents"
        if not default_parent.is_dir():
            default_parent = Path.home()
        self.output_dir = Path(
            self.config.get("output_dir", str(default_parent / "WebEvidenceArchives"))
        ).expanduser().resolve()
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

    def capture_all(self) -> Path:
        run_dir = _unique_run_dir(self.output_dir)
        manifest = {
            "created_at": datetime.now().astimezone().isoformat(),
            "allow_hosts": self.allow_hosts,
            "captures": [],
        }

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={
                    "width": int(self.viewport.get("width", 1440)),
                    "height": int(self.viewport.get("height", 1000)),
                }
            )
            page = context.new_page()
            page.route("**/*", self._route_guard)

            try:
                for index, url in enumerate(self.urls, start=1):
                    capture = self._capture_one(page, run_dir, index, url)
                    manifest["captures"].append(capture)
            finally:
                context.close()
                browser.close()

        manifest_path = run_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return run_dir

    def _capture_one(self, page, run_dir: Path, index: int, url: str) -> dict:
        validate_url(url, self.allow_hosts)
        name = f"{index:03d}_{_safe_name(url)}"
        page_dir = run_dir / name
        page_dir.mkdir()

        response = page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        page.wait_for_timeout(750)
        final_url = page.url
        validate_url(final_url, self.allow_hosts)

        html_path = page_dir / "page.html"
        screenshot_path = page_dir / "screenshot.png"
        pdf_path = page_dir / "page.pdf"

        html_path.write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(screenshot_path), full_page=True)
        page.pdf(path=str(pdf_path), format="A4", print_background=True)

        title = page.title()
        captured_at = datetime.now().astimezone().isoformat()
        status = response.status if response is not None else None

        metadata = {
            "original_url": url,
            "final_url": final_url,
            "title": title,
            "http_status": status,
            "captured_at": captured_at,
            "files": {
                "html": {"path": "page.html", "sha256": sha256_file(html_path)},
                "screenshot": {"path": "screenshot.png", "sha256": sha256_file(screenshot_path)},
                "pdf": {"path": "page.pdf", "sha256": sha256_file(pdf_path)},
            },
        }
        (page_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {"folder": name, **metadata}


def main() -> None:
    parser = argparse.ArgumentParser(description="Web Evidence Archiver")
    parser.add_argument("config")
    args = parser.parse_args()
    result = WebEvidenceArchiver(args.config).capture_all()
    print(result)


if __name__ == "__main__":
    main()
