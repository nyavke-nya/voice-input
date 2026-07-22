"""Фильтр галлюцинаций Whisper и косметика текста (без загрузки модели)."""
from types import SimpleNamespace

from pill.stt_engine import SttEngine, apply_replacements, is_hallucination, polish


def test_blocklist_and_empty():
    assert is_hallucination("Спасибо за просмотр!")
    assert is_hallucination("Thanks for watching")
    assert is_hallucination("   ")
    assert is_hallucination("...")


def test_low_confidence_dropped():
    assert is_hallucination("you", no_speech_prob=0.9, avg_logprob=-2.0)
    assert not is_hallucination("you", no_speech_prob=0.05, avg_logprob=-0.1)


def test_real_speech_kept():
    assert not is_hallucination("привет как дела")
    assert not is_hallucination("hello there", no_speech_prob=0.1, avg_logprob=-0.3)


def test_polish_capitalizes_and_collapses():
    assert polish("  привет   мир ") == "Привет мир"
    assert polish("...так вот") == "...Так вот"
    assert polish("hello world") == "Hello world"
    assert polish("-5 градусов") == "-5 градусов"
    assert polish("") == ""


class _FakeModel:
    def __init__(self, text="translated text"):
        self.text = text
        self.kwargs = None

    def transcribe(self, _audio, **kwargs):
        self.kwargs = kwargs
        segment = SimpleNamespace(text=self.text, no_speech_prob=0.0, avg_logprob=-0.1)
        return iter([segment]), None


def test_english_mode_translates_with_auto_source_language():
    cfg = {"language": "en", "model": "small", "device": "cpu", "beam_size": 5,
           "packs": ["profanity"], "prompt": "Русский контекст"}
    engine, model = SttEngine(cfg), _FakeModel()
    engine._ensure_model = lambda: model
    assert engine.transcribe([0.1]) == "Translated text"
    assert model.kwargs["task"] == "translate" and model.kwargs["language"] is None
    assert "fuck" in model.kwargs["hotwords"] and "хуй" not in model.kwargs["hotwords"]
    assert model.kwargs["initial_prompt"] is None


def test_russian_mode_remains_transcription():
    cfg = {"language": "ru", "model": "small", "device": "cpu", "packs": []}
    engine, model = SttEngine(cfg), _FakeModel("русский текст")
    engine._ensure_model = lambda: model
    assert engine.transcribe([0.1]) == "Русский текст"
    assert model.kwargs["task"] == "transcribe" and model.kwargs["language"] == "ru"


def test_replacement_is_literal():
    assert apply_replacements("ошибка", {"ошибка": r"C:\\new\\1"}) == r"C:\\new\\1"


if __name__ == "__main__":
    test_blocklist_and_empty()
    test_low_confidence_dropped()
    test_real_speech_kept()
    test_polish_capitalizes_and_collapses()
    test_english_mode_translates_with_auto_source_language()
    test_russian_mode_remains_transcription()
    test_replacement_is_literal()
    print("test_stt_filter OK")
