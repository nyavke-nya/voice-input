"""Сборка словарного biasing для транскрипции и перевода."""
from pill.vocab import build_bias


def test_transcription_bias_uses_russian_pack():
    prompt, hotwords = build_bias({"packs": ["profanity"], "prompt": "Контекст"})
    assert prompt == "Контекст" and "хуй" in hotwords


def test_translation_bias_uses_english_targets():
    prompt, hotwords = build_bias(
        {"packs": ["profanity", "it"], "prompt": "Русский контекст"}, translate=True
    )
    assert prompt is None and "fuck" in hotwords and "GitHub" in hotwords
    assert "хуй" not in hotwords


if __name__ == "__main__":
    test_transcription_bias_uses_russian_pack()
    test_translation_bias_uses_english_targets()
    print("test_vocab OK")
