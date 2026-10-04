"""No-network validation of first-run Web archiver settings."""
import json
import pytest
from app import EXAMPLE_URL, EXAMPLE_HOST, build_gui_config, validate_application_config

def test_public_page_preset(tmp_path):
    config = build_gui_config(EXAMPLE_URL, EXAMPLE_HOST, str(tmp_path))
    assert config["urls"] == [EXAMPLE_URL]
    assert config["allow_hosts"] == [EXAMPLE_HOST]
    path = tmp_path / "archiver.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    validate_application_config(str(path))

def test_arbitrary_json_rejected(tmp_path):
    path = tmp_path / "page.json"
    path.write_text(json.dumps({"title": "Example Domain"}), encoding="utf-8")
    with pytest.raises(ValueError, match="設定"):
        validate_application_config(str(path))

def test_empty_config_and_host_mismatch(tmp_path):
    with pytest.raises(ValueError, match="設定JSON"):
        validate_application_config("")
    with pytest.raises(ValueError, match="allow_hosts"):
        build_gui_config(EXAMPLE_URL, "example.net", str(tmp_path))
