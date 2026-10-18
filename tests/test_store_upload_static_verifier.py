"""Synthetic MSIX archive checks; no Windows installation or Store publishing."""
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("upload_verifier_under_test",
                                              ROOT / "store" / "verify-upload-inputs.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class StaticStoreUploadVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = self.root / "store"
        (self.store / "assets").mkdir(parents=True)
        (self.root / "app.py").write_text("# dummy", encoding="utf-8")
        (self.store / "build-msix.ps1").write_text("# dummy", encoding="utf-8")
        self.product = {
            "displayName": "Test Product", "repository": "test-repo",
            "entryPoint": "app.py", "exeName": "TestApp",
            "appId": "TestApp", "needsBundledBrowser": False,
        }
        self.record = {
            "repository": "test-repo", "displayName": "Test Product",
            "targetPackage": "MSIX", "partnerCenterState": "EXISTING_CONFIRMED",
            "certificationSubmission": "NOT_AUTHORIZED", "salesRelease": "HOLD",
            "storeIdentity": {
                "storeId": "EXAMPLE", "packageIdentityName": "Example.TestApp",
                "packageIdentityPublisher": "CN=Example",
                "publisherDisplayName": "Example", "packageFamilyName": "Example.TestApp_abcd",
            },
        }
        self._write_json()
        for filename, size in verifier.REQUIRED_LOGOS.items():
            header = b"\x89PNG\r\n\x1a\n" + b"\x00"*8 + struct.pack(">II", *size)
            (self.store / "assets" / filename).write_bytes(header)
        self.msix = self.root / "TestApp.msix"
        self._msix()

    def _write_json(self):
        (self.store / "product.json").write_text(
            json.dumps(self.product), encoding="utf-8")
        (self.store / "partner_center_registration.json").write_text(
            json.dumps(self.record), encoding="utf-8")

    def _msix(self, display="Test Product", arch="x64",
              app_id="TestApp", exe="App\\TestApp.exe", duplicate=False):
        xml = (
            '<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10">'
            f'<Identity Name="Example.TestApp" Publisher="CN=Example" '
            f'Version="1.0.0.0" ProcessorArchitecture="{arch}"/>'
            f'<Properties><DisplayName>{display}</DisplayName></Properties>'
            f'<Applications><Application Id="{app_id}" Executable="{exe}"/></Applications>'
            '</Package>'
        )
        with zipfile.ZipFile(self.msix, "w") as z:
            z.writestr("AppxManifest.xml", xml)
            z.writestr("App/TestApp.exe", "test")
            for fname in verifier.REQUIRED_LOGOS:
                z.writestr("Assets/" + fname, b"icon")
            if duplicate:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    z.writestr("App/TestApp.exe", "other")

    def _check(self):
        original_root, original_store = verifier.ROOT, verifier.STORE
        try:
            verifier.ROOT, verifier.STORE = self.root, self.store
            return verifier.check(self.msix)
        finally:
            verifier.ROOT, verifier.STORE = original_root, original_store

    def test_good_identity_is_draft_ready_but_never_certified(self):
        result = self._check()
        self.assertTrue(result["draft_package_upload_ready"], result["blockers"])
        self.assertFalse(result["certification_ready"])
        self.assertEqual(result["sales_release"], "HOLD")
        self.assertEqual(len(result["msix"]["sha256"]), 64)

    def test_wrong_display_name_architecture_and_appid_are_rejected(self):
        for kwargs in ({"display": "Wrong Product"}, {"arch": "arm64"},
                       {"app_id": "WrongApp"}, {"exe": "App\\Else.exe"},
                       {"duplicate": True}):
            with self.subTest(kwargs=kwargs):
                self._msix(**kwargs)
                result = self._check()
                self.assertFalse(result["draft_package_upload_ready"])
                self.assertTrue(result["blockers"])

    def test_unapproved_certification_or_release_blocks_draft_check(self):
        for key, value in (("certificationSubmission", "AUTHORIZED"),
                           ("salesRelease", "GO")):
            with self.subTest(key=key):
                self._msix()
                self.record[key] = value
                self._write_json()
                self.assertFalse(self._check()["draft_package_upload_ready"])
                self.record[key] = (
                    "NOT_AUTHORIZED" if key == "certificationSubmission" else "HOLD"
                )
                self._write_json()


if __name__ == "__main__":
    unittest.main()
