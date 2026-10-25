import json
from pathlib import Path

from thinkpad_deals.cli import apply_control, load_config, load_control, title_passes

ROOT = Path(__file__).parent.parent


def test_control_applies_to_sources(tmp_path):
    ctl = {"sources": {"afb": {"enabled": False}, "hardware-online-shop": {"max_pages": 1, "urls": ["https://x/{page}"]},
                       "mydealz": {"urls": ["https://m/rss"]}}}
    cfg = apply_control(load_config(ROOT / "config" / "sources.yaml"), ctl)
    by = {s["name"]: s for s in cfg["sources"]}
    assert by["afb"]["enabled"] is False
    assert by["hardware-online-shop"]["max_pages"] == 1 and by["hardware-online-shop"]["urls"] == ["https://x/{page}"]
    assert by["mydealz"]["feeds"] == ["https://m/rss"]


def test_repo_control_json_is_valid_and_complete():
    ctl = load_control(None)
    cfg = load_config(ROOT / "config" / "sources.yaml")
    assert set(ctl["sources"]) >= {s["name"] for s in cfg["sources"]}
    assert ctl["interval_hours"] >= 1 and ctl["profile"] in ("dev", "office")


def test_title_filter():
    ctl = {"keywords": ["thinkpad"], "exclude": ["dock", "netzteil"]}
    assert title_passes("Lenovo ThinkPad T14 Gen 3", ctl)
    assert not title_passes("Lenovo ThinkPad USB-C Dock Gen 2", ctl)
    assert not title_passes("Lenovo IdeaPad 5", ctl)
    assert title_passes("irgendwas", {})
