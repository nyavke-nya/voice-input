"""Санитайзер конфига и round-trip сохранения."""
import os
import tempfile

from pill import config


def test_sanitize_fixes_garbage():
    s = config._sanitize({
        "language": "de", "model": "huge", "input_method": "telepathy",
        "vad_sensitivity": 9, "silence_ms": "x", "junk": 1,
    })
    assert s["language"] == "auto"
    assert s["model"] == "small"
    assert s["input_method"] == "keyboard"
    assert s["vad_sensitivity"] == 1.0
    assert s["silence_ms"] == 500
    assert "junk" not in s


def test_save_load_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        os.environ["XDG_CONFIG_HOME"] = d
        cfg = config.load()
        cfg["language"] = "ru"
        cfg["silence_ms"] = 700
        config.save(cfg)
        again = config.load()
        assert again["language"] == "ru"
        assert again["silence_ms"] == 700


def test_missing_config_returns_defaults():
    with tempfile.TemporaryDirectory() as d:
        os.environ["XDG_CONFIG_HOME"] = d
        assert config.load() == config.DEFAULTS


def test_malformed_shape_and_nested_defaults_are_safe():
    with tempfile.TemporaryDirectory() as d:
        os.environ["XDG_CONFIG_HOME"] = d
        p = config.config_path()
        p.parent.mkdir(parents=True)
        p.write_text("[]")
        assert config.load() == config.DEFAULTS
        a = config.load()
        a["packs"].append("it")
        assert config.load()["packs"] == ["profanity"]
        assert config._sanitize({"hotkey": "a+b"})["hotkey"] == "grave"


if __name__ == "__main__":
    test_sanitize_fixes_garbage()
    test_save_load_roundtrip()
    test_missing_config_returns_defaults()
    test_malformed_shape_and_nested_defaults_are_safe()
    print("test_config OK")
