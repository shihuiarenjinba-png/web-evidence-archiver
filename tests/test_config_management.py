import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import archiver as archiver_module
from app_v2 import build_managed_config, host_candidates, merge_preserved_config, normalize_urls
from archiver import WebEvidenceArchiver, load_config
from config_store import atomic_write_json, read_json_object


class WebConfigManagementTests(unittest.TestCase):
    def test_new_update_backup_and_save_as(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); first = root / "first.json"; second = root / "second.json"
            original = build_managed_config("https://example.com/", "example.com", str(root / "out"))
            atomic_write_json(first, original); before = first.read_bytes()
            changed = build_managed_config("https://example.com/\nhttps://example.com/about", "example.com", str(root / "out"))
            _, backup = atomic_write_json(first, changed, overwrite=True, backup=True)
            atomic_write_json(second, changed)
            self.assertEqual(backup.read_bytes(), before)
            self.assertEqual(len(read_json_object(first)["urls"]), 2)
            self.assertEqual(len(read_json_object(second)["urls"]), 2)

    def test_adding_url_does_not_erase_existing_urls(self):
        existing = ["https://example.com/", "https://example.com/pricing"]
        text = "\n".join(existing + ["https://example.com/support"])
        config = build_managed_config(text, "example.com", "output")
        self.assertEqual(config["urls"][:2], existing)
        self.assertEqual(len(config["urls"]), 3)

    def test_duplicate_url_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "重複"):
            normalize_urls("https://example.com/\nhttps://example.com/")

    def test_host_candidates_require_explicit_later_confirmation(self):
        candidates = host_candidates(["https://example.com/", "https://cdn.example.net/a.png"])
        self.assertEqual(candidates, ["cdn.example.net", "example.com"])

    def test_legacy_config_is_compatible(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); path = root / "legacy.json"
            path.write_text(json.dumps({
                "allow_hosts": ["example.com"], "urls": ["https://example.com/"],
                "output_dir": str(root / "out"), "timeout_seconds": 30,
            }), encoding="utf-8")
            self.assertEqual(load_config(path)["urls"], ["https://example.com/"])

    def test_edit_preserves_unknown_legacy_fields(self):
        base = build_managed_config("https://example.com/", "example.com", "out")
        base["vendor_extension"] = {"keep": True}
        edited = build_managed_config("https://example.com/\nhttps://example.com/about", "example.com", "out")
        merged = merge_preserved_config(base, edited)
        self.assertEqual(merged["vendor_extension"], {"keep": True})
        self.assertEqual(len(merged["urls"]), 2)

    def test_invalid_json_read_leaves_caller_state_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"; path.write_text("{", encoding="utf-8")
            editing = ["https://example.com/kept"]
            with self.assertRaises(json.JSONDecodeError): read_json_object(path)
            self.assertEqual(editing, ["https://example.com/kept"])

    def test_partial_capture_writes_manifest_and_is_not_complete(self):
        class Page:
            def route(self, *_args): pass
        class Context:
            def new_page(self): return Page()
            def close(self): pass
        class Browser:
            def new_context(self, **_kwargs): return Context()
            def close(self): pass
        class Chromium:
            def launch(self, **_kwargs): return Browser()
        class Playwright:
            chromium = Chromium()
        class Manager:
            def __enter__(self): return Playwright()
            def __exit__(self, *_args): return False

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); path = root / "config.json"
            path.write_text(json.dumps(build_managed_config(
                "https://example.com/\nhttps://example.com/fail", "example.com", str(root / "out")
            )), encoding="utf-8")
            worker = WebEvidenceArchiver(path)
            capture = {
                "folder": "001_example", "original_url": "https://example.com/",
                "http_status": 200, "files": {},
            }
            with patch.object(archiver_module, "sync_playwright", return_value=Manager()), patch.object(
                worker, "_capture_one", side_effect=[capture, RuntimeError("fixture")]
            ):
                output = worker.capture_all()
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(manifest["complete"]); self.assertEqual(len(manifest["captures"]), 1)
            self.assertEqual(len(manifest["errors"]), 1); self.assertEqual(worker.last_result["failed"], 1)

    def test_http_error_and_blocked_resource_are_not_complete(self):
        class Page:
            def route(self, *_args): pass
        class Context:
            def new_page(self): return Page()
            def close(self): pass
        class Browser:
            def new_context(self, **_kwargs): return Context()
            def close(self): pass
        class Chromium:
            def launch(self, **_kwargs): return Browser()
        class Playwright:
            chromium = Chromium()
        class Manager:
            def __enter__(self): return Playwright()
            def __exit__(self, *_args): return False

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); path = root / "config.json"
            path.write_text(json.dumps(build_managed_config(
                "https://example.com/missing", "example.com", str(root / "out")
            )), encoding="utf-8")
            worker = WebEvidenceArchiver(path)
            capture = {
                "folder": "001_missing", "original_url": "https://example.com/missing",
                "http_status": 404, "files": {},
            }
            with patch.object(archiver_module, "sync_playwright", return_value=Manager()), patch.object(
                worker, "_capture_one", return_value=capture
            ):
                worker._blocked_hosts = {"cdn.example.net": 2}
                output = worker.capture_all()
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(manifest["complete"])
            self.assertEqual(manifest["errors"][0]["error_category"], "HttpStatusError")
            self.assertEqual(manifest["blocked_resources"], {"cdn.example.net": 2})


if __name__ == "__main__":
    unittest.main()
