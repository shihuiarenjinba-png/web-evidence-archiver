"""Structural release gate: verify source, not Windows MSIX execution.

This test can run on Linux/Windows; success is NOT Microsoft Store acceptance.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StoreCandidateSourceChecks(unittest.TestCase):
    def test_product_settings_are_unique_placeholders_not_fake_identity(self):
        cfg = json.loads((ROOT / "store" / "product.json").read_text(encoding="utf-8"))
        self.assertTrue(cfg["exeName"].isidentifier())
        self.assertTrue(cfg["appId"].isidentifier())
        self.assertEqual(cfg["entryPoint"], "app.py")
        self.assertEqual(cfg["storeStatus"], "HOLD_OFFICIAL_PARTNER_IDENTITY_REQUIRED")
        self.assertEqual(cfg["commercialLicense"], "NOT_CERTIFIED")
        self.assertNotIn("publisher", cfg)
        self.assertNotIn("packageFamilyName", cfg)

    def test_msix_script_has_valid_single_manifest_and_fail_closed_gates(self):
        text = (ROOT / "store" / "build-msix.ps1").read_text(encoding="utf-8")
        self.assertEqual(text.count("#requires -Version 5.1"), 1)
        self.assertEqual(text.count("<Package xmlns="), 1)
        self.assertEqual(text.count("$xml = @'"), 1)
        self.assertEqual(text.count("\n'@"), 1)
        for key in (
            "STORE_IDENTITY_NAME", "STORE_PUBLISHER", "STORE_VERSION",
            "STORE_IDENTITY_CONFIRMED", "STORE_BRAND_APPROVED",
            "PREFLIGHT_PASS_NO_PACKAGE", "python", "PyInstaller",
            "makeappx.exe", "MSIX_AUDIT.json", "UNSIGNED_MSIX_CANDIDATE"
        ):
            self.assertIn(key, text, key)
        for forbidden in (
            "Remove-AppxPackage", "Add-AppxPackage", "Import-PfxCertificate",
            "Start-Process -Verb RunAs", "Set-ExecutionPolicy"
        ):
            self.assertNotIn(forbidden, text)
        self.assertRegex(text, r"unittest\s+discover")
        self.assertIn("store-output\\", text)
        self.assertIn('Join-Path $out "spec"', text)
        self.assertIn('Join-Path $out "work"', text)

    def test_all_png_dimensions_have_a_mandatory_approval_gate(self):
        src = (ROOT / "store" / "build-msix.ps1").read_text(encoding="utf-8")
        candidate = (ROOT / "store" / "make-logo-candidates.ps1").read_text(encoding="utf-8")
        for name in ("StoreLogo.png", "Square44x44Logo.png",
                     "Square150x150Logo.png", "Wide310x150Logo.png"):
            self.assertIn(name, src)
            self.assertIn(name, candidate)
        self.assertIn("STORE_BRAND_APPROVED", src)
        self.assertIn("KEEP_EXISTING", candidate)

    def test_chromium_dependent_products_are_blocked_until_bundled(self):
        cfg = json.loads((ROOT / "store" / "product.json").read_text(encoding="utf-8"))
        script = (ROOT / "store" / "build-msix.ps1").read_text(encoding="utf-8")
        self.assertIn("needsBundledBrowser", cfg)
        self.assertIn("if ($cfg.needsBundledBrowser)", script)
        if cfg["needsBundledBrowser"]:
            self.assertIn("offline Chromium bundle", script)


if __name__ == "__main__":
    unittest.main()
