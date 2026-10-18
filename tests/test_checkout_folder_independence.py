"""Protect Windows Store packaging from depending on the clone folder name."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "store"


class CheckoutNameIndependenceTests(unittest.TestCase):
    def test_product_repository_slug_drives_identity_validation(self):
        product = json.loads((STORE / "product.json").read_text(encoding="utf-8"))
        record = json.loads((STORE / "partner_center_registration.json").read_text(encoding="utf-8"))
        self.assertEqual(product["repository"], record["repository"])
        self.assertTrue(product["repository"])
        self.assertEqual(product["displayName"], record["displayName"])

    def test_packaging_scripts_use_slug_not_checkout_basename(self):
        for filename in ("build-msix.ps1", "build-with-partner-identity.ps1"):
            src = (STORE / filename).read_text(encoding="utf-8")
            self.assertNotIn("(Split-Path $root -Leaf)", src)
            self.assertNotIn("(Split-Path $repo -Leaf)", src)
            self.assertIn(".repository", src)

    def test_checker_does_not_require_repo_directory_name(self):
        src = (STORE / "verify-upload-inputs.py").read_text(encoding="utf-8")
        self.assertIn('product.get("repository"', src)
        self.assertNotIn("repo = ROOT.name", src)


if __name__ == "__main__":
    unittest.main()
