"""Вставка распознанного текста в активное поле — кроссплатформенно.

Выбор бэкенда по окружению (никакой лишней настройки от пользователя):

  Wayland                     keyboard: wtype  ·  fallback: wl-copy + ydotool/dotool
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
import time
from pathlib import Path
from typing import List

_TERMINALS = {
    "foot", "kitty", "alacritty", "wezterm", "org.wezfurlong.wezterm",
    "konsole", "gnome-terminal-server", "org.gnome.terminal",
    "com.mitchellh.ghostty", "ghostty", "org.gnome.ptyxis", "ptyxis",
    "org.gnome.console", "kgx",
    "xterm", "st", "urxvt",
}


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def _is_wayland() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY"))


def _is_x11() -> bool:
    return bool(os.environ.get("DISPLAY")) and not _is_wayland()


def _have(tool: str) -> bool:
    return shutil.which(tool) is not None


def _win_clipboard_set(text: str) -> None:
    """Положить Unicode-текст в буфер Windows через WinAPI (CF_UNICODETEXT).

    Через ctypes, а не Qt: инъекция идёт из аудиопотока, а QClipboard небезопасен
    вне GUI-потока."""
    import ctypes
    from ctypes import wintypes

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]

    data = text.encode("utf-16-le") + b"\x00\x00"
    if not user32.OpenClipboard(None):
        raise OSError("OpenClipboard не удался")
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            raise OSError("GlobalAlloc не удался")
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            raise OSError("GlobalLock не удался")
        ctypes.memmove(pointer, data, len(data))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            raise OSError("SetClipboardData не удался")
    finally:
        user32.CloseClipboard()


def _ensure_ydotoold() -> None:
    """Start ydotoold lazily on non-systemd desktops and custom init systems."""
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/voice-input-{os.getuid()}"
    socket_path = os.environ.get("YDOTOOL_SOCKET") or str(Path(runtime) / ".ydotool_socket")
    if Path(socket_path).exists() or not _have("ydotoold"):
        return
    try:
        Path(runtime).mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError:
        return
    os.environ["YDOTOOL_SOCKET"] = socket_path
    try:
        subprocess.Popen(
            ["ydotoold", "--socket-path", socket_path, "--socket-perm", "0600"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return
    for _ in range(10):
        if Path(socket_path).exists():
            break
        time.sleep(0.05)


def _type_cmd(text: str) -> List[str]:
    """Команда «набрать текст» для текущей сессии Linux."""
    if _is_wayland():
        if _have("wtype"):
            return ["wtype", "--", text]           # Unicode (кириллица)
        if _have("ydotool") and text.isascii():
            return ["ydotool", "type", text]        # uinput-фолбэк, без кириллицы
        raise RuntimeError("для Unicode на Wayland нужен clipboard fallback")
    if not _is_x11():
        raise RuntimeError("графическая сессия Wayland/X11 не найдена")
    # X11
    if _have("xdotool"):
        return ["xdotool", "type", "--clearmodifiers", "--", text]  # Unicode
    if _have("ydotool"):
        return ["ydotool", "type", text]
    raise RuntimeError("для X11 нужен xdotool (или ydotool); поставьте xdotool")


def _paste_key_cmd(shift: bool = False, prefer_ydotool: bool = False) -> List[str]:
    """Команда вставки: Ctrl+V, а для терминалов Ctrl+Shift+V."""
    if _is_wayland():
        if _have("wtype") and not prefer_ydotool:
            if shift:
                return ["wtype", "-M", "ctrl", "-M", "shift", "v",
                        "-m", "shift", "-m", "ctrl"]
            return ["wtype", "-M", "ctrl", "v", "-m", "ctrl"]
        if _have("ydotool"):
            if shift:
                return ["ydotool", "key", "29:1", "42:1", "47:1", "47:0", "42:0", "29:0"]
            return ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"]  # 29=Ctrl 47=V
        if _have("dotool"):
            return ["dotool"]
    else:
        if _have("xdotool"):
            return ["xdotool", "key", "--clearmodifiers", "ctrl+shift+v" if shift else "ctrl+v"]
        if _have("ydotool"):
            if shift:
                return ["ydotool", "key", "29:1", "42:1", "47:1", "47:0", "42:0", "29:0"]
            return ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"]
        if _have("dotool"):
            return ["dotool"]
    raise RuntimeError("нет инструмента для эмуляции Ctrl+V")


def _terminal_name(value: object) -> bool:
    app_id = str(value or "").lower()
    return app_id in _TERMINALS or any(app_id.endswith("." + name) for name in _TERMINALS)


def _sway_focused(node: object) -> object:
    if not isinstance(node, dict):
        return None
    if node.get("focused"):
        props = node.get("window_properties") or {}
        return node.get("app_id") or props.get("class") or node.get("name")
    for child in [*node.get("nodes", []), *node.get("floating_nodes", [])]:
        found = _sway_focused(child)
        if found:
            return found
    return None


def _active_app_is_terminal() -> bool:
    if not _is_wayland():
        if not _have("xdotool"):
            return False
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowclassname"],
                capture_output=True, text=True, timeout=0.5, check=False,
            )
            return result.returncode == 0 and _terminal_name(result.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            return False
    command = None
    if _have("hyprctl") and os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        command = ["hyprctl", "-j", "activewindow"]
    elif _have("swaymsg") and os.environ.get("SWAYSOCK"):
        command = ["swaymsg", "-t", "get_tree", "-r"]
    if command is None:
        return False
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=0.5, check=False,
        )
        data = json.loads(result.stdout) if result.returncode == 0 else {}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return False
    if command[0] == "swaymsg":
        return _terminal_name(_sway_focused(data))
    return _terminal_name(data.get("class") or data.get("initialClass"))


class TextInjector:
    def __init__(self, cfg: dict, runner=subprocess.run):
        self.cfg = cfg
        self._run = runner  # инъекция зависимости ради тестов
        self.last_error = ""

    def _execute(self, command: List[str], **kwargs):
        if command and command[0] == "ydotool" and self._run is subprocess.run:
            _ensure_ydotoold()
        return self._run(command, **kwargs)

    def inject(self, text: str) -> bool:
        self.last_error = ""
        if not text:
            return False
        first_error = None
        try:
            if _is_windows():
                return self._inject_windows(text)
            if self.cfg.get("input_method", "keyboard") == "clipboard":
                return self._inject_clipboard(text)
            self._execute(_type_cmd(text), check=True)
            return True
        except (subprocess.SubprocessError, OSError, RuntimeError, ImportError) as e:
            first_error = e
        # wtype может быть установлен, но недоступен в GNOME/KWin Wayland.
        # Unicode через clipboard + uinput покрывает больше compositor'ов.
        try:
            return self._inject_clipboard(text, prefer_ydotool=_is_wayland())
        except (subprocess.SubprocessError, OSError, RuntimeError) as fallback_error:
            self.last_error = f"{first_error}; clipboard fallback: {fallback_error}"
            print(f"[voice-input] инъекция не удалась: {self.last_error}")
            return False

    def _inject_clipboard(self, text: str, prefer_ydotool: bool = False) -> bool:
        if _is_wayland():
            if not _have("wl-copy"):
                raise RuntimeError("wl-copy не найден (установите wl-clipboard)")
            self._execute(["wl-copy", "--", text], check=True)
        elif _have("xclip"):
            self._execute(["xclip", "-selection", "clipboard"], input=text.encode(), check=True)
        elif _have("xsel"):
            self._execute(["xsel", "-b", "-i"], input=text.encode(), check=True)
        else:
            raise RuntimeError("нет wl-copy/xclip/xsel для буфера обмена")
        shift = _active_app_is_terminal()
        command = _paste_key_cmd(shift=shift, prefer_ydotool=prefer_ydotool)
        kwargs = {"input": ("key ctrl+shift+v\n" if shift else "key ctrl+v\n").encode()} \
            if command[0] == "dotool" else {}
        try:
            self._execute(command, check=True, **kwargs)
        except (subprocess.SubprocessError, OSError):
            if (not _is_wayland() or command[0] != "wtype"
                    or not (_have("ydotool") or _have("dotool"))):
                raise
            fallback = _paste_key_cmd(shift=shift, prefer_ydotool=True)
            fallback_kwargs = {
                "input": ("key ctrl+shift+v\n" if shift else "key ctrl+v\n").encode()
            } if fallback[0] == "dotool" else {}
            self._execute(fallback, check=True, **fallback_kwargs)
        return True

    def _inject_windows(self, text: str) -> bool:
        if self.cfg.get("input_method", "keyboard") == "clipboard":
            return self._inject_windows_clipboard(text)
        from pynput.keyboard import Controller  # keyboard: Unicode-набор, фокус не нужен

        Controller().type(text)
        return True

    def _inject_windows_clipboard(self, text: str) -> bool:
        from pynput.keyboard import Controller, Key

        _win_clipboard_set(text)  # Win32 clipboard (потокобезопасно, без Qt)
        keyboard = Controller()
        with keyboard.pressed(Key.ctrl):
            keyboard.press("v")
            keyboard.release("v")
        return True

    @staticmethod
    def diagnostics() -> str:
        if _is_windows():
            try:
                import pynput  # noqa: F401
                return "windows: pynput=ok"
            except ImportError:
                return "windows: pynput=НЕТ (pip install pynput)"
        sess = "wayland" if _is_wayland() else ("x11" if _is_x11() else "headless")
        tools = ("wtype", "ydotool", "dotool", "wl-copy") if _is_wayland() else ("xdotool", "xclip", "xsel", "ydotool", "dotool")
        state = " ".join(f"{t}={'ok' if _have(t) else 'нет'}" for t in tools)
        return f"{sess}: {state}"


if __name__ == "__main__":
    # self-check: команды осмысленны для текущей сессии
    if not _is_windows():
        try:
            cmd = _type_cmd("привет")
            assert cmd[0] in ("wtype", "xdotool", "ydotool"), cmd
        except RuntimeError:
            assert _is_wayland() and _have("wl-copy") and (_have("ydotool") or _have("dotool"))
        assert _paste_key_cmd()[0] in ("wtype", "xdotool", "ydotool", "dotool")
    calls = []
    inj = TextInjector({"input_method": "keyboard"}, runner=lambda *a, **k: calls.append(a[0]))
    if not _is_windows():
        assert inj.inject("тест") and calls
    assert not inj.inject(""), "пустой текст не вставляем"
    print("text_injector OK:", TextInjector.diagnostics())
