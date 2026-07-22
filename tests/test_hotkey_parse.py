"""Разбор строки бинда (без evdev)."""
from pill.hotkey import canonical_combo, parse_combo, to_pynput
from pill.ui import _qt_hotkey_combo
from PySide6.QtCore import Qt


def test_super_alt_letter():
    mods, trig = parse_combo("super+alt+d")
    assert trig == "KEY_D"
    assert ("KEY_LEFTMETA", "KEY_RIGHTMETA") in mods
    assert ("KEY_LEFTALT", "KEY_RIGHTALT") in mods


def test_aliases_and_space():
    mods, trig = parse_combo("ctrl+shift+space")
    assert trig == "KEY_SPACE"
    assert len(mods) == 2
    assert parse_combo("win+r")[0] == [("KEY_LEFTMETA", "KEY_RIGHTMETA")]
    assert parse_combo("super+`")[1] == "KEY_GRAVE"
    assert canonical_combo("win+`") == "super+grave"
    assert to_pynput("super+`") == "<cmd>+`"


def test_requires_main_key():
    for bad in ("ctrl+alt", "", "  ", "shift", "a+b", "ctrl+ctrl+a",
                "alt+not-a-key", "ctrl++a"):
        try:
            parse_combo(bad)
            raise AssertionError(f"должно было упасть: {bad!r}")
        except ValueError:
            pass


def test_qt_wayland_capture():
    mods = int((
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
    ).value)
    assert _qt_hotkey_combo(int(Qt.Key.Key_A), mods) == "ctrl+alt+a"
    assert _qt_hotkey_combo(int(Qt.Key.Key_QuoteLeft), 0) == "grave"
    assert _qt_hotkey_combo(int(Qt.Key.Key_Control), mods) is None


if __name__ == "__main__":
    test_super_alt_letter()
    test_aliases_and_space()
    test_requires_main_key()
    test_qt_wayland_capture()
    print("test_hotkey_parse OK")
