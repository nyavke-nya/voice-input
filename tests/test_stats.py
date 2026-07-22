"""Учёт статистики диктовок."""
import os
import tempfile

from pill import stats


def test_record_counts():
    s = stats.fresh()
    stats.record(s, "Привет мир!", 0.2, 1.5)
    assert s["count"] == 1
    assert s["chars"] == 11          # "Привет мир!" = 11 символов
    assert s["letters"] == 9         # буквы без пробела и "!"
    assert s["words"] == 2
    assert s["last"]["proc_ms"] == 200
    assert s["last"]["audio_ms"] == 1500


def test_accumulates():
    s = stats.fresh()
    stats.record(s, "раз два", 0.1, 1.0)
    stats.record(s, "три", 0.3, 0.5)
    assert s["count"] == 2
    assert s["words"] == 3
    assert s["letters"] == 9          # раз(3)+два(3)+три(3)
    assert abs(s["proc_sec"] - 0.4) < 1e-9
    assert s["last"]["words"] == 1    # последняя = "три"


def test_fresh_is_independent():
    a = stats.fresh()
    a["count"] = 5
    a["history"].append({"time": "00:00", "text": "x"})
    assert stats.fresh()["count"] == 0            # не делит состояние с DEFAULTS
    assert stats.fresh()["history"] == []          # и список истории тоже свой


def test_history_capped_newest_first():
    s = stats.fresh()
    for i in range(stats.HISTORY_MAX + 5):
        stats.record(s, f"фраза {i}", 0.1, 0.5)
    assert len(s["history"]) == stats.HISTORY_MAX   # не растёт бесконечно
    assert s["history"][0]["text"] == f"фраза {stats.HISTORY_MAX + 4}"  # новые сверху


def test_load_repairs_malformed_data():
    with tempfile.TemporaryDirectory() as d:
        os.environ["XDG_CONFIG_HOME"] = d
        os.environ["APPDATA"] = d  # Windows: stats рядом с конфигом в %APPDATA%
        p = stats.stats_path()
        p.parent.mkdir(parents=True)
        p.write_text('{"count": -2, "last": null, "history": [1, {"text": "ok"}]}')
        s = stats.load()
        assert s["count"] == 0 and s["last"]["words"] == 0
        assert s["history"] == [{"time": "", "text": "ok"}]


def test_word_count_ignores_punctuation():
    s = stats.fresh()
    stats.record(s, "... один-два !!!", 0.1, 0.5)
    assert s["words"] == 1


if __name__ == "__main__":
    test_record_counts()
    test_accumulates()
    test_fresh_is_independent()
    test_history_capped_newest_first()
    test_load_repairs_malformed_data()
    test_word_count_ignores_punctuation()
    print("test_stats OK")
