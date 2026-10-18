import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

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

    def test_safe_name(self):
        value = _safe_name("https://example.com/pricing/2026?q=x")
        self.assertTrue(value.startswith("example.com_pricing_2026"))
        self.assertNotIn("/", value)


if __name__ == "__main__":
    unittest.main()
