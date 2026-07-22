"""Словарные «пакеты» для смещения распознавания Whisper.

Проблема: базовый Whisper обучен на отфильтрованных данных и глушит мат и редкую
лексику — выдаёт эвфемизм, соседнее слово или мусор. Лечится не пост-правкой
(она портит корректные редкие слова), а на этапе декодирования:

  • initial_prompt — пользовательский контекст для обычной транскрипции;
  • hotwords — список слов, которые beam-search подхватывает охотнее. Для
    перевода используются отдельные английские целевые hotwords.

faster-whisper склеивает оба (см. Tokenizer.get_prompt: сначала hotwords, потом
previous_tokens из initial_prompt). Это ровно тот «словарь как у клавиатуры» —
бандлим лексикон и отдаём его декодеру, ничего не переписывая после.

Пакеты включаются в настройках (config["packs"]). Слова свои — config["vocabulary"].
"""
from __future__ import annotations

from typing import Optional, Tuple

# --- Обсценный лексикон (RU). Нужен, чтобы диктовка не цензурировалась. ---
# ТОЛЬКО hotwords, без нарратив-затравки: крудовый primer в initial_prompt уводил
# тон всей фразы (нормальная речь искажалась, диалогное «— » текло в начало).
# hotwords поднимает мат точечно — только когда он акустически похож — не derailя фразу.
_MAT_HOTWORDS = (
    "хуй хуя хую хуём нахуй похуй нихуя охуеть охуел охуенно хуёво хуйня хуета "
    "пизда пизду пиздец пиздёж пиздатый спиздить пиздеть пиздабол опизденеть "
    "ебать ебал ёб ебало ебанутый ебаный заебал заебись наебал уебать уёбок ебля "
    "блядь бля блять блядский сука суки сучара мудак мудило мудозвон "
    "залупа гандон гондон пидор пидорас пидарас дрочить задрот "
    "хер херня хреново нихера дохера елда манда говно дерьмо распиздяй долбоёб"
)
_MAT_EN_HOTWORDS = (
    "fuck fucking fucked fucker motherfucker shit bullshit bitch bastard asshole "
    "dick cock pussy cunt damn goddamn jerk moron idiot"
)

# --- IT/термины: частая боль русского Whisper (латиница + имена собственные). ---
_IT_HOTWORDS = (
    "Hyprland Wayland Linux Arch Claude GitHub Python Docker Kubernetes systemd "
    "API JSON YAML SQL Redis Nginx Rust Golang TypeScript React бэкенд фронтенд "
    "деплой коммит рефакторинг линтер терминал репозиторий пайплайн фреймворк "
    "curl bash fish ssh git npm pip venv Neovim Whisper промпт токен эмбеддинг"
)
_IT_EN_HOTWORDS = (
    "Hyprland Wayland Linux Arch Claude GitHub Python Docker Kubernetes systemd "
    "API JSON YAML SQL Redis Nginx Rust Golang TypeScript React backend frontend "
    "deploy commit refactoring linter terminal repository pipeline framework curl "
    "bash fish SSH git npm pip venv Neovim Whisper prompt token embedding"
)

PACKS: dict[str, dict] = {
    "profanity": {
        "label": "Мат", "hotwords": _MAT_HOTWORDS,
        "translate_hotwords": _MAT_EN_HOTWORDS,
    },
    "it": {
        "label": "IT", "hotwords": _IT_HOTWORDS,
        "translate_hotwords": _IT_EN_HOTWORDS,
    },
}


def build_bias(cfg: dict, translate: bool = False) -> Tuple[Optional[str], Optional[str]]:
    """(initial_prompt, hotwords) из включённых пакетов + польз. словаря/промпта.

    При переводе на English русскоязычный prompt не подмешивается в декодер, а
    пакеты дают английские целевые слова. Пустые части -> None."""
    packs = cfg.get("packs") or []
    prompt_parts, hot_parts = [], []
    if cfg.get("prompt") and not translate:
        prompt_parts.append(str(cfg["prompt"]).strip())
    for name in packs:
        p = PACKS.get(name)
        if not p:
            continue
        if p.get("primer") and not translate:
            prompt_parts.append(p["primer"])
        words = p.get("translate_hotwords" if translate else "hotwords")
        if words:
            hot_parts.append(words)
    if cfg.get("vocabulary"):
        hot_parts.append(str(cfg["vocabulary"]).strip())
    prompt = " ".join(x for x in prompt_parts if x).strip() or None
    hot = " ".join(x for x in hot_parts if x).strip() or None
    return prompt, hot


if __name__ == "__main__":
    # self-check: пакеты собираются, порядок и None-семантика верны
    p, h = build_bias({"packs": ["profanity"], "prompt": "Про Hyprland."})
    assert p == "Про Hyprland." and h and "хуй" in h  # мат идёт в hotwords, не в prompt
    p2, h2 = build_bias({"packs": [], "prompt": "", "vocabulary": ""})
    assert p2 is None and h2 is None
    p3, h3 = build_bias({"packs": ["it"], "vocabulary": "Каэлестия Пилюля"})
    assert p3 is None and "Docker" in h3 and "Каэлестия" in h3
    assert build_bias({"packs": ["ghost"]}) == (None, None)
    p4, h4 = build_bias({"packs": ["profanity"], "prompt": "Русский контекст"}, translate=True)
    assert p4 is None and h4 and "fuck" in h4 and "хуй" not in h4
    print("vocab OK")
