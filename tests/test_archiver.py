import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import json
import tempfile
from pathlib import Path

from archiver import _safe_name, validate_url


class ArchiverTests(unittest.TestCase):
    def test_validate_url_requires_https_and_allowlist(self):
        validate_url("https://example.com/page", ["example.com"])
        with self.assertRaises(ValueError):
            validate_url("http://example.com/page", ["example.com"])
        with self.assertRaises(ValueError):
            validate_url("https://other.example/page", ["example.com"])

    def test_deny_credentials_private_and_secret_query(self):
        rejected = [
            "https://user:password@example.com/",
            "https://example.com/?token=abc",
            "https://example.com/?API_KEY=abc",
            "https://example.com:8443/",
            "https://example.com/#secret",
            "https://127.0.0.1/",
            "https://localhost/",
            "https://example.com\\\\malformed",
        ]
        for url in rejected:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url, ["example.com"])
        for host in ("localhost", "127.0.0.1", "x.local", "*.example.com"):
            with self.subTest(host=host), self.assertRaises(ValueError):
                validate_url("https://example.com/", [host])
        validate_url("https://example.com/?page=2", ["example.com"])

    def test_resource_route_uses_same_security_policy(self):
        from archiver import WebEvidenceArchiver
        runner = object.__new__(WebEvidenceArchiver)
        runner.allow_hosts = ["example.com"]
        for url in ("https://example.com/?api_key=hidden",
                    "https://other.example/resource.png", "http://example.com/data"):
            route = MagicMock()
            runner._route_guard(route, SimpleNamespace(url=url))
            route.abort.assert_called_once()
            route.continue_.assert_not_called()
        route = MagicMock()
        runner._route_guard(route, SimpleNamespace(url="https://example.com/image.png"))
        route.continue_.assert_called_once()

    def test_all_pages_receive_context_routing(self):
        from archiver import WebEvidenceArchiver
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            settings = base / "settings.json"
            settings.write_text(json.dumps({
                "allow_hosts": ["example.com"],
                "urls": ["https://example.com/"],
                "output_dir": str(base / "archive"),
            }), encoding="utf-8")
            archiver = WebEvidenceArchiver(settings)
            playwright = MagicMock()
            context = playwright.__enter__.return_value.chromium.launch.return_value.new_context.return_value
            with patch("archiver.sync_playwright", return_value=playwright), patch.object(
                archiver, "_capture_one", return_value={"original_url": "https://example.com/"}
            ):
                archiver.capture_all()
            context.route.assert_called_once_with("**/*", archiver._route_guard)
            context.new_page.return_value.route.assert_not_called()
            self.assertEqual(context.new_page.call_count, 1)

    def test_safe_name(self):
        value = _safe_name("https://example.com/pricing/2026?q=x")
        self.assertTrue(value.startswith("example.com_pricing_2026"))
        self.assertNotIn("/", value)


if __name__ == "__main__":
    unittest.main()
