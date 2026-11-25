import json
import tempfile
import unittest
from pathlib import Path

from app import parse_args
from archiver import WebEvidenceArchiver, load_config


ROOT = Path(__file__).resolve().parents[1]


class LauncherAndConfigTests(unittest.TestCase):
    def test_config_can_be_supplied_at_launch(self):
        args = parse_args(["--config", "config.example.json"])
        self.assertEqual(args.config, "config.example.json")

    def test_scripts_resolve_paths_from_their_own_location(self):
        for name in ("setup.ps1", "run.ps1", "doctor.ps1"):
            source = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("$PSScriptRoot", source, name)
            self.assertNotIn("Set-ExecutionPolicy", source, name)
        setup = (ROOT / "setup.ps1").read_text(encoding="utf-8")
        self.assertLess(setup.index("foreach ($minor in @(13, 12))"), setup.index("if ($AllowExperimentalPython314)"))

    def test_config_rejects_http_url(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "bad.json"
            config.write_text(json.dumps({"allow_hosts": ["example.com"], "urls": ["http://example.com/"]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                load_config(config)

    def test_relative_output_directory_is_anchored_to_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config.json"
            config.write_text(json.dumps({
                "allow_hosts": ["example.com"],
                "urls": ["https://example.com/"],
                "output_dir": "relative-captures",
            }), encoding="utf-8")
            archiver = WebEvidenceArchiver(config)
            self.assertEqual(archiver.output_dir, (root / "relative-captures").resolve())


if __name__ == "__main__":
    unittest.main()
