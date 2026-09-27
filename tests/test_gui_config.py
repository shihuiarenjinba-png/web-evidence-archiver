from pathlib import Path
import tempfile
import unittest

from app import build_gui_config
from archiver import load_config


class GuiConfigTests(unittest.TestCase):
    def test_gui_config_supports_multiple_urls_and_hosts(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = build_gui_config(
                "https://example.com/\nhttps://www.example.com/pricing\n",
                "example.com, www.example.com",
                str(root / "output"),
            )
            self.assertEqual(len(config["urls"]), 2)
            path = root / "config.json"
            path.write_text(__import__("json").dumps(config), encoding="utf-8")
            self.assertEqual(load_config(path)["browser_channel"], "msedge")

    def test_gui_config_requires_explicit_allow_host(self) -> None:
        with self.assertRaises(ValueError):
            build_gui_config("https://example.com/", "", "output")
