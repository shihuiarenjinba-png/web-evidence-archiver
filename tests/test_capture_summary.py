import json
import tempfile
import unittest
from pathlib import Path

from archiver import load_capture_summary


class CaptureSummaryTests(unittest.TestCase):
    def test_loads_completed_capture_and_validates_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = root / "001_example.com_home"
            page.mkdir()
            for filename in ("page.html", "screenshot.png", "page.pdf"):
                (page / filename).write_bytes(b"synthetic artifact")
            manifest = {
                "captures": [
                    {
                        "folder": page.name,
                        "files": {
                            "html": {"path": "page.html"},
                            "screenshot": {"path": "screenshot.png"},
                            "pdf": {"path": "page.pdf"},
                        },
                    }
                ]
            }
            (root / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )

            result = load_capture_summary(root)

            self.assertEqual(len(result["captures"]), 1)
            self.assertEqual(len(result["files"]), 3)
            self.assertFalse(result["cancelled"])
            self.assertEqual(Path(result["manifest_path"]), (root / "manifest.json").resolve())

    def test_preserves_cancelled_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "manifest.json").write_text(
                json.dumps({"captures": [], "cancelled": True}),
                encoding="utf-8",
            )

            result = load_capture_summary(root)

            self.assertTrue(result["cancelled"])
            self.assertEqual(result["captures"], [])
            self.assertEqual(result["files"], [])

    def test_missing_manifest_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(FileNotFoundError):
                load_capture_summary(temporary)

    def test_malformed_manifest_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            (Path(temporary) / "manifest.json").write_text(
                "{not-json", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "manifest"):
                load_capture_summary(temporary)

    def test_missing_artifact_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = root / "001_example"
            page.mkdir()
            (root / "manifest.json").write_text(
                json.dumps({
                    "captures": [{
                        "folder": page.name,
                        "files": {"html": {"path": "page.html"}},
                    }]
                }),
                encoding="utf-8",
            )
            with self.assertRaises(FileNotFoundError):
                load_capture_summary(root)

    def test_manifest_cannot_reference_paths_outside_output_folder(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "manifest.json").write_text(
                json.dumps({
                    "captures": [{
                        "folder": "..",
                        "files": {"outside": {"path": "outside.txt"}},
                    }]
                }),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "outside"):
                load_capture_summary(root)


if __name__ == "__main__":
    unittest.main()
