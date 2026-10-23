"""Fail-closed, read-only MSIX readiness report for Web Evidence Archiver.

This checks owner-approved configuration, NOT whether Microsoft accepted a package.
Use --strict to reject incomplete inputs before invoking any packager.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STORE_ID = "9NNT1B142ZWV"
ASSETS = {
    "StoreLogo.png": (50, 50),
    "Square44x44Logo.png": (44, 44),
    "Square150x150Logo.png": (150, 150),
}


def read_json(path: Path) -> dict:
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return result


def check_png(path: Path, dimensions: tuple[int, int]) -> bool:
    try:
        with path.open("rb") as source:
            header = source.read(24)
        return (len(header) == 24
                and header[:8] == b"\x89PNG\r\n\x1a\n"
                and header[12:16] == b"IHDR"
                and struct.unpack(">II", header[16:24]) == dimensions)
    except OSError:
        return False


def blockers_for(root: Path, registration: dict, product: dict) -> list[str]:
    blockers: list[str] = []
    fields = registration.get("storeIdentity")
    if not isinstance(fields, dict):
        fields = {}
    if registration.get("repository") != "web-evidence-archiver":
        blockers.append("repository: wrong product")
    if registration.get("displayName") != product.get("displayName"):
        blockers.append("displayName: product and registration differ")
    if product.get("needsBundledBrowser") is not True:
        blockers.append("browser: product config must explicitly request a bundled browser")
    if product.get("entryPoint") != "app.py":
        blockers.append("entryPoint: unexpected application entry point")
    if fields.get("storeId") != STORE_ID:
        blockers.append("storeId: this product's owner-provided identifier missing or mismatched")
    if registration.get("storeIdVerificationStatus") != "PARTNER_CENTER_VERIFIED":
        blockers.append("storeId: live Partner Center confirmation not recorded")
    if registration.get("partnerCenterState") not in (
            "EXISTING_CONFIRMED", "RESERVED_CONFIRMED", "SUBMISSION_DRAFT_CONFIRMED"):
        blockers.append("partnerCenterState: unverified or conditional")
    name = fields.get("packageIdentityName")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,48}", name):
        blockers.append("packageIdentityName: exact verified value absent or invalid")
    publisher = fields.get("packageIdentityPublisher")
    if not isinstance(publisher, str) or not publisher.startswith("CN=") or len(publisher) <= 3:
        blockers.append("packageIdentityPublisher: exact verified value absent")
    for field in ("publisherDisplayName", "packageFamilyName"):
        if not isinstance(fields.get(field), str) or not fields[field].strip():
            blockers.append(f"{field}: exact verified value absent")
    verification = registration.get("identityFieldVerification")
    if not isinstance(verification, dict):
        verification = {}
    for field in ("packageIdentityName", "packageIdentityPublisher",
                  "publisherDisplayName", "packageFamilyName"):
        if verification.get(field) != "PARTNER_CENTER_VERIFIED":
            blockers.append(f"{field}: live verification status not confirmed")
    version = registration.get("approvedStoreVersion")
    version_ok = (isinstance(version, str)
                  and re.fullmatch(r"\d+\.\d+\.\d+\.0", version))
    if version_ok:
        components = [int(part) for part in version.split(".")]
        version_ok = components[0] >= 1 and all(x <= 65535 for x in components)
    if not version_ok:
        blockers.append("approvedStoreVersion: exact approved four-part Store version required (revision 0)")
    if registration.get("manifestResources") not in (["ja-JP"], ["en-US"],
                                                       ["ja-JP", "en-US"],
                                                       ["en-US", "ja-JP"]):
        blockers.append("manifestResources: owner-approved languages required")
    if registration.get("certificationSubmission") != "NOT_AUTHORIZED":
        blockers.append("certificationSubmission: unauthorized change of release hold")
    if registration.get("salesRelease") != "HOLD":
        blockers.append("salesRelease: unauthorized change of release hold")

    assets = root / "store" / "assets"
    approval_path = assets / "approval.json"
    try:
        approval = read_json(approval_path)
        if (approval.get("product_key") != "web-evidence-archiver"
                or approval.get("status") != "OWNER_APPROVED"
                or not approval.get("approval_reference")):
            blockers.append("brandAssets: product-specific owner approval absent")
    except (OSError, ValueError, json.JSONDecodeError):
        blockers.append("brandAssets: owner approval JSON absent or invalid")
    for filename, dimensions in ASSETS.items():
        if not check_png(assets / filename, dimensions):
            blockers.append(f"brandAssets: missing or dimension-invalid {filename}")

    browser_path = root / "store" / "browser_bundle_approval.json"
    try:
        browser = read_json(browser_path)
        expected = (
            browser.get("product_key") == "web-evidence-archiver"
            and browser.get("status") == "OWNER_APPROVED"
            and all(isinstance(browser.get(k), str) and browser[k].strip()
                    for k in ("playwright_version", "chromium_version",
                              "browser_payload_sha256", "license_review_reference",
                              "bundling_qa_reference"))
            and re.fullmatch(r"[0-9a-fA-F]{64}", browser.get("browser_payload_sha256", ""))
        )
        if not expected:
            blockers.append("browserBundle: version/hash/license/Windows QA approval missing")
    except (OSError, ValueError, json.JSONDecodeError):
        blockers.append("browserBundle: browser distribution and offline QA approval absent")
    return sorted(set(blockers))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true",
                        help="Return nonzero if any packaging prerequisite is missing")
    parser.add_argument("--json-out", type=Path, help="Write report to a new path, without overwriting")
    args = parser.parse_args()
    try:
        reg = read_json(HERE / "partner_center_registration.json")
        product = read_json(HERE / "product.json")
        blockers = blockers_for(ROOT, reg, product)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        blockers = [f"configuration: cannot load JSON: {exc}"]
    report = {
        "product": "web-evidence-archiver",
        "store_id": STORE_ID,
        "ready": not blockers,
        "blockers": blockers,
        "package": "NOT_BUILT",
        "signature": "NOT_SIGNED",
        "windows_install_qa": "NOT_VERIFIED",
        "certification_submission": "NOT_AUTHORIZED",
        "sales_release": "HOLD",
    }
    body = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(body, end="")
    if args.json_out is not None:
        if args.json_out.exists():
            print("HOLD: refusing to overwrite an existing report")
            return 2
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(body, encoding="utf-8")
    return 2 if args.strict and blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
