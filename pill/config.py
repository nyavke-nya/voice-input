"""Загрузка/сохранение настроек. Один JSON в ~/.config/pill/config.json."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .hotkey import canonical_combo

DEFAULTS: dict = {
    "hotkey": "grave",                # бинд активации (Hyprland), меняется в настройках
    "language": "auto",               # "ru" | "en" | "auto"
    "model": "small",                 # "tiny" | "small" | "medium" | "large"
    "input_device": None,             # None = устройство по умолчанию, иначе индекс sounddevice
    "vad_sensitivity": 0.5,           # 0..1 — порог вероятности речи Silero (выше = агрессивнее режет)
    "silence_ms": 500,                # тишина дольше этого = конец фразы
    "input_method": "keyboard",       # "keyboard" (wtype) | "clipboard" (wl-copy + вставка)
    "device": "auto",                 # "auto" | "cuda" (GPU) | "cpu" — где считать STT
    "prompt": "",                     # подсказка словаря для Whisper (имена/термины)
    "replacements": {},               # словарь исправлений: {"гитхаб": "GitHub"}
    "vad_model_path": None,           # переопределить путь к silero_vad.onnx
    "beam_size": 5,                   # ширина beam-search (5 = точнее, ~как дефолт whisper)
    "packs": ["profanity"],           # словарные пакеты biasing: "profanity" | "it" (см. vocab.py)
    "vocabulary": "",                 # свои hotwords через пробел (имена/термины/сленг)
    "pill_position": "bottom",        # где пилюля: "bottom" | "top" экрана
}

_ALLOWED = {
    "language": {"ru", "en", "auto"},
    "model": {"tiny", "small", "medium", "large"},
    "input_method": {"keyboard", "clipboard"},
    "device": {"auto", "cuda", "cpu"},
    "pill_position": {"bottom", "top"},
}
_KNOWN_PACKS = {"profanity", "it"}


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "pill" / "config.json"


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    d = Path(base) / "pill"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sanitize(cfg: dict) -> dict:
    if not isinstance(cfg, dict):
        cfg = {}
    out = dict(DEFAULTS)
    out.update({k: v for k, v in cfg.items() if k in DEFAULTS})
    for key, allowed in _ALLOWED.items():
        if out[key] not in allowed:
            out[key] = DEFAULTS[key]
    try:
        out["vad_sensitivity"] = min(1.0, max(0.0, float(out["vad_sensitivity"])))
    except (TypeError, ValueError):
        out["vad_sensitivity"] = DEFAULTS["vad_sensitivity"]
    try:
        out["silence_ms"] = min(10_000, max(100, int(out["silence_ms"])))
    except (TypeError, ValueError):
        out["silence_ms"] = DEFAULTS["silence_ms"]
    try:
        out["hotkey"] = canonical_combo(out["hotkey"])
    except ValueError:
        out["hotkey"] = DEFAULTS["hotkey"]
    device = out["input_device"]
    if device is not None and (isinstance(device, bool) or not isinstance(device, int) or device < 0):
        out["input_device"] = None
    out["prompt"] = str(out["prompt"]) if out["prompt"] is not None else ""
    out["vocabulary"] = str(out["vocabulary"]) if out["vocabulary"] is not None else ""
    path = out["vad_model_path"]
    out["vad_model_path"] = str(path).strip() if path else None
    if not isinstance(out["replacements"], dict):
        out["replacements"] = {}
    else:
        out["replacements"] = {str(k): str(v) for k, v in out["replacements"].items()}
    if not isinstance(out["packs"], list):
        out["packs"] = list(DEFAULTS["packs"])
    else:  # только известные, без дублей, порядок стабилен
        out["packs"] = [p for p in dict.fromkeys(out["packs"]) if p in _KNOWN_PACKS]
    try:
        out["beam_size"] = min(10, max(1, int(out["beam_size"])))
    except (TypeError, ValueError):
        out["beam_size"] = DEFAULTS["beam_size"]
    return out


def load() -> dict:
    p = config_path()
    if not p.exists():
        return _sanitize({})
    try:
        return _sanitize(json.loads(p.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return _sanitize({})


def save(cfg: dict) -> None:
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(_sanitize(cfg), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)


if __name__ == "__main__":
    # self-check: санитайзер чинит мусор и клампит диапазоны
    bad = {"language": "de", "model": "huge", "vad_sensitivity": 5, "silence_ms": "x", "junk": 1}
    s = _sanitize(bad)
    assert s["language"] == "auto" and s["model"] == "small"
    assert s["vad_sensitivity"] == 1.0 and s["silence_ms"] == 500
    assert "junk" not in s
    assert _sanitize({"model": "large"})["model"] == "large"
    assert _sanitize({"packs": ["it", "ghost", "it"]})["packs"] == ["it"]
    assert _sanitize({"packs": "nope"})["packs"] == ["profanity"]
    assert _sanitize({"beam_size": 99})["beam_size"] == 10
    assert _sanitize({"beam_size": "x"})["beam_size"] == 5
    assert _sanitize({"pill_position": "top"})["pill_position"] == "top"
    assert _sanitize({"pill_position": "xx"})["pill_position"] == "bottom"
    print("config OK")
