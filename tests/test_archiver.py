import unittest

from archiver import _safe_name, validate_url


class ArchiverTests(unittest.TestCase):
    def test_validate_url_requires_https_and_allowlist(self):
        validate_url("https://example.com/page", ["example.com"])
        with self.assertRaises(ValueError):
            validate_url("http://example.com/page", ["example.com"])
        with self.assertRaises(ValueError):
            validate_url("https://other.example/page", ["example.com"])

    def test_safe_name(self):
        value = _safe_name("https://example.com/pricing/2026?q=x")
        self.assertTrue(value.startswith("example.com_pricing_2026"))
        self.assertNotIn("/", value)


if __name__ == "__main__":
    unittest.main()
