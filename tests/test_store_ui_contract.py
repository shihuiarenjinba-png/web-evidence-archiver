"""Static Store-facing UI contract.

This test protects the reviewed Store-facing title/layout/path-privacy decisions.
It does not replace real Windows 11 DPI or interaction QA.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "app.py").read_text(encoding="utf-8")
CHECKS = [["Web Evidence Archiver","reserved Store name"],["self.geometry(\"810x500\")","default geometry"],["self.minsize(710, 440)","minimum geometry"],["Path(value).name","output path privacy"]]

class StoreUiContractTests(unittest.TestCase):
    def test_reviewed_ui_contract_is_present(self):
        for token, purpose in CHECKS:
            with self.subTest(purpose=purpose):
                self.assertIn(token, UI)

if __name__ == "__main__":
    unittest.main()
