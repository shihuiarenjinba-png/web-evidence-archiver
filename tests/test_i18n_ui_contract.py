from pathlib import Path
import unittest

import i18n

ROOT = Path(__file__).resolve().parents[1]
UI_FILE = ROOT / "app.py"
SOURCE = "① URLまたは設定JSONを選択  →  ② 保存先を確認  →  ③ HTML・PNG・PDF・SHA256を保存"
ENGLISH = "① Choose URL/config  →  ② Confirm output folder  →  ③ Save HTML, PNG, PDF and SHA256"
JAPANESE = "① URLまたは設定JSONを選択  →  ② 保存先を確認  →  ③ HTML・PNG・PDF・SHA256を保存"


class I18nUiContractTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("en")

    def test_guide_switches_both_languages(self):
        i18n.set_language("en")
        self.assertEqual(i18n.translate(SOURCE), ENGLISH)
        i18n.set_language("ja")
        self.assertEqual(i18n.translate(SOURCE), JAPANESE)

    def test_ui_installs_visible_language_switch(self):
        ui = UI_FILE.read_text(encoding="utf-8")
        helper = (ROOT / "i18n.py").read_text(encoding="utf-8")
        self.assertIn("install_bilingual_ui", ui)
        self.assertIn("Language / 言語", helper)


if __name__ == "__main__":
    unittest.main()
