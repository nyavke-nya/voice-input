"""Пути под платформу и формат хоткея для Windows — проверяются на любой ОС,
т.к. чистые функции принимают env/platform (Windows-ветка без Windows-машины)."""
import tempfile
from pathlib import Path

from pill import paths
from pill.hotkey import to_pynput

WIN = {"APPDATA": r"C:\Users\A\AppData\Roaming",
       "LOCALAPPDATA": r"C:\Users\A\AppData\Local"}
LIN = {"XDG_CONFIG_HOME": "/home/a/.config", "XDG_CACHE_HOME": "/home/a/.cache"}


def test_windows_paths():
    assert paths.config_path(WIN, "win32").name == "config.json"
    assert paths.config_dir(WIN, "win32").name == "Voice Input"
    assert "Roaming" in str(paths.config_dir(WIN, "win32"))    # config -> APPDATA
    assert "Local" in str(paths.data_dir(WIN, "win32"))        # cache/logs/models -> LOCALAPPDATA


def test_linux_paths_unchanged():
    assert paths.config_path(LIN, "linux").as_posix() == "/home/a/.config/pill/config.json"
    assert paths.data_dir(LIN, "linux").as_posix() == "/home/a/.cache/pill"
    assert paths.models_dir(LIN, "linux") is None  # Linux = дефолт HuggingFace


def test_models_dir_windows_created():
    with tempfile.TemporaryDirectory() as d:
        env = {"LOCALAPPDATA": d}
        got = paths.models_dir(env, "win32")
        assert got is not None and got.is_dir()
        assert got == Path(d) / "Voice Input" / "models"


def test_resources_present_in_checkout():
    assert paths.resource_path("qml", "Main.qml").is_file()
    for font in ("AdwaitaSans-Regular.ttf", "AdwaitaMono-Regular.ttf"):
        assert paths.resource_path("qml", "fonts", font).is_file()


def test_windows_hotkey_format():
    assert to_pynput("ctrl+alt+d") == "<ctrl>+<alt>+d"
    assert to_pynput("super+space") == "<cmd>+<space>"
    assert to_pynput("grave") == "`"


if __name__ == "__main__":
    test_windows_paths()
    test_linux_paths_unchanged()
    test_models_dir_windows_created()
    test_resources_present_in_checkout()
    test_windows_hotkey_format()
    print("test_paths OK")
