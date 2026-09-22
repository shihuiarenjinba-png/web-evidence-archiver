"""Create sale-review metadata from the active build environment.

This tool intentionally records only information published by installed package
metadata.  It never guesses license texts or assigns a license to this product.
"""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path


UNKNOWN_LICENSE = "UNKNOWN (not declared in installed package metadata)"


def package_records() -> list[dict[str, str]]:
    records: dict[str, dict[str, str]] = {}
    for distribution in metadata.distributions():
        meta = distribution.metadata
        name = (meta.get("Name") or "").strip()
        if not name:
            continue
        key = name.lower().replace("_", "-")
        license_value = (
            (meta.get("License-Expression") or "").strip()
            or (meta.get("License") or "").strip()
            or UNKNOWN_LICENSE
        )
        records[key] = {
            "name": name,
            "version": distribution.version,
            "license": license_value,
            "homepage": (meta.get("Home-page") or "").strip(),
        }
    return [records[key] for key in sorted(records)]


def write_lock(output: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"], check=True, text=True, capture_output=True
    )
    header = f"# Generated with Python {sys.version.split()[0]}\n"
    (output / "runtime-requirements-lock.txt").write_text(header + result.stdout, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--product", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    packages = package_records()
    write_lock(args.output)
    generated = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    components = []
    for package in packages:
        component: dict[str, object] = {
            "type": "library",
            "name": package["name"],
            "version": package["version"],
            "purl": f"pkg:pypi/{package['name']}@{package['version']}",
            "properties": [{"name": "okinawa:license-metadata", "value": package["license"]}],
        }
        if package["homepage"]:
            component["externalReferences"] = [{"type": "website", "url": package["homepage"]}]
        components.append(component)
    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": generated,
            "tools": [{"vendor": "Python", "name": "importlib.metadata", "version": sys.version.split()[0]}],
            "component": {"type": "application", "name": args.product, "version": args.version},
            "properties": [
                {"name": "okinawa:inventory-scope", "value": "Installed build environment; see runtime-requirements-lock.txt."},
                {"name": "okinawa:product-license", "value": "PENDING APPROVAL"},
            ],
        },
        "components": components,
    }
    (args.output / f"{args.product}-SBOM.cdx.json").write_text(
        json.dumps(bom, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    notice = [
        f"Third-party notice candidate for {args.product} {args.version}",
        "Generated from installed package metadata. No license text is inferred or reproduced.",
        "A package marked UNKNOWN needs legal review before sale.",
        "",
    ]
    for package in packages:
        notice.extend((f"- {package['name']} {package['version']}", f"  License metadata: {package['license']}"))
        if package["homepage"]:
            notice.append(f"  Homepage metadata: {package['homepage']}")
    (args.output / "THIRD_PARTY_NOTICE.txt").write_text("\n".join(notice) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
