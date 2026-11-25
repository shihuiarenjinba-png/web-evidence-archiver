import json
import hashlib
import tempfile
import unittest
import base64
from pathlib import Path

from archiver import load_capture_summary


class CaptureSummaryTests(unittest.TestCase):
    @staticmethod
    def write_capture(root: Path, *, tamper_sha: bool = False) -> Path:
        page = root / "001_example.com_home"
        page.mkdir()
        payloads = {
            "html": ("page.html", b"<!doctype html><title>Example</title>"),
            "screenshot": ("screenshot.png", base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/7uoAAAAASUVORK5CYII=")),
            "pdf": ("page.pdf", b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n"),
        }
        entries = {}
        for kind, (filename, payload) in payloads.items():
            (page / filename).write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            entries[kind] = {"path": filename, "sha256": ("0" * 64 if tamper_sha and kind == "html" else digest)}
        (page / "metadata.json").write_text(json.dumps({"title": "Example"}), encoding="utf-8")
        (root / "manifest.json").write_text(json.dumps({"captures": [{"folder": page.name, "files": entries}]}), encoding="utf-8")
        return page

    def test_loads_completed_capture_and_validates_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = self.write_capture(root)

            result = load_capture_summary(root)

            self.assertEqual(len(result["captures"]), 1)
            self.assertEqual(len(result["files"]), 4)
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
            (page / "screenshot.png").write_bytes(b"png")
            (page / "page.pdf").write_bytes(b"pdf")
            (root / "manifest.json").write_text(
                json.dumps({
                    "captures": [{
                        "folder": page.name,
                        "files": {
                            "html": {"path": "page.html", "sha256": "0" * 64},
                            "screenshot": {"path": "screenshot.png", "sha256": hashlib.sha256(b"png").hexdigest()},
                            "pdf": {"path": "page.pdf", "sha256": hashlib.sha256(b"pdf").hexdigest()},
                        },
                    }]
                }),
                encoding="utf-8",
            )
            with self.assertRaises(FileNotFoundError):
                load_capture_summary(root)

    def test_artifact_sha_mismatch_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_capture(root, tamper_sha=True)
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                load_capture_summary(root)

    def test_empty_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = self.write_capture(root)
            (page / "page.html").write_bytes(b"")
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            manifest["captures"][0]["files"]["html"]["sha256"] = hashlib.sha256(b"").hexdigest()
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "empty"):
                load_capture_summary(root)

    def test_missing_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = self.write_capture(root)
            (page / "metadata.json").unlink()
            with self.assertRaisesRegex(FileNotFoundError, "metadata"):
                load_capture_summary(root)

    def test_manifest_cannot_reference_paths_outside_output_folder(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "manifest.json").write_text(
                json.dumps({
                    "captures": [{
                        "folder": "..",
                        "files": {
                            "html": {"path": "outside.html", "sha256": "0" * 64},
                            "screenshot": {"path": "outside.png", "sha256": "0" * 64},
                            "pdf": {"path": "outside.pdf", "sha256": "0" * 64},
                        },
                    }]
                }),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "outside"):
                load_capture_summary(root)


if __name__ == "__main__":
    unittest.main()
