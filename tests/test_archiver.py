from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from archiver import compare_runs, normalize_visible_text, validate_url


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_run(root: Path, name: str, text: str, *, html_hash: str = "h", screenshot_hash: str = "s") -> Path:
    run = root / name
    folder = run / "001_Test"
    folder.mkdir(parents=True)
    (folder / "normalized_text.txt").write_text(text, encoding="utf-8")
    capture = {
        "folder": "001_Test",
        "target_name": "Test",
        "original_url": "https://example.com/page",
        "files": {
            "normalized_text": {"sha256": _sha(text)},
            "html": {"sha256": html_hash},
            "screenshot": {"sha256": screenshot_hash},
        },
    }
    (run / "manifest.json").write_text(json.dumps({"captures": [capture]}), encoding="utf-8")
    return run


class ArchiverTests(unittest.TestCase):
    def test_https_allowlist(self) -> None:
        validate_url("https://example.com/page", ["example.com"])
        with self.assertRaises(ValueError):
            validate_url("http://example.com/page", ["example.com"])
        with self.assertRaises(ValueError):
            validate_url("https://other.example/page", ["example.com"])

    def test_normalize_visible_text_ignores_volatile_value(self) -> None:
        first = normalize_visible_text("Price 100\nLast updated: 10:01:02", [r"Last updated:.*$"])
        second = normalize_visible_text("Price 100\nLast updated: 10:02:03", [r"Last updated:.*$"])
        self.assertEqual(first, second)

    def test_compare_runs_detects_content_change_and_writes_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = _make_run(root, "web_evidence_1", "Price 100\nPlan A")
            after = _make_run(root, "web_evidence_2", "Price 120\nPlan A")
            report = compare_runs(before, after)
            self.assertEqual(report["changed_targets"], 1)
            item = report["targets"][0]
            self.assertEqual(item["status"], "content_changed")
            self.assertGreater(item["added_text_lines"], 0)
            self.assertTrue((after / "change_report.json").exists())
            self.assertTrue((after / item["diff_file"]).exists())

    def test_compare_runs_separates_render_only_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = _make_run(root, "web_evidence_1", "Same", screenshot_hash="a")
            after = _make_run(root, "web_evidence_2", "Same", screenshot_hash="b")
            report = compare_runs(before, after)
            self.assertEqual(report["targets"][0]["status"], "render_changed")


if __name__ == "__main__":
    unittest.main()
