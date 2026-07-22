"""Сборка команд ввода по сессии (Wayland/X11), раннер и which замоканы."""
import os

import pill.text_injector as ti
from pill.text_injector import TextInjector


def _which(pred):
    ti.shutil.which = lambda tool: ("/usr/bin/" + tool) if pred(tool) else None


def _wayland(on):
    if on:
        os.environ["WAYLAND_DISPLAY"] = "wayland-0"
    else:
        os.environ.pop("WAYLAND_DISPLAY", None)


def test_wayland_prefers_wtype():
    _wayland(True); _which(lambda t: t in ("wtype", "ydotool"))
    assert ti._type_cmd("привет") == ["wtype", "--", "привет"]      # Unicode
    assert ti._paste_key_cmd()[0] == "wtype"


def test_wayland_fallback_ydotool():
    _wayland(True); _which(lambda t: t == "ydotool")
    assert ti._type_cmd("x") == ["ydotool", "type", "x"]


def test_x11_uses_xdotool():
    _wayland(False); _which(lambda t: t == "xdotool")
    assert ti._type_cmd("привет") == ["xdotool", "type", "--clearmodifiers", "--", "привет"]
    assert ti._paste_key_cmd() == ["xdotool", "key", "--clearmodifiers", "ctrl+v"]


def test_terminal_paste_uses_ctrl_shift_v():
    _wayland(True); _which(lambda t: t == "wtype")
    assert ti._paste_key_cmd(shift=True) == [
        "wtype", "-M", "ctrl", "-M", "shift", "v", "-m", "shift", "-m", "ctrl"
    ]


def test_wayland_keyboard_inject_calls_typer():
    _wayland(True); _which(lambda t: t == "wtype")
    calls = []
    inj = TextInjector({"input_method": "keyboard"}, runner=lambda *a, **k: calls.append(a[0]))
    assert inj.inject("тест") and calls == [["wtype", "--", "тест"]]


def test_wayland_clipboard_copies_then_pastes():
    _wayland(True); _which(lambda t: t in ("wl-copy", "wtype"))
    calls = []
    inj = TextInjector({"input_method": "clipboard"}, runner=lambda *a, **k: calls.append(a[0]))
    assert inj.inject("текст")
    assert calls[0] == ["wl-copy", "--", "текст"] and calls[1][0] == "wtype"


def test_empty_text_noop():
    calls = []
    inj = TextInjector({"input_method": "keyboard"}, runner=lambda *a, **k: calls.append(a[0]))
    assert not inj.inject("") and calls == []


if __name__ == "__main__":
    test_wayland_prefers_wtype()
    test_wayland_fallback_ydotool()
    test_x11_uses_xdotool()
    test_terminal_paste_uses_ctrl_shift_v()
    test_wayland_keyboard_inject_calls_typer()
    test_wayland_clipboard_copies_then_pastes()
    test_empty_text_noop()
    print("test_text_injector OK")
