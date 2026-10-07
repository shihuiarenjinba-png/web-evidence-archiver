"""No-network validation of first-run Web archiver settings."""
import json
import tempfile
import unittest
from pathlib import Path

from app import EXAMPLE_URL, EXAMPLE_HOST, build_gui_config, validate_application_config


class FirstUseTests(unittest.TestCase):
    def test_public_page_preset(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = build_gui_config(EXAMPLE_URL, EXAMPLE_HOST, str(root))
            self.assertEqual(config["urls"], [EXAMPLE_URL])
            self.assertEqual(config["allow_hosts"], [EXAMPLE_HOST])
            path = root / "archiver.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            validate_application_config(str(path))

    def test_arbitrary_json_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "page.json"
            path.write_text(json.dumps({"title": "Example Domain"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "設定"):
                validate_application_config(str(path))

    def test_empty_config_and_host_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "設定JSON"):
                validate_application_config("")
            with self.assertRaisesRegex(ValueError, "allow_hosts"):
                build_gui_config(EXAMPLE_URL, "example.net", folder)


if __name__ == "__main__":
    unittest.main()
