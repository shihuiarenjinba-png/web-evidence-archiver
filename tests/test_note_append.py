from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app_v2 import build_managed_config
from archiver import append_capture_note


class MemoLinkTests(unittest.TestCase):
    def test_existing_note_is_preserved_and_entry_is_appended(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            note = root / "notes.md"
            note.write_text("既存メモ", encoding="utf-8")
            result = {
                "created_at": "2026-10-07T18:00:00+09:00",
                "captures": [{"requested_url": "https://example.com/"}],
                "output": str(root / "web_evidence_1"),
                "manifest": str(root / "web_evidence_1" / "manifest.json"),
                "complete": True,
            }
            append_capture_note(note, result)
            text = note.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("既存メモ"))
            self.assertIn("## Web Evidence Archiver 記録", text)
            self.assertIn("https://example.com/", text)
            self.assertIn("完了状態: 完了", text)

    def test_empty_note_starts_with_entry(self):
        with tempfile.TemporaryDirectory() as folder:
            note = Path(folder) / "notes.txt"
            note.write_text("", encoding="utf-8")
            append_capture_note(note, {
                "created_at": "2026-10-07T18:00:00+09:00",
                "captures": [],
                "output": "out",
                "manifest": "manifest.json",
                "complete": False,
            })
            self.assertTrue(note.read_text(encoding="utf-8").startswith("## Web Evidence Archiver 記録"))

    def test_only_text_or_markdown_note_is_allowed(self):
        with tempfile.TemporaryDirectory() as folder:
            note = Path(folder) / "notes.docx"
            note.write_bytes(b"not-a-docx")
            with self.assertRaises(ValueError):
                append_capture_note(note, {"captures": [], "complete": True})

    def test_config_can_store_optional_memo_path(self):
        with tempfile.TemporaryDirectory() as folder:
            note = Path(folder) / "notes.md"
            note.write_text("", encoding="utf-8")
            config = build_managed_config(
                "https://example.com/",
                "example.com",
                str(Path(folder) / "output"),
                "Example",
                str(note),
            )
            self.assertEqual(config["memo_path"], str(note))


if __name__ == "__main__":
    unittest.main()
