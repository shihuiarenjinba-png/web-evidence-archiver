from __future__ import annotations

import importlib.metadata
import json
import re
import shutil
import sys
from pathlib import Path

LICENSE_NAME_RE = re.compile(r"(?:^|/)(?:licen[cs]e|copying|notice)(?:[._-].*)?$", re.I)

def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "package"

def collect(output_dir: str | Path) -> Path:
    out = Path(output_dir).resolve(); out.mkdir(parents=True, exist_ok=True); inventory=[]
    for dist in importlib.metadata.distributions():
        name=dist.metadata.get("Name") or "unknown"; version=dist.version; copied=[]
        for entry in dist.files or []:
            rel=str(entry).replace("\\", "/")
            if not LICENSE_NAME_RE.search(rel): continue
            try: source=Path(dist.locate_file(entry)).resolve()
            except Exception: continue
            if not source.is_file(): continue
            target=out / f"{safe_name(name)}-{safe_name(version)}-{safe_name(source.name)}"
            if target.exists(): continue
            try: shutil.copy2(source, target); copied.append(target.name)
            except OSError: continue
        if copied: inventory.append({"package":name,"version":version,"files":copied})
    for candidate in (Path(sys.base_prefix)/"LICENSE.txt", Path(sys.base_prefix)/"LICENSE"):
        if candidate.is_file():
            target=out/f"Python-{safe_name(sys.version.split()[0])}-{candidate.name}"; shutil.copy2(candidate,target)
            inventory.append({"package":"Python","version":sys.version.split()[0],"files":[target.name]}); break
    (out/"LICENSE_INVENTORY.json").write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding="utf-8")
    return out

if __name__ == "__main__":
    print(collect(sys.argv[1] if len(sys.argv)>1 else "dist/licenses"))
