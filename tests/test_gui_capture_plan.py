"""GUI approval regressions. No browser launch, network or GUI display needed."""
import json
import tempfile
import unittest
from pathlib import Path

from gui_capture_plan import approved_revision, prepare_advanced_plan, prepare_manual_plan


class CapturePlanTests(unittest.TestCase):
    def test_two_urls_become_one_reviewable_capture_without_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "not_created"
            plan = prepare_manual_plan(
                "https://example.com/pricing\nhttps://docs.example.com/help\n", str(output))
            self.assertEqual(plan["urls"], [
                "https://example.com/pricing", "https://docs.example.com/help"])
            self.assertEqual(plan["allow_hosts"], ["docs.example.com", "example.com"])
            self.assertFalse(output.exists())

    def test_unchanged_approval_and_revoke_on_changed_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = prepare_manual_plan("https://example.com/one", tmp)
            same = prepare_manual_plan("https://example.com/one\n", tmp)
            changed = prepare_manual_plan("https://example.com/two", tmp)
            self.assertEqual(approved_revision(first), approved_revision(same))
            self.assertNotEqual(approved_revision(first), approved_revision(changed))

    def test_duplicate_and_secret_urls_are_not_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            for urls in [
                "https://example.com/\nhttps://example.com/",
                "http://example.com/",
                "https://example.com/path?token=secret",
                "https://user:pass@example.com/",
                "https://127.0.0.1/",
                "https://localhost/",
            ]:
                with self.subTest(urls=urls), self.assertRaises(ValueError):
                    prepare_manual_plan(urls, tmp)

    def test_advanced_config_is_pinned_to_exact_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / "settings.json"
            settings.write_text(json.dumps({
                "allow_hosts": ["example.com"],
                "urls": ["https://example.com/"],
                "output_dir": str(Path(tmp) / "output"),
                "timeout_seconds": 30,
            }), encoding="utf-8")
            first, h1 = prepare_advanced_plan(str(settings))
            self.assertEqual(first["urls"], ["https://example.com/"])
            settings.write_text(settings.read_text(encoding="utf-8") + "  ", encoding="utf-8")
            second, h2 = prepare_advanced_plan(str(settings))
            self.assertNotEqual(approved_revision(first, h1),
                                approved_revision(second, h2))

    def test_advanced_invalid_json_is_not_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "broken.json"
            p.write_text("{broken json", encoding="utf-8")
            with self.assertRaises(ValueError):
                prepare_advanced_plan(str(p))


if __name__ == "__main__":
    unittest.main()
