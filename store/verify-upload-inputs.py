"""Static Store upload candidate checker. NEVER publishes, edits source, or tests GUI.

Usage:
    python store/verify-upload-inputs.py
    python store/verify-upload-inputs.py --msix "store-output/.../Example.msix"

A passed package integrity check is NOT Windows E2E, certification, or a sales GO.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "store"
REQUIRED_LOGOS = {
    "StoreLogo.png": (50, 50),
    "Square44x44Logo.png": (44, 44),
    "Square150x150Logo.png": (150, 150),
    "Wide310x150Logo.png": (310, 150),
}
CONFIRMED_STATES = {"EXISTING_CONFIRMED", "RESERVED_CONFIRMED", "SUBMISSION_DRAFT_CONFIRMED"}


def check(msix: Path | None = None) -> dict:
    blockers: list[str] = []
    warnings: list[str] = []
    product = json.loads((STORE / "product.json").read_text(encoding="utf-8"))
    record = json.loads((STORE / "partner_center_registration.json").read_text(encoding="utf-8"))
    name = product.get("displayName", "")
    repo = ROOT.name
    if record.get("repository") != repo or record.get("displayName") != name:
        blockers.append("Product and registration metadata do not match repository.")
    if record.get("targetPackage") != "MSIX":
        blockers.append("Expected a MSIX product registration.")
    entrypoint = product.get("entryPoint", "")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*\.py", entrypoint):
        blockers.append("Invalid or missing product entryPoint.")
    elif not (ROOT / entrypoint).is_file():
        blockers.append(f"Python entry point missing: {entrypoint}")
    if not (STORE / "build-msix.ps1").is_file():
        blockers.append("Store MSIX build script missing.")
    official = record.get("storeIdentity") or {}
    for field in ("storeId", "packageIdentityName", "packageIdentityPublisher",
                  "publisherDisplayName", "packageFamilyName"):
        if not isinstance(official.get(field), str) or not official[field].strip():
            blockers.append(f"Official Partner Center value missing: {field}")
    if record.get("partnerCenterState") not in CONFIRMED_STATES:
        blockers.append("Partner Center name reservation / existing product not confirmed.")
    if record.get("certificationSubmission") != "NOT_AUTHORIZED":
        warnings.append("Check certificationSubmission flag; this script never authorizes release.")
    if record.get("salesRelease") != "HOLD":
        warnings.append("Sales flag is not HOLD; verify separate owner's authorization.")
    if product.get("needsBundledBrowser"):
        blockers.append("Bundled Chromium runtime is not proven; Web Archiver package HOLD.")

    for filename, expected in REQUIRED_LOGOS.items():
        p = STORE / "assets" / filename
        if not p.is_file():
            blockers.append(f"Approved artwork missing: store/assets/{filename}")
            continue
        try:
            data = p.read_bytes()[:24]
            if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("not PNG")
            dims = struct.unpack(">II", data[16:24])
            if dims != expected:
                raise ValueError(f"dimensions {dims}, expected {expected}")
        except (OSError, ValueError, struct.error) as exc:
            blockers.append(f"Invalid artwork {filename}: {exc}")

    msix_details = None
    if msix is None:
        blockers.append("Actual .msix file not supplied; source preparation only.")
    else:
        msix = msix.resolve()
        if not msix.is_file() or msix.suffix.lower() != ".msix":
            blockers.append("MSIX path missing or not a .msix file.")
        else:
            try:
                with zipfile.ZipFile(msix) as z:
                    members = set(z.namelist())
                    required = {"AppxManifest.xml", f"App/{product['exeName']}.exe"}
                    required.update(f"Assets/{x}" for x in REQUIRED_LOGOS)
                    missing = sorted(required - members)
                    if missing:
                        blockers.append(f"MSIX archive missing: {missing}")
                    manifest = ET.fromstring(z.read("AppxManifest.xml"))
                    ns = {"m": "http://schemas.microsoft.com/appx/manifest/foundation/windows10"}
                    tag = manifest.find("m:Identity", ns)
                    if tag is None:
                        blockers.append("Missing Identity in MSIX manifest.")
                    else:
                        for xml_name, field in (
                            ("Name", "packageIdentityName"),
                            ("Publisher", "packageIdentityPublisher"),
                        ):
                            if tag.get(xml_name) != official.get(field):
                                blockers.append(f"MSIX Identity/{xml_name} differs from Partner Center.")
                        version = tag.get("Version") or ""
                        if not re.fullmatch(r"\d+\.\d+\.\d+\.0", version):
                            blockers.append("MSIX manifest version must end in .0.")
                    h = hashlib.sha256()
                    with msix.open("rb") as fh:
                        for block in iter(lambda: fh.read(1024 * 1024), b""):
                            h.update(block)
                    msix_details = {"path": str(msix), "sha256": h.hexdigest(),
                                    "size_bytes": msix.stat().st_size}
            except (zipfile.BadZipFile, KeyError, ET.ParseError, OSError) as exc:
                blockers.append(f"Unable to validate MSIX contents: {exc}")
    return {
        "product": name,
        "repository": repo,
        "draft_package_upload_ready": len(blockers) == 0,
        "certification_ready": False,
        "sales_release": "HOLD",
        "windows_gui_e2e": "DEFERRED_BY_OWNER",
        "msix": msix_details,
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--msix", type=Path, default=None, help="Optional actual built MSIX for static manifest/ZIP check")
    args = ap.parse_args()
    try:
        result = check(args.msix)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        result = {"draft_package_upload_ready": False, "sales_release": "HOLD",
                  "blockers": [f"Inspection error: {exc}"]}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["draft_package_upload_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
