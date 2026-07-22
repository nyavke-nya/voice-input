"""Конвертация комбо в формат Hyprland и генерация управляемого блока."""
from pill import hypr


def test_to_hypr():
    assert hypr.to_hypr("alt+a") == "ALT + A"
    assert hypr.to_hypr("super+alt+d") == "SUPER + ALT + D"
    assert hypr.to_hypr("ctrl+shift+space") == "CTRL + SHIFT + SPACE"
    assert hypr.to_hypr("win+r") == "SUPER + R"
    assert hypr.to_hypr("`") == "GRAVE"          # спецсимвол -> имя keysym
    assert hypr.to_hypr("super+`") == "SUPER + GRAVE"


def test_block_has_markers_and_rule():
    b = hypr._block("alt+a")
    assert hypr.BEGIN in b and hypr.END in b
    assert 'no_initial_focus = true' in b       # не крадёт фокус -> вставка в нужное поле
    assert 'no_focus' not in b                  # иначе перестают работать клики по настройкам
    assert 'class = "^pill$"' in b
    assert 'size             = "400 960"' in b
    assert '"ALT + A"' in b
    assert "-m pill --toggle" in b


def test_invalid_combo_is_not_written_to_lua():
    try:
        hypr._block('a+b") evil')
        raise AssertionError("невалидный бинд должен отклоняться")
    except ValueError:
        pass


if __name__ == "__main__":
    test_to_hypr()
    test_block_has_markers_and_rule()
    test_invalid_combo_is_not_written_to_lua()
    print("test_hypr OK")
