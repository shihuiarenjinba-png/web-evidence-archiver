"""Pure safety regression tests; never create production identities or packages."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from store.msix_preflight import blockers_for


class MsixPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.product = {
            "displayName": "Web Evidence Archiver",
            "needsBundledBrowser": True,
            "entryPoint": "app.py",
        }
        self.reg = {
            "repository": "web-evidence-archiver",
            "displayName": "Web Evidence Archiver",
            "storeIdentity": {"storeId": "9NNT1B142ZWV"},
            "storeIdVerificationStatus": "USER_CONFIRMED_NOT_LIVE_VERIFIED",
            "partnerCenterState": "EXISTING_USER_REPORTED_RECONFIRM",
            "approvedStoreVersion": None,
            "manifestResources": [],
            "certificationSubmission": "NOT_AUTHORIZED",
            "salesRelease": "HOLD",
        }

    def test_owner_provided_store_id_is_not_live_identity(self):
        blockers = blockers_for(self.root, self.reg, self.product)
        self.assertTrue(any("live Partner Center confirmation" in x for x in blockers))
        self.assertTrue(any("packageIdentityName" in x for x in blockers))
        self.assertTrue(any("brandAssets" in x for x in blockers))

    def test_browser_approval_is_required_independently(self):
        self.reg["storeIdVerificationStatus"] = "PARTNER_CENTER_VERIFIED"
        blockers = blockers_for(self.root, self.reg, self.product)
        self.assertTrue(any("browserBundle" in x for x in blockers))

    def test_revision_nonzero_is_blocked(self):
        self.reg["approvedStoreVersion"] = "1.0.0.1"
        self.assertTrue(any("approvedStoreVersion" in x
                            for x in blockers_for(self.root, self.reg, self.product)))

    def test_spoofed_product_and_egress_state_are_blocked(self):
        self.product["needsBundledBrowser"] = False
        self.reg["salesRelease"] = "READY"
        blockers = blockers_for(self.root, self.reg, self.product)
        self.assertTrue(any("browser: product" in x for x in blockers))
        self.assertTrue(any("salesRelease" in x for x in blockers))

    def test_malformed_browser_approval_is_blocked(self):
        approval = self.root / "store" / "browser_bundle_approval.json"
        approval.parent.mkdir(parents=True)
        approval.write_text(json.dumps({"product_key": "web-evidence-archiver",
                                        "status": "OWNER_APPROVED"}), encoding="utf-8")
        self.assertTrue(any("browserBundle" in x
                            for x in blockers_for(self.root, self.reg, self.product)))


if __name__ == "__main__":
    unittest.main()
