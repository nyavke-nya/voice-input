"""Единая точка правды для путей: пользовательские данные под платформу и доступ
к ресурсам как из source checkout, так и из PyInstaller onedir (_MEIPASS).

  Linux:   XDG — config ~/.config/pill, cache/models ~/.cache/pill (без изменений)
  Windows: config  %APPDATA%\\Voice Input\\config.json
           cache/logs/models %LOCALAPPDATA%\\Voice Input\\...

Чистые функции принимают env/platform, поэтому Windows-ветку можно тестировать
на любой ОС (см. tests/test_paths.py) без разбросанных по проекту проверок
sys.frozen / os.name.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR = "Voice Input"   # каталог данных на Windows
XDG_SUB = "pill"          # каталог данных в XDG на Linux


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _is_win(platform: str | None) -> bool:
    return (platform if platform is not None else sys.platform).startswith("win")


def config_dir(env: dict | None = None, platform: str | None = None) -> Path:
    env = os.environ if env is None else env
    if _is_win(platform):
        base = env.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_DIR
    base = env.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / XDG_SUB


def data_dir(env: dict | None = None, platform: str | None = None) -> Path:
    """cache / logs / models."""
    env = os.environ if env is None else env
    if _is_win(platform):
        base = env.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP_DIR
    base = env.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / XDG_SUB


def config_path(env: dict | None = None, platform: str | None = None) -> Path:
    return config_dir(env, platform) / "config.json"


def cache_dir(env: dict | None = None, platform: str | None = None) -> Path:
    d = data_dir(env, platform)
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_dir(env: dict | None = None, platform: str | None = None) -> Path:
    d = data_dir(env, platform) / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def models_dir(env: dict | None = None, platform: str | None = None) -> Path | None:
    """Каталог кэша Whisper-моделей на Windows. None на Linux = дефолт HuggingFace
    (XDG-пути не трогаем)."""
    if not _is_win(platform):
        return None
    d = data_dir(env, platform) / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


_PKG = Path(__file__).resolve().parent  # .../pill


def resource_path(*parts: str) -> Path:
    """Путь к ресурсу пакета в обоих режимах: source checkout и onedir(_MEIPASS)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", str(_PKG.parent))) / "pill" / Path(*parts)
    return _PKG.joinpath(*parts)


def icon_path() -> Path | None:
    """voice-input.ico: рядом с ресурсами (frozen) или в packaging (source-dev)."""
    for candidate in (resource_path("voice-input.ico"),
                      _PKG.parent / "packaging" / "windows" / "voice-input.ico"):
        if candidate.is_file():
            return candidate
    return None


if __name__ == "__main__":
    # чистые функции (без mkdir) — безопасно проверять фейковыми win-путями на Linux
    win_env = {"APPDATA": r"C:\Users\A\AppData\Roaming",
               "LOCALAPPDATA": r"C:\Users\A\AppData\Local"}
    assert config_path(win_env, "win32").name == "config.json"
    assert config_dir(win_env, "win32").name == "Voice Input"
    assert "Roaming" in str(config_dir(win_env, "win32"))
    assert "Local" in str(data_dir(win_env, "win32"))
    lin_env = {"XDG_CONFIG_HOME": "/home/a/.config", "XDG_CACHE_HOME": "/home/a/.cache"}
    assert config_path(lin_env, "linux").as_posix() == "/home/a/.config/pill/config.json"
    assert data_dir(lin_env, "linux").as_posix() == "/home/a/.cache/pill"
    assert models_dir(lin_env, "linux") is None  # None-путь mkdir не вызывает
    assert resource_path("qml", "Main.qml").name == "Main.qml"
    print("paths OK")
