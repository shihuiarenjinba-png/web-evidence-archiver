"""Read-only guardrails for Group C's new unsigned Store MSIX wrapper.

These are source-contract tests, NOT evidence of a Windows build, PowerShell
parsing, packaging, browser redistribution compliance, or Store acceptance.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "store" / "build-msix.ps1"
WORKFLOW = ROOT / ".github" / "workflows" / "group-c-msix-preflight.yml"


class UnsignedWrapperSourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.wrapper = WRAPPER.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_single_wrapper_body_not_duplicated(self):
        self.assertEqual(self.wrapper.count("[CmdletBinding()]"), 1)
        self.assertEqual(self.wrapper.count("QA_UNSIGNED_MSIX_CREATED"), 1)
        self.assertEqual(self.wrapper.count("STORE_SUBMISSION=NOT_AUTHORIZED"), 1)
        self.assertEqual(self.wrapper.count("if ($Commit -notmatch"), 1)

    def test_exact_repo_branch_and_clean_head_checked_before_writes(self):
        text = self.wrapper
        origin = text.index("$RemoteUrl = Git-Value")
        branch = text.index("if ($Branch -cne")
        head = text.index("if ($RemoteCommit -cne")
        dirty = text.index("if ($Dirty) { throw")
        first_output = text.index("New-Item -ItemType Directory")
        self.assertLess(origin, branch)
        self.assertLess(branch, head)
        self.assertLess(head, dirty)
        self.assertLess(dirty, first_output)
        self.assertIn("github[.]com[:/]shihuiarenjinba-png/web-evidence-archiver", text)
        self.assertIn("codex/store-p0-web-evidence-20261023", text)

    def test_unsigned_only_no_upload_or_certificate_work(self):
        text = self.wrapper
        self.assertIn("if (-not $Report.ready) { throw", text)
        self.assertIn("browser_payload_sha256", text)
        self.assertIn("AppxManifest.xml", text)
        self.assertIn("Get-FileHash", text)
        self.assertNotIn("SignTool.exe", text)
        self.assertNotIn("New-SelfSignedCertificate", text)
        self.assertIn("QA_UNSIGNED", text)
        self.assertNotIn("partner.microsoft.com/api", text)

    def test_conditional_workflow_does_not_build_on_hold(self):
        self.assertIn("needs.inspect.outputs.ready == 'true'", self.workflow)
        self.assertIn("build-msix.ps1 -PreflightOnly", self.workflow)
        self.assertIn("build-msix.ps1", self.workflow)
        self.assertNotIn("Submit for certification", self.workflow)


if __name__ == "__main__":
    unittest.main()
