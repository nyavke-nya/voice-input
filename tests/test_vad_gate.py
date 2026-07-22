"""Конечный автомат конца фразы (без onnx/железа)."""
from pill.audio_recorder import SpeechGate


def test_fires_after_speech_then_silence():
    g = SpeechGate(silence_ms=500, min_speech_ms=200, frame_ms=32)
    for _ in range(10):  # ~320мс речи
        g.feed(True)
    assert g.started and not g.should_stop
    fired = None
    for i in range(100):
        g.feed(False)
        if g.should_stop:
            fired = i + 1
            break
    assert fired == round(500 / 32)  # ~16 кадров тишины


def test_no_fire_on_short_blip():
    g = SpeechGate(silence_ms=300, min_speech_ms=200, frame_ms=32)
    g.feed(True)  # один кадр (~32мс) — мало для start
    for _ in range(50):
        g.feed(False)
    assert not g.started and not g.should_stop


def test_silence_resets_between_words():
    g = SpeechGate(silence_ms=500, min_speech_ms=100, frame_ms=32)
    for _ in range(5):
        g.feed(True)
    for _ in range(10):  # пауза короче порога
        g.feed(False)
    assert not g.should_stop
    g.feed(True)  # снова речь — счётчик тишины сброшен
    for _ in range(10):
        g.feed(False)
    assert not g.should_stop


def test_timeout_on_pure_silence():
    g = SpeechGate(preroll_timeout_ms=320, frame_ms=32)
    for _ in range(10):
        g.feed(False)
    assert g.timed_out and not g.should_stop


if __name__ == "__main__":
    test_fires_after_speech_then_silence()
    test_no_fire_on_short_blip()
    test_silence_resets_between_words()
    test_timeout_on_pure_silence()
    print("test_vad_gate OK")
