"""Нативный hotkey там, где он безопасно настраивается; evdev — общий fallback.

Файл не пытается знать каждый Linux desktop. Он распознаёт популярные WM/DE,
добавляет отдельный управляемый блок в текстовые конфиги и никогда не
перезаписывает пользовательский конфиг целиком. Неизвестная среда получает
XDG-autostart из install.sh и desktop-independent listener из hotkey.py.
"""
from __future__ import annotations

import argparse
import ast
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from . import hypr
from .hotkey import normalize_combo

BEGIN = "# >>> voice-input managed integration >>>"
END = "# <<< voice-input managed integration <<<"


@dataclass(frozen=True)
class DesktopInfo:
    desktop: str
    session: str

    @property
    def label(self) -> str:
        return f"{self.desktop} ({self.session})"


def _config_home(env: Optional[Mapping[str, str]] = None) -> Path:
    env = os.environ if env is None else env
    return Path(env.get("XDG_CONFIG_HOME") or Path(env.get("HOME") or Path.home()) / ".config")


def detect(env: Optional[Mapping[str, str]] = None) -> DesktopInfo:
    """Определить текущую графическую среду только по стандартному окружению."""
    env = os.environ if env is None else env
    forced = env.get("VOICE_INPUT_DESKTOP", "").strip().lower()
    raw = ":".join(
        env.get(name, "")
        for name in ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP", "DESKTOP_SESSION")
    ).lower()
    tokens = [part for part in raw.replace("-", ":").replace("_", ":").split(":") if part]
    words = set(tokens)

    if forced:
        desktop = forced
    elif env.get("HYPRLAND_INSTANCE_SIGNATURE") or "hyprland" in words:
        desktop = "hyprland"
    elif env.get("SWAYSOCK") or "sway" in words:
        desktop = "sway"
    elif env.get("I3SOCK") or "i3" in words:
        desktop = "i3"
    elif "gnome" in words:
        desktop = "gnome"
    elif "cinnamon" in words or "x-cinnamon" in raw:
        desktop = "cinnamon"
    elif "xfce" in words:
        desktop = "xfce"
    elif "kde" in words or "plasma" in words:
        desktop = "kde"
    elif "mate" in words:
        desktop = "mate"
    elif "lxqt" in words:
        desktop = "lxqt"
    elif "lxde" in words:
        desktop = "lxde"
    elif "budgie" in words:
        desktop = "budgie"
    else:
        desktop = tokens[0] if tokens else "generic"

    session = env.get("XDG_SESSION_TYPE", "").strip().lower()
    if not session:
        session = "wayland" if env.get("WAYLAND_DISPLAY") else ("x11" if env.get("DISPLAY") else "unknown")
    return DesktopInfo(desktop, session)


def _command(*args: str) -> str:
    root = Path(__file__).resolve().parent.parent
    wrapper = root / "voice-input"
    if wrapper.exists():
        return shlex.join([str(wrapper), *args])
    return shlex.join(["env", f"PYTHONPATH={root}", str(root / ".venv/bin/python"), "-m", "pill", *args])


def _backup_once(path: Path) -> None:
    backup = path.with_name(path.name + ".voice-input-before-install.bak")
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)


def _replace_block(path: Path, block: str) -> bool:
    """Добавить/заменить свой блок. Частичные маркеры считаются ошибкой."""
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"[voice-input] не удалось прочитать {path}: {e}")
        return False
    has_begin, has_end = BEGIN in text, END in text
    if has_begin != has_end:
        print(f"[voice-input] не трогаю {path}: найден только один маркер Voice Input")
        return False
    if has_begin:
        start, end = text.index(BEGIN), text.index(END)
        if end < start:
            print(f"[voice-input] не трогаю {path}: маркеры Voice Input переставлены")
            return False
        updated = text[:start] + block + text[end + len(END):]
    else:
        updated = text.rstrip() + "\n\n" + block + "\n"
    if updated == text:
        return True
    try:
        _backup_once(path)
        path.write_text(updated, encoding="utf-8")
    except OSError as e:
        print(f"[voice-input] не удалось обновить {path}: {e}")
        return False
    return True


def _remove_block(path: Path) -> bool:
    if not path.exists():
        return True
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"[voice-input] не удалось прочитать {path}: {e}")
        return False
    has_begin, has_end = BEGIN in text, END in text
    if not has_begin and not has_end:
        return True
    if has_begin != has_end or text.index(END) < text.index(BEGIN):
        print(f"[voice-input] не трогаю {path}: повреждены маркеры Voice Input")
        return False
    start, end = text.index(BEGIN), text.index(END) + len(END)
    updated = (text[:start].rstrip() + "\n" + text[end:].lstrip("\n")).lstrip("\n")
    try:
        path.write_text(updated, encoding="utf-8")
    except OSError as e:
        print(f"[voice-input] не удалось обновить {path}: {e}")
        return False
    return True


_KEYSYM = {
    "grave": "grave", "minus": "minus", "equal": "equal",
    "leftbrace": "bracketleft", "rightbrace": "bracketright",
    "semicolon": "semicolon", "apostrophe": "apostrophe", "comma": "comma",
    "dot": "period", "slash": "slash", "backslash": "backslash",
    "space": "space", "enter": "Return", "esc": "Escape",
    "pageup": "Page_Up", "pagedown": "Page_Down",
    "tab": "Tab", "backspace": "BackSpace", "delete": "Delete",
    "insert": "Insert", "home": "Home", "end": "End",
    "left": "Left", "right": "Right", "up": "Up", "down": "Down",
    "capslock": "Caps_Lock", "numlock": "Num_Lock",
    "scrolllock": "Scroll_Lock", "pause": "Pause", "sysrq": "Print",
    "menu": "Menu", "compose": "Multi_key", "mute": "XF86AudioMute",
    "volumedown": "XF86AudioLowerVolume", "volumeup": "XF86AudioRaiseVolume",
    "playpause": "XF86AudioPlay", "nextsong": "XF86AudioNext",
    "previoussong": "XF86AudioPrev",
}


def to_i3(combo: str) -> str:
    mods, key = normalize_combo(combo)
    names = {"ctrl": "Ctrl", "alt": "Mod1", "shift": "Shift", "super": "Mod4"}
    keysym = _KEYSYM.get(key, key.upper() if key.startswith("f") else key)
    return "+".join([*(names[m] for m in mods), keysym])


def to_gsettings(combo: str) -> str:
    mods, key = normalize_combo(combo)
    names = {"ctrl": "<Control>", "alt": "<Alt>", "shift": "<Shift>", "super": "<Super>"}
    return "".join(names[m] for m in mods) + _KEYSYM.get(key, key)


def _legacy_hypr_block(combo: str) -> str:
    mods, key = normalize_combo(combo)
    mod_names = {"ctrl": "CTRL", "alt": "ALT", "shift": "SHIFT", "super": "SUPER"}
    hypr_key = _KEYSYM.get(key, key.upper())
    return "\n".join([
        BEGIN,
        "# Managed by Voice Input. Change the hotkey in the app settings.",
        f"exec-once = {_command()}",
        f"bindr = {' '.join(mod_names[m] for m in mods)}, {hypr_key}, exec, {_command('--toggle')}",
        "windowrulev2 = float,class:^(pill)$",
        "windowrulev2 = pin,class:^(pill)$",
        "windowrulev2 = noinitialfocus,class:^(pill)$",
        "windowrulev2 = noborder,class:^(pill)$",
        "windowrulev2 = size 400 960,class:^(pill)$",
        END,
    ])


def _sway_block(combo: str, x11: bool = False) -> str:
    selector = 'class="^pill$"' if x11 else 'app_id="^pill$"'
    return "\n".join([
        BEGIN,
        "# Managed by Voice Input. Change the hotkey in the app settings.",
        f"exec {_command()}",
        f"bindsym --release {to_i3(combo)} exec {_command('--toggle')}",
        f"for_window [{selector}] floating enable, sticky enable, border pixel 0",
        END,
    ])


def _reload(command: list[str]) -> None:
    if shutil.which(command[0]):
        subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _hypr_paths() -> tuple[Path, Path, Path]:
    cfg = _config_home()
    return cfg / "caelestia/hypr-user.lua", cfg / "hypr/hyprland.lua", cfg / "hypr/hyprland.conf"


def _install_hypr(combo: str, position: str) -> bool:
    caelestia, main_lua, legacy = _hypr_paths()
    use_caelestia = caelestia.exists() and main_lua.exists()
    if use_caelestia:
        try:
            entry = main_lua.read_text(encoding="utf-8")
            use_caelestia = "hypr-user" in entry and "caelestia" in entry
        except OSError:
            use_caelestia = False
    lua = caelestia if use_caelestia else main_lua
    if lua.exists():
        _backup_once(lua)
        return hypr.install(combo, position, path=lua)
    if legacy.exists() and _replace_block(legacy, _legacy_hypr_block(combo)):
        _reload(["hyprctl", "reload"])
        return True
    return False


def _gsettings_run(*args: str):
    try:
        return subprocess.run(
            ["gsettings", *args], capture_output=True, text=True, timeout=3, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _gsettings_spec(desktop: str) -> Optional[tuple[str, str, str]]:
    if desktop != "gnome":
        return None
    parent = "org.gnome.settings-daemon.plugins.media-keys"
    custom = parent + ".custom-keybinding"
    path = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/nyavke-voice-input/"
    return parent, custom, path


def _parse_gsettings_list(value: str) -> list[str]:
    value = value.strip()
    if value.startswith("@as "):
        value = value[4:]
    try:
        result = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return []
    return [str(item) for item in result] if isinstance(result, (list, tuple)) else []


def _install_gsettings(desktop: str, combo: str) -> bool:
    if not shutil.which("gsettings"):
        return False
    spec = _gsettings_spec(desktop)
    if spec is None:
        return False
    parent, custom, path = spec
    current = _gsettings_run("get", parent, "custom-keybindings")
    if current is None or current.returncode != 0:
        return False
    values = _parse_gsettings_list(current.stdout)
    target = f"{custom}:{path}"
    fields = (
        ("name", repr("Voice Input")),
        ("command", repr(_command("--toggle"))),
        ("binding", repr(to_gsettings(combo))),
    )
    if any((result := _gsettings_run("set", target, key, value)) is None or result.returncode != 0
           for key, value in fields):
        return False
    if path not in values:
        values.append(path)
        result = _gsettings_run("set", parent, "custom-keybindings", repr(values))
        if result is None or result.returncode != 0:
            return False
    return True


def _uninstall_gsettings(desktop: str) -> bool:
    if not shutil.which("gsettings"):
        return True
    spec = _gsettings_spec(desktop)
    if spec is None:
        return True
    parent, custom, path = spec
    current = _gsettings_run("get", parent, "custom-keybindings")
    if current is None or current.returncode != 0:
        return True
    values = _parse_gsettings_list(current.stdout)
    if path in values:
        values = [value for value in values if value != path]
        result = _gsettings_run("set", parent, "custom-keybindings", repr(values))
        if result is None or result.returncode != 0:
            return False
    target = f"{custom}:{path}"
    for key in ("name", "command", "binding"):
        _gsettings_run("reset", target, key)
    return True


def install(combo: str, position: str = "bottom") -> bool:
    """Установить native bind. False означает: включить evdev listener."""
    info = detect()
    cfg = _config_home()
    ok = False
    if info.desktop == "hyprland":
        ok = _install_hypr(combo, position)
    elif info.desktop == "sway":
        path = cfg / "sway/config"
        ok = _replace_block(path, _sway_block(combo))
        if ok:
            _reload(["swaymsg", "reload"])
    elif info.desktop == "i3":
        paths = (cfg / "i3/config", Path(os.environ.get("HOME") or Path.home()) / ".i3/config")
        path = next((candidate for candidate in paths if candidate.exists()), paths[0])
        ok = _replace_block(path, _sway_block(combo, x11=True))
        if ok:
            _reload(["i3-msg", "reload"])
    elif info.desktop == "gnome":
        ok = _install_gsettings(info.desktop, combo)
    print(f"[voice-input] среда: {info.label}; hotkey: {'native' if ok else 'evdev fallback'}")
    return ok


def uninstall_all() -> bool:
    """Удалить все известные управляемые bind-блоки; операция идемпотентна."""
    ok = True
    caelestia, main_lua, legacy = _hypr_paths()
    for path in {caelestia, main_lua}:
        ok = hypr.uninstall(path=path) and ok
    cfg = _config_home()
    for path in (legacy, cfg / "sway/config", cfg / "i3/config",
                 Path(os.environ.get("HOME") or Path.home()) / ".i3/config"):
        ok = _remove_block(path) and ok
    ok = _uninstall_gsettings("gnome") and ok
    _reload(["hyprctl", "reload"])
    _reload(["swaymsg", "reload"])
    _reload(["i3-msg", "reload"])
    return ok


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Voice Input desktop integration")
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--hotkey", default="grave")
    parser.add_argument("--position", choices=("top", "bottom"), default="bottom")
    args = parser.parse_args(argv)
    if args.uninstall:
        return 0 if uninstall_all() else 1
    if args.install:
        install(args.hotkey, args.position)
    info = detect()
    print(f"desktop={info.desktop} session={info.session}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
