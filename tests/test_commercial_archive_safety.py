import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from archiver import WebEvidenceArchiver, validate_url


class CommercialWebEvidenceSafetyTests(unittest.TestCase):
    def test_rejects_inline_web_credentials(self):
        for url in (
            "https://user:password@example.com/private",
            "https://example.com/record?api_key=plaintext",
            "https://example.com/record?access_token=abc",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url, ["example.com"])

    def test_offline_default_output_is_writable_user_location(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            config_file = home / "config.json"
            config_file.write_text(json.dumps({
                "urls": ["https://example.com/"],
                "allow_hosts": ["example.com"],
                "timeout_seconds": 10,
            }), encoding="utf-8")
            with patch("archiver.Path.home", return_value=home):
                tool = WebEvidenceArchiver(config_file)
            self.assertEqual(tool.output_dir, home / "WebEvidenceArchives")

    def test_allowlist_blocks_unexpected_hosts(self):
        with self.assertRaises(ValueError):
            validate_url("https://outside.invalid/test", ["example.com"])
        with self.assertRaises(ValueError):
            validate_url("file:///C:/secret", ["example.com"])


if __name__ == "__main__":
    unittest.main()
