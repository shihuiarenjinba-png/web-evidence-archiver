from pathlib import Path

import pytest

from app import build_gui_config
from archiver import load_config


def test_gui_config_supports_multiple_urls_and_hosts(tmp_path: Path) -> None:
    config = build_gui_config(
        "https://example.com/\nhttps://www.example.com/pricing\n",
        "example.com, www.example.com",
        str(tmp_path / "output"),
    )
    assert len(config["urls"]) == 2
    path = tmp_path / "config.json"
    path.write_text(__import__("json").dumps(config), encoding="utf-8")
    assert load_config(path)["browser_channel"] == "msedge"


def test_gui_config_requires_explicit_allow_host(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        build_gui_config("https://example.com/", "", str(tmp_path))
