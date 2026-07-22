"""Сборка команд ввода по сессии (Wayland/X11), раннер и which замоканы."""
import os

import pill.text_injector as ti
from pill.text_injector import TextInjector


def _which(pred):
    ti.shutil.which = lambda tool: ("/usr/bin/" + tool) if pred(tool) else None


def _wayland(on):
    if on:
        os.environ["WAYLAND_DISPLAY"] = "wayland-0"
        os.environ.pop("DISPLAY", None)
    else:
        os.environ.pop("WAYLAND_DISPLAY", None)
        os.environ["DISPLAY"] = ":0"


def test_wayland_prefers_wtype():
    _wayland(True)
    _which(lambda t: t in ("wtype", "ydotool"))
    assert ti._type_cmd("привет") == ["wtype", "-d", "8", "--", "привет"]
    assert ti._paste_key_cmd()[0] == "wtype"


def test_wayland_fallback_ydotool():
    _wayland(True)
    _which(lambda t: t == "ydotool")
    assert ti._type_cmd("x") == ["ydotool", "type", "x"]


def test_wayland_ydotool_uses_clipboard_for_unicode():
    _wayland(True)
    _which(lambda t: t in ("ydotool", "wl-copy"))
    calls = []
    inj = TextInjector({"input_method": "keyboard"}, runner=lambda *a, **k: calls.append(a[0]))
    assert inj.inject("привет")
    assert calls[0][0] == "wl-copy" and calls[1][0] == "ydotool"


def test_x11_uses_xdotool():
    _wayland(False)
    _which(lambda t: t == "xdotool")
    assert ti._type_cmd("привет") == [
        "xdotool", "type", "--delay", "8", "--clearmodifiers", "--", "привет",
    ]
    assert ti._paste_key_cmd() == ["xdotool", "key", "--clearmodifiers", "ctrl+v"]


def test_terminal_paste_uses_ctrl_shift_v():
    _wayland(True)
    _which(lambda t: t == "wtype")
    assert ti._paste_key_cmd(shift=True) == [
        "wtype", "-M", "ctrl", "-M", "shift", "v", "-m", "shift", "-m", "ctrl"
    ]


def test_wayland_keyboard_inject_calls_typer():
    _wayland(True)
    _which(lambda t: t == "wtype")
    calls = []
    inj = TextInjector({"input_method": "keyboard"}, runner=lambda *a, **k: calls.append(a[0]))
    assert inj.inject("тест") and calls == [["wtype", "-d", "8", "--", "тест"]]


def test_wayland_clipboard_copies_then_pastes():
    _wayland(True)
    _which(lambda t: t in ("wl-copy", "wtype"))
    calls = []
    inj = TextInjector({"input_method": "clipboard"}, runner=lambda *a, **k: calls.append(a[0]))
    assert inj.inject("текст")
    assert calls[0] == ["wl-copy", "--", "текст"] and calls[1][0] == "wtype"


def test_failed_wtype_falls_back_to_clipboard_and_ydotool():
    _wayland(True)
    _which(lambda t: t in ("wtype", "ydotool", "wl-copy"))
    calls = []

    def runner(command, **_kwargs):
        calls.append(command)
        if command[0] == "wtype":
            raise ti.subprocess.CalledProcessError(1, command)

    inj = TextInjector({"input_method": "keyboard"}, runner=runner)
    assert inj.inject("текст")
    assert [command[0] for command in calls] == ["wtype", "wl-copy", "ydotool"]


def test_dotool_pastes_when_ydotool_is_unavailable():
    _wayland(True)
    _which(lambda t: t in ("dotool", "wl-copy"))
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs.get("input")))

    inj = TextInjector({"input_method": "keyboard"}, runner=runner)
    assert inj.inject("текст")
    assert calls[0][0] == ["wl-copy", "--", "текст"]
    assert calls[1] == (["dotool"], b"key ctrl+v\n")


def test_empty_text_noop():
    calls = []
    inj = TextInjector({"input_method": "keyboard"}, runner=lambda *a, **k: calls.append(a[0]))
    assert not inj.inject("") and calls == []


if __name__ == "__main__":
    test_wayland_prefers_wtype()
    test_wayland_fallback_ydotool()
    test_wayland_ydotool_uses_clipboard_for_unicode()
    test_x11_uses_xdotool()
    test_terminal_paste_uses_ctrl_shift_v()
    test_wayland_keyboard_inject_calls_typer()
    test_wayland_clipboard_copies_then_pastes()
    test_failed_wtype_falls_back_to_clipboard_and_ydotool()
    test_dotool_pastes_when_ydotool_is_unavailable()
    test_empty_text_noop()
    print("test_text_injector OK")
