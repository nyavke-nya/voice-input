"""Вставка распознанного текста в активное поле — кроссплатформенно.

Выбор бэкенда по окружению (никакой лишней настройки от пользователя):

  Wayland (wlroots: Hyprland/Sway)  keyboard: wtype  ·  clipboard: wl-copy + paste
  X11 (любой DE)                    keyboard: xdotool ·  clipboard: xclip/xsel + Ctrl+V
  Windows                           keyboard/clipboard: pynput (Unicode-набор)
  терминалы получают Ctrl+Shift+V; прочие приложения — Ctrl+V.
  Фолбэк без юникод-тула — ydotool (uinput, кириллицу не осилит).

Команды-строители — чистые функции, проверяются в тестах без реального ввода.
"""
from __future__ import annotations

import os
import json
import shutil
import subprocess
import sys
from typing import List

_TERMINALS = {
    "foot", "kitty", "alacritty", "wezterm", "org.wezfurlong.wezterm",
    "konsole", "gnome-terminal-server", "org.gnome.terminal",
    "com.mitchellh.ghostty", "ghostty",
    "xterm", "st", "urxvt",
}


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def _is_wayland() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY"))


def _have(tool: str) -> bool:
    return shutil.which(tool) is not None


def _type_cmd(text: str) -> List[str]:
    """Команда «набрать текст» для текущей сессии Linux."""
    if _is_wayland():
        if _have("wtype"):
            return ["wtype", "--", text]           # Unicode (кириллица)
        if _have("ydotool"):
            return ["ydotool", "type", text]        # uinput-фолбэк, без кириллицы
        raise RuntimeError("для Wayland нужен wtype (или ydotool); поставьте wtype")
    # X11
    if _have("xdotool"):
        return ["xdotool", "type", "--clearmodifiers", "--", text]  # Unicode
    if _have("ydotool"):
        return ["ydotool", "type", text]
    raise RuntimeError("для X11 нужен xdotool (или ydotool); поставьте xdotool")


def _paste_key_cmd(shift: bool = False) -> List[str]:
    """Команда вставки: Ctrl+V, а для терминалов Ctrl+Shift+V."""
    if _is_wayland():
        if _have("wtype"):
            if shift:
                return ["wtype", "-M", "ctrl", "-M", "shift", "v",
                        "-m", "shift", "-m", "ctrl"]
            return ["wtype", "-M", "ctrl", "v", "-m", "ctrl"]
        if _have("ydotool"):
            if shift:
                return ["ydotool", "key", "29:1", "42:1", "47:1", "47:0", "42:0", "29:0"]
            return ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"]  # 29=Ctrl 47=V
    else:
        if _have("xdotool"):
            return ["xdotool", "key", "--clearmodifiers", "ctrl+shift+v" if shift else "ctrl+v"]
        if _have("ydotool"):
            if shift:
                return ["ydotool", "key", "29:1", "42:1", "47:1", "47:0", "42:0", "29:0"]
            return ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"]
    raise RuntimeError("нет инструмента для эмуляции Ctrl+V")


def _active_app_is_terminal() -> bool:
    if not _is_wayland() or not _have("hyprctl"):
        return False
    try:
        result = subprocess.run(
            ["hyprctl", "-j", "activewindow"], capture_output=True, text=True,
            timeout=0.5, check=False,
        )
        data = json.loads(result.stdout) if result.returncode == 0 else {}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return False
    app_id = str(data.get("class") or data.get("initialClass") or "").lower()
    return app_id in _TERMINALS or any(app_id.endswith("." + name) for name in _TERMINALS)


class TextInjector:
    def __init__(self, cfg: dict, runner=subprocess.run):
        self.cfg = cfg
        self._run = runner  # инъекция зависимости ради тестов
        self.last_error = ""

    def inject(self, text: str) -> bool:
        self.last_error = ""
        if not text:
            return False
        try:
            if _is_windows():
                return self._inject_windows(text)
            if self.cfg.get("input_method", "keyboard") == "clipboard":
                return self._inject_clipboard(text)
            self._run(_type_cmd(text), check=True)
            return True
        except (subprocess.SubprocessError, OSError, RuntimeError, ImportError) as e:
            self.last_error = str(e)
            print(f"[pill] инъекция не удалась: {e}")
            return False

    def _inject_clipboard(self, text: str) -> bool:
        if _is_wayland():
            if not _have("wl-copy"):
                raise RuntimeError("wl-copy не найден (установите wl-clipboard)")
            self._run(["wl-copy", "--", text], check=True)
        elif _have("xclip"):
            self._run(["xclip", "-selection", "clipboard"], input=text.encode(), check=True)
        elif _have("xsel"):
            self._run(["xsel", "-b", "-i"], input=text.encode(), check=True)
        else:
            raise RuntimeError("нет wl-copy/xclip/xsel для буфера обмена")
        self._run(_paste_key_cmd(shift=_active_app_is_terminal()), check=True)
        return True

    def _inject_windows(self, text: str) -> bool:
        from pynput.keyboard import Controller  # Windows: Unicode-набор, фокус не нужен

        Controller().type(text)
        return True

    @staticmethod
    def diagnostics() -> str:
        if _is_windows():
            try:
                import pynput  # noqa: F401
                return "windows: pynput=ok"
            except ImportError:
                return "windows: pynput=НЕТ (pip install pynput)"
        sess = "wayland" if _is_wayland() else "x11"
        tools = ("wtype", "ydotool", "wl-copy") if _is_wayland() else ("xdotool", "xclip", "xsel", "ydotool")
        state = " ".join(f"{t}={'ok' if _have(t) else 'нет'}" for t in tools)
        return f"{sess}: {state}"


if __name__ == "__main__":
    # self-check: команды осмысленны для текущей сессии
    if not _is_windows():
        cmd = _type_cmd("привет")
        assert cmd[0] in ("wtype", "xdotool", "ydotool"), cmd
        assert _paste_key_cmd()[0] in ("wtype", "xdotool", "ydotool")
    calls = []
    inj = TextInjector({"input_method": "keyboard"}, runner=lambda *a, **k: calls.append(a[0]))
    if not _is_windows():
        assert inj.inject("тест") and calls
    assert not inj.inject(""), "пустой текст не вставляем"
    print("text_injector OK:", TextInjector.diagnostics())
