"""Определение Linux desktop и генерация безопасных managed-блоков."""
import tempfile
import os
from pathlib import Path
from types import SimpleNamespace

from pill import desktop_integration as di, hypr


def test_detect_popular_desktops_and_sessions():
    assert di.detect({"HYPRLAND_INSTANCE_SIGNATURE": "x", "WAYLAND_DISPLAY": "wayland-1"}).label == "hyprland (wayland)"
    assert di.detect({"XDG_CURRENT_DESKTOP": "ubuntu:GNOME", "XDG_SESSION_TYPE": "wayland"}).desktop == "gnome"
    assert di.detect({"XDG_CURRENT_DESKTOP": "KDE", "DISPLAY": ":0"}).label == "kde (x11)"
    assert di.detect({"SWAYSOCK": "/tmp/sway.sock", "XDG_SESSION_TYPE": "wayland"}).desktop == "sway"


def test_hotkey_formats():
    assert di.to_i3("super+alt+d") == "Mod4+Mod1+d"
    assert di.to_i3("ctrl+shift+space") == "Ctrl+Shift+space"
    assert di.to_gsettings("super+grave") == "<Super>grave"
    assert di.to_gsettings("ctrl+alt+a") == "<Control><Alt>a"
    assert di.to_i3("ctrl+backspace") == "Ctrl+BackSpace"
    assert di.to_gsettings("volumeup") == "XF86AudioRaiseVolume"


def test_managed_block_roundtrip_preserves_user_text():
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "config"
        path.write_text("set $mod Mod4\n", encoding="utf-8")
        first = di._sway_block("grave")
        assert di._replace_block(path, first)
        assert path.read_text().count(di.BEGIN) == 1
        second = di._sway_block("ctrl+space")
        assert di._replace_block(path, second)
        text = path.read_text()
        assert text.count(di.BEGIN) == 1 and "Ctrl+space" in text
        assert di._remove_block(path)
        assert path.read_text() == "set $mod Mod4\n"


def test_partial_marker_is_never_overwritten():
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "config"
        original = "user config\n" + di.BEGIN + "\n"
        path.write_text(original, encoding="utf-8")
        assert not di._replace_block(path, di._sway_block("grave"))
        assert path.read_text() == original


def test_gsettings_list_parser():
    expected = ["/one/", "/two/"]
    assert di._parse_gsettings_list("['/one/', '/two/']") == expected
    assert di._parse_gsettings_list("@as ['/one/', '/two/']") == expected
    assert di._parse_gsettings_list("not gvariant") == []
    assert di._gsettings_spec("cinnamon") is None


def test_gnome_binding_commands_preserve_existing_paths():
    calls = []
    original_which, original_run = di.shutil.which, di._gsettings_run
    di.shutil.which = lambda tool: "/usr/bin/gsettings" if tool == "gsettings" else None

    def fake_run(*args):
        calls.append(args)
        if args[:3] == ("get", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"):
            return SimpleNamespace(returncode=0, stdout="['/existing/']")
        return SimpleNamespace(returncode=0, stdout="")

    di._gsettings_run = fake_run
    try:
        assert di._install_gsettings("gnome", "ctrl+alt+space")
    finally:
        di.shutil.which, di._gsettings_run = original_which, original_run
    registry_sets = [call for call in calls if call[:3] == (
        "set", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"
    )]
    assert registry_sets and "/existing/" in registry_sets[0][3]
    assert "voice-input" in registry_sets[0][3]


def test_vanilla_hypr_lua_uses_explicit_config_home():
    old_xdg = os.environ.get("XDG_CONFIG_HOME")
    old_reload, old_hypr_reload = di._reload, hypr.reload
    try:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["XDG_CONFIG_HOME"] = temp
            path = Path(temp) / "hypr/hyprland.lua"
            path.parent.mkdir(parents=True)
            path.write_text("hl.config({})\n", encoding="utf-8")
            di._reload = lambda _command: None
            hypr.reload = lambda: None
            assert di._install_hypr("super+grave", "bottom")
            text = path.read_text(encoding="utf-8")
            assert hypr.BEGIN in text and '"SUPER + GRAVE"' in text
            assert hypr.uninstall(path=path)
            assert path.read_text(encoding="utf-8") == "hl.config({})\n"
    finally:
        di._reload, hypr.reload = old_reload, old_hypr_reload
        if old_xdg is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = old_xdg


if __name__ == "__main__":
    test_detect_popular_desktops_and_sessions()
    test_hotkey_formats()
    test_managed_block_roundtrip_preserves_user_text()
    test_partial_marker_is_never_overwritten()
    test_gsettings_list_parser()
    test_gnome_binding_commands_preserve_existing_paths()
    test_vanilla_hypr_lua_uses_explicit_config_home()
    print("test_desktop_integration OK")
