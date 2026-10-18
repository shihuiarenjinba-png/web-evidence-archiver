"""Offline plan and approval signatures for the beginner evidence-capture GUI.

No browser starts, no destination is created and no network request occurs here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from archiver import load_config, validate_url

MAX_GUI_URLS = 20


def prepare_manual_plan(lines: str, output_directory: str) -> dict:
    urls = [s.strip() for s in lines.splitlines() if s.strip()]
    if not urls:
        raise ValueError("HTTPS URLを入力してください。1行につき1件です。")
    if len(urls) > MAX_GUI_URLS:
        raise ValueError(f"一度に指定できるURLは{MAX_GUI_URLS}件までです。")
    if len(set(urls)) != len(urls):
        raise ValueError("URLが重複しています。重複行を削除してください。")
    if not output_directory.strip():
        raise ValueError("保存するフォルダーを選んでください。")
    requested_path = Path(output_directory).expanduser()
    if requested_path.is_symlink():
        raise ValueError("保存先のシンボリックリンクは使用できません。")
    output = requested_path.resolve()
    if output.exists() and not output.is_dir():
        raise ValueError("保存先はフォルダーを選択してください。")
    hosts = sorted({(urlparse(url).hostname or "").lower().rstrip(".") for url in urls})
    for url in urls:
        validate_url(url, hosts)
    return {
        "allow_hosts": hosts,
        "urls": urls,
        "output_dir": str(output),
        "timeout_seconds": 30,
    }


def prepare_advanced_plan(config_filename: str) -> tuple[dict, str]:
    if not config_filename.strip():
        raise ValueError("詳細設定JSONを指定してください。")
    path = Path(config_filename).expanduser()
    if path.is_symlink() or not path.is_file():
        raise ValueError("既存の通常JSONファイルを指定してください。")
    if path.stat().st_size <= 0 or path.stat().st_size > 1024 * 1024:
        raise ValueError("設定JSONは1MiB以下にしてください。")
    before = path.read_bytes()
    config = load_config(path)
    after = path.read_bytes()
    if before != after:
        raise ValueError("設定JSONが検査中に変更されました。")
    return config, hashlib.sha256(after).hexdigest()


def approved_revision(config: dict, advanced_digest: str = "") -> str:
    snapshot = json.dumps({"configuration": config, "advanced_digest": advanced_digest},
                          ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(snapshot.encode("utf-8")).hexdigest()
