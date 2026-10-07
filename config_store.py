from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


SENSITIVE_KEYS = ("authorization", "api_key", "apikey", "token", "secret", "password")


def read_json_object(path: str | Path) -> dict[str, Any]:
    """Read a JSON object without mutating any caller-owned editing state."""
    value = json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("設定JSONの最上位はオブジェクトである必要があります。")
    return value


def _contains_plaintext_secret(value: Any, key: str = "") -> bool:
    if isinstance(value, dict):
        return any(_contains_plaintext_secret(child, str(name)) for name, child in value.items())
    if isinstance(value, list):
        return any(_contains_plaintext_secret(child, key) for child in value)
    if any(marker in key.casefold() for marker in SENSITIVE_KEYS):
        text = str(value)
        return bool(text) and "${ENV:" not in text
    return False


def atomic_write_json(
    path: str | Path,
    document: dict[str, Any],
    *,
    overwrite: bool = False,
    backup: bool = False,
) -> tuple[Path, Path | None]:
    """Atomically store JSON on the same filesystem and optionally back up the old file."""
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise FileExistsError("同名の設定が既にあります。更新または別名を選んでください。")

    backup_path: Path | None = None
    if target.exists() and backup:
        old = read_json_object(target)
        if _contains_plaintext_secret(old):
            raise ValueError("平文の機密値を含む可能性があるため、バックアップを作成できません。環境変数参照へ移行してください。")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = target.with_name(f"{target.stem}.backup-{stamp}{target.suffix}")
        counter = 1
        while backup_path.exists():
            backup_path = target.with_name(f"{target.stem}.backup-{stamp}-{counter}{target.suffix}")
            counter += 1
        backup_path.write_bytes(target.read_bytes())

    payload = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", prefix=f".{target.name}.", suffix=".tmp",
            dir=target.parent, delete=False,
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target, backup_path


def list_config_files(folder: str | Path) -> list[Path]:
    root = Path(folder).expanduser().resolve()
    if not root.exists():
        return []
    return sorted(
        (p for p in root.glob("*.json") if ".backup-" not in p.name),
        key=lambda p: p.name.casefold(),
    )
