"""Нативная интеграция с Lua-конфигом Hyprland.

В Hyprland 0.55 с Lua-конфигом динамические windowrulev2/keyword не работают, а
правильный способ сделать плавающий оверлей — это window_rule.
Приложение владеет блоком между маркерами в hypr-user.lua: bind активации +
window_rule (float/pin/no_initial_focus/size/move). При смене хоткея в настройках
блок переписывается и конфиг перезагружается, поэтому нативный bind всегда
совпадает с выбранной комбинацией.

Клавиатурный фокус сохраняет Qt.WindowDoesNotAcceptFocus в QML. В правиле остаётся
no_initial_focus как дополнительная страховка; в отличие от no_focus он не ломает
клики по шестерёнке и настройкам.
"""
from __future__ import annotations

import shutil
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .hotkey import normalize_combo

BEGIN = "-- >>> pill managed integration >>>"
END = "-- <<< pill managed integration <<<"

_MOD = {"ctrl": "CTRL", "alt": "ALT", "shift": "SHIFT", "super": "SUPER"}

# Пунктуация -> имя XKB-keysym (Hyprland не понимает сам символ, только имя).
_KEYSYM = {
    "grave": "GRAVE", "minus": "MINUS", "equal": "EQUAL",
    "leftbrace": "BRACKETLEFT", "rightbrace": "BRACKETRIGHT",
    "semicolon": "SEMICOLON", "apostrophe": "APOSTROPHE", "comma": "COMMA",
    "dot": "PERIOD", "slash": "SLASH", "backslash": "BACKSLASH",
    "space": "SPACE", "enter": "RETURN", "esc": "ESCAPE",
    "tab": "Tab", "backspace": "BackSpace", "delete": "Delete",
    "insert": "Insert", "home": "Home", "end": "End",
    "left": "Left", "right": "Right", "up": "Up", "down": "Down",
    "pageup": "Page_Up", "pagedown": "Page_Down",
    "capslock": "Caps_Lock", "numlock": "Num_Lock",
    "scrolllock": "Scroll_Lock", "pause": "Pause", "sysrq": "Print",
    "menu": "Menu", "compose": "Multi_key", "mute": "XF86AudioMute",
    "volumedown": "XF86AudioLowerVolume", "volumeup": "XF86AudioRaiseVolume",
    "playpause": "XF86AudioPlay", "nextsong": "XF86AudioNext",
    "previoussong": "XF86AudioPrev",
}


def user_lua() -> Optional[Path]:
    p = Path.home() / ".config" / "caelestia" / "hypr-user.lua"
    return p if p.exists() else None


def to_hypr(combo: str) -> str:
    """'alt+a' -> 'ALT + A' для hl.bind."""
    mods, key = normalize_combo(combo)
    return " + ".join([*(_MOD[mod] for mod in mods), _KEYSYM.get(key, key.upper())])


def _cmd(*args: str) -> str:
    # тот же интерпретатор venv + путь к пакету, чтобы команда работала из любого cwd
    pkg_parent = Path(__file__).resolve().parent.parent
    return shlex.join(["env", f"PYTHONPATH={pkg_parent}", sys.executable, "-m", "pill", *args])


def _lua_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _block(combo: str) -> str:
    return "\n".join([
        BEGIN,
        "-- Управляется Voice Input. Хоткей меняется в настройках.",
        f'hl.on("hyprland.start", function() hl.exec_cmd({_lua_string(_cmd())}) end)  -- фоновый демон',
        f'hl.bind({_lua_string(to_hypr(combo))}, hl.dsp.exec_cmd({_lua_string(_cmd("--toggle"))}), {{ release = true }})',
        "hl.window_rule({",
        '    name             = "pill-overlay",',
        '    match            = { class = "^pill$" },',
        "    float            = true,",
        "    pin              = true,",
        # только no_initial_focus: не красть фокус при появлении (текст идёт в
        # исходное поле), но клики по настройкам/шестерёнке работают. no_focus
        # блокировал бы и указатель.
        "    no_initial_focus = true,",
        "    no_anim          = true,",
        # blur НЕ отключаем: при включённом глобальном blur пилюля станет
        # настоящим frosted-стеклом. Свою тень рисуем в QML -> no_shadow.
        "    no_dim           = true,",
        "    no_shadow        = true,",
        "    border_size      = 0,",
        "    rounding         = 0,",
        '    opacity          = "1.0 override",',  # перебить глобальный windowOpacity -> без просвечивания
        '    size             = "400 960",',
        '    move             = "(monitor_w*0.5-window_w*0.5) (monitor_h*0.985-window_h)",',
        "})",
        END,
    ])


def install(combo: str, path: Optional[Path] = None) -> bool:
    """Вписать/обновить управляемый блок в Lua-конфиг и reload Hyprland.

    Без ``path`` используется безопасная пользовательская точка caelestia.
    Явный путь нужен универсальному установщику для vanilla Hyprland 0.55+.
    """
    lua = Path(path).expanduser() if path is not None else user_lua()
    if lua is None:
        return False
    try:
        text = lua.read_text(encoding="utf-8")
        block = _block(combo)
    except (OSError, ValueError) as e:
        print(f"[voice-input] интеграция Hyprland не обновлена: {e}")
        return False
    has_begin, has_end = BEGIN in text, END in text
    if has_begin != has_end:
        print("[voice-input] интеграция Hyprland не обновлена: найден только один маркер")
        return False
    if has_begin:
        start, end = text.index(BEGIN), text.index(END)
        if end < start:
            print("[voice-input] интеграция Hyprland не обновлена: маркеры переставлены")
            return False
        updated = text[:start] + block + text[end + len(END):]
    else:
        updated = text.rstrip() + "\n\n" + block + "\n"
    if updated != text:
        try:
            lua.write_text(updated, encoding="utf-8")
        except OSError as e:
            print(f"[voice-input] интеграция Hyprland не записана: {e}")
            return False
        reload()
    return True


def uninstall(path: Optional[Path] = None) -> bool:
    """Удалить только управляемый блок, не затрагивая остальной Lua-конфиг."""
    lua = Path(path).expanduser() if path is not None else user_lua()
    if lua is None or not lua.exists():
        return True
    try:
        text = lua.read_text(encoding="utf-8")
    except OSError as e:
        print(f"[voice-input] интеграция Hyprland не прочитана: {e}")
        return False
    has_begin, has_end = BEGIN in text, END in text
    if not has_begin and not has_end:
        return True
    if has_begin != has_end or text.index(END) < text.index(BEGIN):
        print("[voice-input] интеграция Hyprland не удалена: повреждены маркеры")
        return False
    start, end = text.index(BEGIN), text.index(END) + len(END)
    updated = (text[:start].rstrip() + "\n" + text[end:].lstrip("\n")).lstrip("\n")
    try:
        lua.write_text(updated, encoding="utf-8")
    except OSError as e:
        print(f"[voice-input] интеграция Hyprland не удалена: {e}")
        return False
    reload()
    return True


def reload() -> None:
    if shutil.which("hyprctl"):
        subprocess.run(["hyprctl", "reload"], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    assert to_hypr("alt+a") == "ALT + A"
    assert to_hypr("super+alt+d") == "SUPER + ALT + D"
    assert to_hypr("ctrl+shift+space") == "CTRL + SHIFT + SPACE"
    b = _block("alt+a")
    assert BEGIN in b and END in b and 'no_initial_focus = true' in b
    assert '"ALT + A"' in b and "-m pill --toggle" in b
    assert "monitor_h*0.985-window_h" in b
    print("hypr OK")
