"""STT на faster-whisper: аудио -> текст. Пунктуацию и капитализацию Whisper
ставит сам; здесь только фильтр галлюцинаций на тишине и косметика.

Модель грузится лениво и живёт между вызовами (важно для задержки).
"""
from __future__ import annotations

import re
import threading
from typing import Optional

from .vocab import build_bias

# tiny/small/medium грузятся по имени; «large» -> large-v3 (лучшее качество на мате
# и редкой лексике, ~3ГБ, качается при первом выборе).
_MODEL_ALIAS = {"large": "large-v3"}

# Фразы, которые Whisper выдумывает на тишине/шуме (ru+en). Сравнение по
# нормализованному тексту (нижний регистр, без пунктуации по краям).
_HALLUCINATIONS = {
    "спасибо за просмотр",
    "спасибо за внимание",
    "продолжение следует",
    "субтитры сделал dimatorzok",
    "субтитры делал dimatorzok",
    "редактор субтитров а.семкин корректор а.егорова",
    "продолжение следует...",
    "thank you for watching",
    "thanks for watching",
    "please subscribe",
    "subscribe to my channel",
    "amara.org",
    "subtitles by the amara.org community",
    "продолжение следует.",
}
_AMBIGUOUS_HALLUCINATIONS = {"you", "thank you"}


def _norm(text: str) -> str:
    return text.strip().strip(".!?…,-—\"' ").lower()


def is_hallucination(
    text: str,
    no_speech_prob: Optional[float] = None,
    avg_logprob: Optional[float] = None,
) -> bool:
    n = _norm(text)
    if not n:
        return True
    if n in _HALLUCINATIONS:
        if no_speech_prob is None or avg_logprob is None:
            return True
        return no_speech_prob > 0.35 or avg_logprob < -0.7
    if n in _AMBIGUOUS_HALLUCINATIONS:
        return bool(no_speech_prob is not None and avg_logprob is not None
                    and no_speech_prob > 0.6 and avg_logprob < -1.0)
    # уверенная «не-речь» + низкое правдоподобие = мусор
    if (no_speech_prob is not None and avg_logprob is not None
            and no_speech_prob > 0.6 and avg_logprob < -1.0):
        return True
    return False


def polish(text: str) -> str:
    """Схлопнуть пробелы, срезать ведущее тире-артефакт, капитализировать."""
    text = " ".join(text.split())
    text = re.sub(r"^[—–-]+\s+", "", text)  # диалогное «— »; минус в «-5» сохраняем
    if text and not any(ch.isalnum() for ch in text):
        return ""
    for i, ch in enumerate(text):
        if ch.isalpha():
            if any(prefix.isdigit() for prefix in text[:i]):
                return text
            return text[:i] + ch.upper() + text[i + 1:]
    return text


def apply_replacements(text: str, repl: dict) -> str:
    """Пользовательский словарь исправлений (регистронезависимо, по фразам).
    Правит повторяющиеся ослышки/термины: {'гитхаб': 'GitHub'}."""
    if not repl:
        return text
    for wrong, right in repl.items():
        if wrong:
            text = re.sub(re.escape(wrong), lambda _match, value=str(right): value,
                          text, flags=re.IGNORECASE)
    return text


class SttEngine:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._model = None
        self._model_name: Optional[str] = None
        self._device: Optional[str] = None
        self._requested_device: Optional[str] = None
        self._lock = threading.RLock()

    @staticmethod
    def _preload_cuda_libs():
        """Подгрузить cuBLAS/cuDNN из pip-пакетов nvidia-*-cu12 (если стоят),
        чтобы ctranslate2 нашёл их без LD_LIBRARY_PATH. Без них GPU не поедет."""
        import ctypes
        import glob
        import os

        try:
            import nvidia  # namespace-пакет: путь(и) в __path__, __file__ = None
        except ImportError:
            return
        for base in list(getattr(nvidia, "__path__", [])):
            for pat in ("cublas/lib/libcublasLt.so*", "cublas/lib/libcublas.so*",
                        "cudnn/lib/libcudnn*.so*"):
                for so in sorted(glob.glob(os.path.join(base, pat))):
                    try:
                        ctypes.CDLL(so, mode=ctypes.RTLD_GLOBAL)
                    except OSError:
                        pass

    def _device_plan(self):
        """Порядок попыток (device, compute_type). GPU резко ускоряет БЕЗ смены модели."""
        dev = self.cfg.get("device", "auto")
        if dev == "cpu":
            return [("cpu", "int8")]
        if dev == "cuda":
            return [("cuda", "float16"), ("cpu", "int8")]
        try:  # auto: взять GPU, если ctranslate2 его видит (проверено на RTX 3060)
            import ctranslate2

            if ctranslate2.get_cuda_device_count() > 0:
                return [("cuda", "float16"), ("cpu", "int8")]
        except Exception:  # noqa: BLE001
            pass
        return [("cpu", "int8")]

    def _ensure_model(self):
        import os

        name = _MODEL_ALIAS.get(self.cfg.get("model", "small"), self.cfg.get("model", "small"))
        requested = self.cfg.get("device", "auto")
        with self._lock:
            if (self._model is None or self._model_name != name
                    or self._requested_device != requested):
                from faster_whisper import WhisperModel

                errors = []
                for device, compute in self._device_plan():
                    try:
                        if device == "cuda":
                            self._preload_cuda_libs()
                        kw = {"device": device, "compute_type": compute}
                        if device == "cpu":
                            kw["cpu_threads"] = os.cpu_count() or 4
                        model = WhisperModel(name, **kw)
                        self._model = model
                        self._model_name = name
                        self._device = device
                        self._requested_device = requested
                        print(f"[pill] STT: {name} на {device}/{compute}")
                        break
                    except Exception as e:  # noqa: BLE001  (нет CUDA-библиотек -> CPU)
                        errors.append(f"{device}: {e}")
                else:
                    raise RuntimeError("модель не загрузилась: " + " | ".join(errors))
            return self._model

    def transcribe(self, audio) -> str:
        """audio: np.ndarray float32 @16кГц. Вернуть очищенный текст (может быть пустым)."""
        if audio is None or len(audio) == 0:
            return ""
        with self._lock:
            model = self._ensure_model()
            lang = self.cfg.get("language", "auto")
            translate = lang == "en"
            prompt, hotwords = build_bias(self.cfg, translate=translate)
            try:
                beam = max(1, int(self.cfg.get("beam_size", 5)))
            except (TypeError, ValueError):
                beam = 5
            segments, _info = model.transcribe(
                audio,
                language=None if lang in ("auto", "en") else lang,
                task="translate" if translate else "transcribe",
                beam_size=beam,                  # 5 = точнее на редких словах
                vad_filter=False,                # тишину уже отрезал потоковый VAD
                condition_on_previous_text=False,  # без переноса ошибок между сегментами
                initial_prompt=prompt,
                hotwords=hotwords,
                repetition_penalty=1.15,
                no_repeat_ngram_size=3,
            )
            parts = []
            for seg in segments:
                if is_hallucination(seg.text, seg.no_speech_prob, seg.avg_logprob):
                    continue
                parts.append(seg.text.strip())
        return apply_replacements(polish(" ".join(parts)), self.cfg.get("replacements") or {})

    def warmup(self) -> None:
        """Прогреть модель на тишине, чтобы первая реальная фраза не ждала загрузку."""
        try:
            import numpy as np

            with self._lock:
                model = self._ensure_model()
                list(model.transcribe(np.zeros(16000, dtype="float32"), beam_size=1)[0])
        except Exception:
            pass  # прогрев — не критичный путь


if __name__ == "__main__":
    # self-check: фильтр галлюцинаций и косметика — без загрузки модели
    assert is_hallucination("Спасибо за просмотр!")
    assert is_hallucination("   ")
    assert is_hallucination("you", no_speech_prob=0.9, avg_logprob=-2.0)
    assert not is_hallucination("привет как дела")
    assert not is_hallucination("hello there", no_speech_prob=0.1, avg_logprob=-0.3)
    assert polish("  привет   мир ") == "Привет мир"
    assert polish("...так вот") == "...Так вот"
    assert polish("— отзвучал сигнал") == "Отзвучал сигнал"   # тире-артефакт срезан
    assert polish("-- ну да") == "Ну да"
    assert polish("—") == ""
    assert apply_replacements("я про гитхаб и Гитхаб", {"гитхаб": "GitHub"}) == "я про GitHub и GitHub"
    assert apply_replacements("без замен", {}) == "без замен"
    print("stt_engine filter OK")
