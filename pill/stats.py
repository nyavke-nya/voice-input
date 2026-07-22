"""Статистика диктовок: сколько надиктовано и как быстро распозналось.

Хранится в ~/.config/pill/stats.json, копится между сессиями. record() — чистая
функция, считает символы/буквы/слова и обновляет тотал + «последнюю».
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime

from .config import config_path

HISTORY_MAX = 12

DEFAULTS: dict = {
    "count": 0,        # число диктовок
    "chars": 0,        # всего символов (с пробелами/пунктуацией)
    "letters": 0,      # всего букв (алфавитные)
    "words": 0,        # всего слов
    "audio_sec": 0.0,  # всего записано звука, с
    "proc_sec": 0.0,   # всего времени распознавания, с
    "last": {"chars": 0, "letters": 0, "words": 0, "proc_ms": 0, "audio_ms": 0},
    "history": [],     # последние диктовки: [{"time": "ЧЧ:ММ", "text": "…"}], новые сверху
}


def stats_path():
    return config_path().parent / "stats.json"


def fresh() -> dict:
    return json.loads(json.dumps(DEFAULTS))  # глубокая копия дефолтов


def _number(value, default=0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) and value >= 0 else default


def _sanitize(raw) -> dict:
    out = fresh()
    if not isinstance(raw, dict):
        return out
    for key in ("count", "chars", "letters", "words"):
        out[key] = int(_number(raw.get(key), 0))
    for key in ("audio_sec", "proc_sec"):
        out[key] = _number(raw.get(key), 0.0)

    last = raw.get("last")
    if isinstance(last, dict):
        for key in ("chars", "letters", "words", "proc_ms", "audio_ms"):
            out["last"][key] = int(_number(last.get(key), 0))

    history = raw.get("history")
    if isinstance(history, list):
        out["history"] = [
            {"time": str(item.get("time", "")), "text": str(item.get("text", ""))}
            for item in history
            if isinstance(item, dict) and item.get("text") is not None
        ][:HISTORY_MAX]
    return out


def load() -> dict:
    p = stats_path()
    if not p.exists():
        return fresh()
    try:
        return _sanitize(json.loads(p.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return fresh()


def save(s: dict) -> None:
    p = stats_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(_sanitize(s), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)


def record(s: dict, text: str, proc_sec: float, audio_sec: float) -> dict:
    """Учесть одну диктовку. Мутирует и возвращает s."""
    text = str(text)
    proc_sec = _number(proc_sec, 0.0)
    audio_sec = _number(audio_sec, 0.0)
    chars = len(text)
    letters = sum(1 for c in text if c.isalpha())
    words = len(re.findall(r"[^\W_]+(?:[-'’][^\W_]+)*", text, flags=re.UNICODE))
    s["count"] += 1
    s["chars"] += chars
    s["letters"] += letters
    s["words"] += words
    s["audio_sec"] += audio_sec
    s["proc_sec"] += proc_sec
    s["last"] = {
        "chars": chars, "letters": letters, "words": words,
        "proc_ms": round(proc_sec * 1000), "audio_ms": round(audio_sec * 1000),
    }
    hist = s.setdefault("history", [])
    hist.insert(0, {"time": datetime.now().strftime("%H:%M"), "text": text})
    del hist[HISTORY_MAX:]
    return s


if __name__ == "__main__":
    s = fresh()
    record(s, "Привет мир!", 0.2, 1.5)
    assert s["count"] == 1 and s["chars"] == 11 and s["words"] == 2
    assert s["letters"] == 9              # «Привет»+«мир» = 9 букв, без пробела/«!»
    assert s["last"]["proc_ms"] == 200 and s["last"]["audio_ms"] == 1500
    record(s, "ещё", 0.1, 0.5)
    assert s["count"] == 2 and s["words"] == 3 and s["letters"] == 12
    assert s["history"][0]["text"] == "ещё" and len(s["history"]) == 2  # новые сверху
    print("stats OK")
