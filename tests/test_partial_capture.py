"""An incomplete capture must never be reported as a complete archive."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from archiver import WebEvidenceArchiver


class CommercialArchiveAcceptanceTests(unittest.TestCase):
    def _create(self, folder: Path) -> WebEvidenceArchiver:
        config = folder / "config.json"
        config.write_text(json.dumps({
            "urls": ["https://example.com/first", "https://example.com/second"],
            "allow_hosts": ["example.com"],
            "output_dir": str(folder / "evidence"),
        }), encoding="utf-8")
        return WebEvidenceArchiver(config)

    @patch("archiver.sync_playwright")
    def test_failed_page_is_explicit_and_other_page_continues(self, playwright):
        playwright.return_value.__enter__.return_value.chromium.launch.return_value = Mock()
        with tempfile.TemporaryDirectory() as folder:
            archive = self._create(Path(folder))
            archive._capture_one = Mock(side_effect=[
                RuntimeError("Navigation failed"),
                {"original_url": archive.urls[1], "files": {}, "http_status": 200},
            ])
            out = archive.capture_all()
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["summary"],
                {"requested": 2, "captured": 1, "failed": 1, "not_attempted": 0})
            self.assertEqual(manifest["captures"][0]["capture_status"], "failed")
            self.assertEqual(manifest["captures"][1]["capture_status"], "captured")

    @patch("archiver.sync_playwright")
    def test_browser_start_failure_writes_fatal_manifest(self, playwright):
        playwright.return_value.__enter__.return_value.chromium.launch.side_effect = OSError("browser missing")
        with tempfile.TemporaryDirectory() as folder:
            archive = self._create(Path(folder))
            with self.assertRaises(OSError):
                archive.capture_all()
            archives = list((Path(folder) / "evidence").glob("web_evidence_*"))
            self.assertEqual(len(archives), 1)
            manifest = json.loads((archives[0] / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["fatal_error"]["type"], "OSError")
            self.assertEqual(manifest["summary"]["not_attempted"], 2)


if __name__ == "__main__":
    unittest.main()
