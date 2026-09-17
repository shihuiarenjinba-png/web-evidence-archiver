from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from archiver import (
    _write_evidence_chain,
    compare_runs,
    normalize_visible_text,
    validate_url,
    verify_run_integrity,
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_run(root: Path, name: str, text: str, *, html_hash: str | None = None, screenshot_hash: str | None = None) -> Path:
    run = root / name
    folder = run / "001_Test"
    folder.mkdir(parents=True)
    files = {
        "page.html": "<html>test</html>",
        "screenshot.png": "fake-image",
        "page.pdf": "fake-pdf",
        "visible_text.txt": text,
        "normalized_text.txt": text,
    }
    for filename, content in files.items():
        (folder / filename).write_text(content, encoding="utf-8")
    capture = {
        "folder": "001_Test",
        "target_name": "Test",
        "original_url": "https://example.com/page",
        "files": {
            "normalized_text": {"path": "normalized_text.txt", "sha256": _sha(text)},
            "visible_text": {"path": "visible_text.txt", "sha256": _sha(text)},
            "html": {"path": "page.html", "sha256": html_hash or _sha(files["page.html"])},
            "screenshot": {"path": "screenshot.png", "sha256": screenshot_hash or _sha(files["screenshot.png"])},
            "pdf": {"path": "page.pdf", "sha256": _sha(files["page.pdf"])},
        },
    }
    (run / "manifest.json").write_text(json.dumps({"captures": [capture]}), encoding="utf-8")
    return run


class ArchiverTests(unittest.TestCase):
    def test_https_allowlist_and_embedded_credentials(self) -> None:
        validate_url("https://example.com/page", ["example.com"])
        with self.assertRaises(ValueError):
            validate_url("http://example.com/page", ["example.com"])
        with self.assertRaises(ValueError):
            validate_url("https://other.example/page", ["example.com"])
        with self.assertRaises(ValueError):
            validate_url("https://user:pass@example.com/page", ["example.com"])

    def test_normalize_visible_text_ignores_volatile_value(self) -> None:
        first = normalize_visible_text("Price 100\nLast updated: 10:01:02", [r"Last updated:.*$"])
        second = normalize_visible_text("Price 100\nLast updated: 10:02:03", [r"Last updated:.*$"])
        self.assertEqual(first, second)

    def test_compare_runs_detects_content_change_and_omits_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = _make_run(root, "web_evidence_1", "Price 100\nPlan A")
            after = _make_run(root, "web_evidence_2", "Price 120\nPlan A")
            report = compare_runs(before, after)
            self.assertEqual(report["changed_targets"], 1)
            item = report["targets"][0]
            self.assertEqual(item["status"], "content_changed")
            self.assertGreater(item["added_text_lines"], 0)
            self.assertEqual(report["previous_run"], "web_evidence_1")
            self.assertEqual(item["before_capture"], "001_Test")
            self.assertNotIn(str(root), json.dumps(report))
            self.assertTrue((after / item["diff_file"]).exists())

    def test_compare_runs_separates_render_only_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = _make_run(root, "web_evidence_1", "Same", screenshot_hash="a")
            after = _make_run(root, "web_evidence_2", "Same", screenshot_hash="b")
            report = compare_runs(before, after)
            self.assertEqual(report["targets"][0]["status"], "render_changed")

    def test_evidence_chain_links_previous_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = _make_run(root, "web_evidence_1", "A")
            first_chain = _write_evidence_chain(first, None)
            second = _make_run(root, "web_evidence_2", "B")
            second_chain = _write_evidence_chain(second, first)
            self.assertEqual(second_chain["previous_run_name"], "web_evidence_1")
            self.assertEqual(second_chain["previous_manifest_sha256"], hashlib.sha256((first / "manifest.json").read_bytes()).hexdigest())
            self.assertEqual(second_chain["previous_entry_sha256"], first_chain["entry_sha256"])

    def test_verify_run_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = _make_run(root, "web_evidence_1", "Original")
            _write_evidence_chain(run, None)
            self.assertEqual(verify_run_integrity(run)["status"], "pass")
            (run / "001_Test" / "normalized_text.txt").write_text("Tampered", encoding="utf-8")
            result = verify_run_integrity(run)
            self.assertEqual(result["status"], "fail")
            self.assertTrue(any(x.startswith("hash_mismatch:") for x in result["errors"]))


if __name__ == "__main__":
    unittest.main()
