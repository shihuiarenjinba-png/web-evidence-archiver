from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import shutil
import tempfile
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qsl

# PyInstaller extracts bundled Chromium under the frozen Playwright package.
# Never silently depend on the developer's global browser cache on buyer PCs.
if getattr(sys, "frozen", False):
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"

from playwright.sync_api import Request, Route, sync_playwright


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


_BLOCKED_QUERY_KEYS = {"token", "access_token", "api_key", "apikey", "key",
                       "password", "secret", "client_secret", "signature", "auth"}


def _allowed_hosts(hosts: list[str]) -> set[str]:
    if not isinstance(hosts, list) or not hosts:
        raise ValueError("At least one approved hostname is required.")
    result = set()
    for host in hosts:
        if not isinstance(host, str):
            raise ValueError("Approved hosts must be hostname strings")
        name = host.strip().lower().rstrip(".")
        if (not name or len(name) > 253 or name == "localhost"
                or name.endswith((".local", ".localhost", ".internal"))
                or not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", name)):
            raise ValueError("Approved host must be a public DNS hostname")
        try:
            ipaddress.ip_address(name)
        except ValueError:
            pass
        else:
            raise ValueError("IP addresses are not supported as approved hosts")
        result.add(name)
    return result


def validate_url(url: str, allow_hosts: list[str]) -> None:
    """Do not put credentials in archived URLs, screenshots, evidence or logs."""
    if not isinstance(url, str):
        raise ValueError("The URL must be a string")
    allowed = _allowed_hosts(allow_hosts)
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid HTTPS URL") from exc
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host or host not in allowed:
        raise ValueError("URL must use an explicitly approved HTTPS host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL credentials are not supported")
    if port not in (None, 443) or parsed.fragment:
        raise ValueError("Custom ports and URL fragments are not supported")
    if any(key.casefold() in _BLOCKED_QUERY_KEYS for key, _ in parse_qsl(parsed.query, keep_blank_values=True)):
        raise ValueError("Secret-bearing query parameters are not supported")


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
        self.output_dir = Path(self.config.get("output_dir", "web_evidence")).expanduser().resolve()
        self.timeout_ms = int(self.config.get("timeout_seconds", 30)) * 1000
        self.viewport = self.config.get("viewport", {"width": 1440, "height": 1000})

    def _route_guard(self, route: Route, request: Request) -> None:
        try:
            parsed = urlparse(request.url)
            # Non-network resources are handled by Chromium. HTTP(S) must pass
            # the same credential/allowlist rules as top-level navigation.
            if parsed.scheme in {"data", "blob", "about"}:
                route.continue_()
                return
            validate_url(request.url, self.allow_hosts)
        except (ValueError, TypeError):
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

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                try:
                    context = browser.new_context(
                        viewport={
                            "width": int(self.viewport.get("width", 1440)),
                            "height": int(self.viewport.get("height", 1000)),
                        },
                        service_workers="block",
                    )
                    try:
                        # Context routing also covers new pages and popups; page.route
                        # can miss popup's very first navigation request.
                        context.route("**/*", self._route_guard)
                        page = context.new_page()
                        for index, url in enumerate(self.urls, start=1):
                            try:
                                capture = self._capture_one(page, run_dir, index, url)
                                capture["capture_status"] = "captured"
                            except Exception as exc:
                                capture = {
                                    "capture_status": "failed",
                                    "original_url": url,
                                    "captured_at": datetime.now().astimezone().isoformat(),
                                    "error_type": type(exc).__name__,
                                    # Error messages from third-party pages may contain
                                    # tokens, URLs, filenames or personal data.
                                    "error": "Capture failed; review locally with approved test data.",
                                }
                            manifest["captures"].append(capture)
                    finally:
                        context.close()
                finally:
                    browser.close()
        except Exception as exc:
            manifest["fatal_error"] = {
                "type": type(exc).__name__, "message": "Capture could not start or complete.",
            }
            raise
        finally:
            captures = manifest["captures"]
            manifest["summary"] = {
                "requested": len(self.urls),
                "captured": sum(item.get("capture_status") == "captured" for item in captures),
                "failed": sum(item.get("capture_status") == "failed" for item in captures),
                "not_attempted": len(self.urls) - len(captures),
            }
            manifest_path = run_dir / "manifest.json"
            with manifest_path.open("x", encoding="utf-8") as fh:
                json.dump(manifest, fh, ensure_ascii=False, indent=2)
        return run_dir

    def _capture_one(self, page, run_dir: Path, index: int, url: str) -> dict:
        """Publish a capture only once HTML, PNG, PDF and hashes all succeed."""
        validate_url(url, self.allow_hosts)
        name = f"{index:03d}_{_safe_name(url)}"
        page_dir = run_dir / name
        temporary = Path(tempfile.mkdtemp(prefix='.pending_evidence_', dir=run_dir))
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            # An HTTP error page is not the requested evidence. Never publish
            # it as a successful capture, even when HTML/PDF were generated.
            if response is None or not (200 <= int(response.status) < 400):
                raise ValueError("Navigation did not return a successful HTTP response")
            page.wait_for_timeout(750)
            final_url = page.url
            validate_url(final_url, self.allow_hosts)

            html_path = temporary / "page.html"
            screenshot_path = temporary / "screenshot.png"
            pdf_path = temporary / "page.pdf"

            html_path.write_text(page.content(), encoding="utf-8")
            page.screenshot(path=str(screenshot_path), full_page=True)
            page.pdf(path=str(pdf_path), format="A4", print_background=True)

            for output in (html_path, screenshot_path, pdf_path):
                if not output.is_file() or output.stat().st_size == 0:
                    raise ValueError('Capture is incomplete: empty output')
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
            with (temporary / "metadata.json").open("x", encoding="utf-8") as fh:
                json.dump(metadata, fh, ensure_ascii=False, indent=2)
            # The completed directory appears atomically. A failed capture is
            # never published as a folder containing partial evidence.
            os.rename(temporary, page_dir)
            return {"folder": name, **metadata}
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description="Web Evidence Archiver")
    parser.add_argument("config")
    args = parser.parse_args()
    result = WebEvidenceArchiver(args.config).capture_all()
    print(result)
    # A partial archive remains available for review, but must never be a
    # successful unattended command or downstream pipeline result.
    summary = json.loads((result / "manifest.json").read_text(encoding="utf-8"))["summary"]
    return 1 if (summary["failed"] or summary["not_attempted"]
                 or summary["captured"] != summary["requested"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
