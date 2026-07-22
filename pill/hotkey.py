"""Глобальный хоткей — кроссплатформенно.

Linux: evdev (читает /dev/input напрямую, работает на ЛЮБОМ композиторе —
GNOME/KDE/Sway/Hyprland — нужна группа `input`). На Hyprland вместо этого обычно
используется нативный bind (pill/hypr.py), тогда evdev-слушатель не запускается,
чтобы не было двойного срабатывания.

Windows: pynput (глобальный перехват из коробки).

parse_combo — чистая функция (имена клавиш evdev строками), тестируется без evdev.
capture_once — запасной одноразовый перехват комбо через evdev/pynput.
На Wayland кнопка «Записать» безопасно ловит клавишу фокусом Qt (см. ui.py).
"""
from __future__ import annotations

import sys
import threading
import time
import re
from typing import Callable, List, Optional, Tuple

_MOD_GROUPS = {
    "ctrl": ("KEY_LEFTCTRL", "KEY_RIGHTCTRL"),
    "alt": ("KEY_LEFTALT", "KEY_RIGHTALT"),
    "shift": ("KEY_LEFTSHIFT", "KEY_RIGHTSHIFT"),
    "super": ("KEY_LEFTMETA", "KEY_RIGHTMETA"),
}
_MOD_ALIASES = {
    "ctrl": "ctrl", "control": "ctrl", "alt": "alt", "shift": "shift",
    "super": "super", "meta": "super", "win": "super",
}

_MOD_TOKEN = {
    "KEY_LEFTCTRL": "ctrl", "KEY_RIGHTCTRL": "ctrl",
    "KEY_LEFTALT": "alt", "KEY_RIGHTALT": "alt",
    "KEY_LEFTSHIFT": "shift", "KEY_RIGHTSHIFT": "shift",
    "KEY_LEFTMETA": "super", "KEY_RIGHTMETA": "super",
}

_KEY_ALIASES = {
    "`": "grave", "-": "minus", "=": "equal", "[": "leftbrace",
    "]": "rightbrace", ";": "semicolon", "'": "apostrophe", ",": "comma",
    ".": "dot", "period": "dot", "/": "slash", "\\": "backslash",
    "escape": "esc", "return": "enter", "pgup": "pageup", "pgdn": "pagedown",
    "printscreen": "sysrq",
}
_NAMED_KEYS = {
    "space": "SPACE", "enter": "ENTER", "tab": "TAB", "esc": "ESC",
    "backspace": "BACKSPACE", "delete": "DELETE", "insert": "INSERT",
    "home": "HOME", "end": "END", "pageup": "PAGEUP", "pagedown": "PAGEDOWN",
    "left": "LEFT", "right": "RIGHT", "up": "UP", "down": "DOWN",
    "capslock": "CAPSLOCK", "numlock": "NUMLOCK", "scrolllock": "SCROLLLOCK",
    "pause": "PAUSE", "sysrq": "SYSRQ", "menu": "MENU", "compose": "COMPOSE",
    "mute": "MUTE", "volumedown": "VOLUMEDOWN", "volumeup": "VOLUMEUP",
    "playpause": "PLAYPAUSE", "nextsong": "NEXTSONG", "previoussong": "PREVIOUSSONG",
}
_PUNCT_KEYS = {
    "grave": "GRAVE", "minus": "MINUS", "equal": "EQUAL",
    "leftbrace": "LEFTBRACE", "rightbrace": "RIGHTBRACE", "semicolon": "SEMICOLON",
    "apostrophe": "APOSTROPHE", "comma": "COMMA", "dot": "DOT",
    "slash": "SLASH", "backslash": "BACKSLASH",
}


def normalize_combo(combo: str) -> Tuple[List[str], str]:
    """Разобрать и канонизировать комбинацию без привязки к платформе."""
    if not isinstance(combo, str):
        raise ValueError(f"бинд должен быть строкой: {combo!r}")
    raw = combo.strip().lower()
    tokens = [token.strip() for token in raw.split("+")]
    if not raw or any(not token for token in tokens):
        raise ValueError(f"пустой или неполный бинд: {combo!r}")

    mods: List[str] = []
    keys: List[str] = []
    for token in tokens:
        if token in _MOD_ALIASES:
            mod = _MOD_ALIASES[token]
            if mod in mods:
                raise ValueError(f"модификатор повторяется: {combo!r}")
            mods.append(mod)
        else:
            keys.append(_KEY_ALIASES.get(token, token))
    if len(keys) != 1:
        raise ValueError(f"в бинде должна быть ровно одна основная клавиша: {combo!r}")

    key = keys[0]
    valid = (
        (len(key) == 1 and key.isascii() and key.isalnum())
        or key in _NAMED_KEYS
        or key in _PUNCT_KEYS
        or re.fullmatch(r"f(?:[1-9]|1[0-9]|2[0-4])", key)
        or re.fullmatch(r"kp[0-9]", key)
    )
    if not valid:
        raise ValueError(f"неизвестная основная клавиша: {key!r}")
    return mods, key


def canonical_combo(combo: str) -> str:
    mods, key = normalize_combo(combo)
    return "+".join([*mods, key])


def parse_combo(combo: str) -> Tuple[List[Tuple[str, ...]], str]:
    """'super+alt+d' -> (группы_модификаторов, 'KEY_D'). Валидация бинда."""
    mod_names, key = normalize_combo(combo)
    code = _NAMED_KEYS.get(key) or _PUNCT_KEYS.get(key) or key.upper()
    return [_MOD_GROUPS[name] for name in mod_names], f"KEY_{code}"


# ------------------------- Linux: постоянный evdev -------------------------
class HotkeyListener:
    def __init__(self, combo: str, on_trigger: Callable[[], None]):
        self.on_trigger = on_trigger
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._mods, self._trigger = parse_combo(combo)

    def set_combo(self, combo: str) -> None:
        parsed = parse_combo(combo)
        running = bool(self._thread and self._thread.is_alive())
        if running:
            self.stop()
        self._mods, self._trigger = parsed
        if running:
            self.start()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        self._thread = None

    def _run(self) -> None:
        import selectors

        try:
            from evdev import InputDevice, categorize, ecodes, list_devices
        except Exception as e:  # noqa: BLE001
            print(f"[pill] хоткей отключён (нет evdev): {e}")
            return
        kbds = []
        for path in list_devices():
            try:
                dev = InputDevice(path)
            except OSError:
                continue
            if ecodes.KEY_A in dev.capabilities().get(ecodes.EV_KEY, []):
                kbds.append(dev)
        if not kbds:
            print("[pill] клавиатуры через evdev не найдены (нужна группа input)")
            return

        name2code = {n: getattr(ecodes, n, None) for grp in self._mods for n in grp}
        trigger_code = getattr(ecodes, self._trigger, None)
        if trigger_code is None or any(code is None for code in name2code.values()):
            print(f"[pill] хоткей отключён: evdev не знает клавишу {self._trigger}")
            for dev in kbds:
                dev.close()
            return
        mod_groups = [[name2code[n] for n in grp] for grp in self._mods]

        sel = selectors.DefaultSelector()
        for dev in kbds:
            sel.register(dev, selectors.EVENT_READ)
        pressed: set = set()
        try:
            while not self._stop.is_set():
                for key, _ in sel.select(timeout=0.5):
                    try:
                        for event in key.fileobj.read():
                            if event.type != ecodes.EV_KEY:
                                continue
                            k = categorize(event)
                            if k.keystate == k.key_down:
                                pressed.add(k.scancode)
                                if k.scancode == trigger_code and all(
                                    any(c in pressed for c in grp) for grp in mod_groups
                                ):
                                    self.on_trigger()
                            elif k.keystate == k.key_up:
                                pressed.discard(k.scancode)
                    except OSError:
                        continue
        finally:
            for dev in kbds:
                try:
                    dev.close()
                except OSError:
                    pass


def capture_once(
    callback: Callable[[str], None],
    on_error: Callable[[str], None] = lambda _: None,
    timeout: float = 15.0,
) -> None:
    """Поймать следующую комбинацию; об ошибке/таймауте сообщить через on_error."""

    if sys.platform.startswith("win"):
        _capture_once_windows(callback, on_error, timeout)
        return

    def run():
        try:
            import selectors

            from evdev import InputDevice, ecodes, list_devices
        except Exception as e:  # noqa: BLE001
            on_error(f"Не удалось открыть evdev: {e}")
            return
        mod_codes = {}
        for name, friendly in _MOD_TOKEN.items():
            code = getattr(ecodes, name, None)
            if code is not None:
                mod_codes[code] = friendly
        kbds = []
        for path in list_devices():
            try:
                d = InputDevice(path)
            except OSError:
                continue
            if ecodes.KEY_A in d.capabilities().get(ecodes.EV_KEY, []):
                kbds.append(d)
        if not kbds:
            on_error("Клавиатуры через evdev не найдены; проверьте группу input")
            return
        sel = selectors.DefaultSelector()
        for d in kbds:
            sel.register(d, selectors.EVENT_READ)
        pressed = set()
        deadline = time.monotonic() + max(1.0, timeout)
        try:
            while time.monotonic() < deadline:
                got = sel.select(timeout=min(0.5, max(0.0, deadline - time.monotonic())))
                for key, _ in got:
                    try:
                        events = list(key.fileobj.read())
                    except OSError:
                        events = []
                    for event in events:
                        if event.type != ecodes.EV_KEY:
                            continue
                        code, val = event.code, event.value
                        if val == 1:
                            if code in mod_codes:
                                pressed.add(code)
                                continue
                            name = ecodes.KEY.get(code)
                            if isinstance(name, (list, tuple)):
                                name = name[0]
                            if not name or not str(name).startswith("KEY_"):
                                continue
                            token = str(name)[4:].lower()
                            mods = [m for m in ("ctrl", "alt", "super", "shift")
                                    if any(mod_codes[c] == m for c in pressed)]
                            try:
                                callback(canonical_combo("+".join(mods + [token])))
                            except ValueError:
                                continue
                            return
                        elif val == 0:
                            pressed.discard(code)
        finally:
            sel.close()
            for d in kbds:
                try:
                    d.close()
                except OSError:
                    pass
        on_error("Время ожидания комбинации истекло")

    threading.Thread(target=run, daemon=True).start()


def _capture_once_windows(callback, on_error, timeout: float) -> None:
    def run():
        try:
            from pynput import keyboard
        except Exception as e:  # noqa: BLE001
            on_error(f"Не удалось открыть pynput: {e}")
            return

        pressed: set[str] = set()

        def token(key):
            name = getattr(key, "name", "") or ""
            for prefix, mod in (("ctrl", "ctrl"), ("alt", "alt"),
                                ("shift", "shift"), ("cmd", "super")):
                if name == prefix or name.startswith(prefix + "_"):
                    return mod, True
            char = getattr(key, "char", None)
            return (char or name).lower(), False

        def on_press(key):
            value, is_mod = token(key)
            if is_mod:
                pressed.add(value)
                return None
            try:
                callback(canonical_combo("+".join([
                    *(m for m in ("ctrl", "alt", "super", "shift") if m in pressed), value
                ])))
            except ValueError:
                return None
            return False

        def on_release(key):
            value, is_mod = token(key)
            if is_mod:
                pressed.discard(value)

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        listener.join(timeout=max(1.0, timeout))
        if listener.is_alive():
            listener.stop()
            on_error("Время ожидания комбинации истекло")

    threading.Thread(target=run, daemon=True).start()


# ------------------------- Windows: pynput -------------------------
_PYNPUT_MOD = {"ctrl": "<ctrl>", "alt": "<alt>", "shift": "<shift>", "super": "<cmd>"}
_PYNPUT_KEY = {"space": "<space>", "grave": "`", "enter": "<enter>", "tab": "<tab>",
               "esc": "<esc>", "backspace": "<backspace>", "delete": "<delete>"}
_PUNCT_TEXT = {"minus": "-", "equal": "=", "leftbrace": "[", "rightbrace": "]",
               "semicolon": ";", "apostrophe": "'", "comma": ",", "dot": ".",
               "slash": "/", "backslash": "\\"}


def to_pynput(combo: str) -> str:
    """'ctrl+alt+d' -> '<ctrl>+<alt>+d' для pynput.GlobalHotKeys."""
    mods, key = normalize_combo(combo)
    trigger = _PYNPUT_KEY.get(key) or _PUNCT_TEXT.get(key)
    if trigger is None:
        trigger = key if len(key) == 1 else f"<{key}>"
    return "+".join([*(_PYNPUT_MOD[mod] for mod in mods), trigger])


class _WinHotkey:
    def __init__(self, combo: str, on_trigger: Callable[[], None]):
        self._cb = on_trigger
        self._combo = combo
        self._h = None

    def start(self) -> None:
        from pynput import keyboard

        self._h = keyboard.GlobalHotKeys({to_pynput(self._combo): self._cb})
        self._h.start()

    def set_combo(self, combo: str) -> None:
        self._combo = combo
        if self._h is not None:
            self.stop()
            self.start()

    def stop(self) -> None:
        if self._h is not None:
            self._h.stop()
            self._h = None


def make_listener(combo: str, on_trigger: Callable[[], None]):
    """Слушатель хоткея под текущую платформу."""
    if sys.platform.startswith("win"):
        return _WinHotkey(combo, on_trigger)
    return HotkeyListener(combo, on_trigger)


if __name__ == "__main__":
    mods, trig = parse_combo("super+alt+d")
    assert trig == "KEY_D"
    assert ("KEY_LEFTMETA", "KEY_RIGHTMETA") in mods and ("KEY_LEFTALT", "KEY_RIGHTALT") in mods
    assert parse_combo("ctrl+shift+space")[1] == "KEY_SPACE"
    assert to_pynput("ctrl+alt+d") == "<ctrl>+<alt>+d"
    assert to_pynput("super+space") == "<cmd>+<space>"
    for bad in ("ctrl+alt", "", "shift"):
        try:
            parse_combo(bad)
            raise AssertionError(f"должно было упасть: {bad!r}")
        except ValueError:
            pass
    print("hotkey OK")
