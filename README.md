# Hyprland Voice Input

Локальная голосовая диктовка на Whisper для Hyprland.

Local Whisper voice dictation for Hyprland with Russian-to-English translation.

## ⚠️ ТОЛЬКО ДЛЯ ЭТОЙ КОНФИГУРАЦИИ / ONLY FOR THIS CONFIGURATION

**RU:** это пока не универсальное Linux-приложение. Не запускайте `install.sh` на
своей системе, если она не совпадает с целевой конфигурацией:

- CachyOS/Arch Linux;
- Wayland + Hyprland **0.55.x**;
- **caelestia-shell** (Quickshell) и Lua-точка входа `~/.config/hypr/hyprland.lua`;
- пользовательские переопределения в `~/.config/caelestia/hypr-user.lua`;
- systemd user session; проверено с SDDM-автологином;
- целевое железо: Ryzen 5 5600 + RTX 3060 (без NVIDIA есть CPU-фолбэк).

Не поддерживаются этим установщиком: Ubuntu/Fedora, GNOME/KDE, X11, Windows,
vanilla-Hyprland с `hyprland.conf` и Noctalia.

**EN:** this is not a universal Linux application yet. Do not run `install.sh` unless your
system matches the target above: CachyOS/Arch, Wayland, Hyprland 0.55.x,
caelestia-shell with its Lua configuration and a systemd user session. The tested
hardware is Ryzen 5 5600 + RTX 3060; CPU fallback exists. Ubuntu/Fedora, GNOME/KDE,
X11, Windows, vanilla Hyprland configuration and Noctalia are not supported by this installer.

## Быстрый старт / Quick start

```bash
git clone https://github.com/nyavke/hyprland-voice-input.git
cd hyprland-voice-input
./install.sh --dry-run
./install.sh
```

Скрипт сначала проверит конфигурацию, затем поставит пакеты, Python-окружение,
GPU-библиотеки, модель, desktop-ярлык и Hyprland bind. В конце он крупно напечатает клавишу
голосового ввода. По умолчанию это `GRAVE` — клавиша `` ` ``.

The installer validates the supported setup first, then installs system/Python dependencies,
GPU libraries, the selected model, desktop entry, and Hyprland bind. At the end it prints
the actual voice-input hotkey. The default is `GRAVE` (the `` ` `` key).

## Как пользоваться / How to use

1. Поставь курсор в любое поле ввода.
2. Нажми горячую клавишу, которую напечатал установщик.
3. Говори обычно. После короткой паузы запись закончится, а текст вставится сам.
4. Для настроек открой `Hyprland Voice Input` в лаунчере.

English: focus a text field, press the printed hotkey, speak, and pause. The text is inserted
automatically. Open `Hyprland Voice Input` from the application launcher to change settings.

| Язык вывода / Output mode | Результат / Result |
| --- | --- |
| `Русский` | Распознаёт русскую речь / Transcribes Russian speech |
| `English` | Переводит поддерживаемую речь в English / Translates supported speech into English |
| `Как в речи` | Определяет и сохраняет язык / Detects and preserves the spoken language |

Первый запуск дольше обычного: модель нужно скачать и загрузить в память.

The first launch is slower while the selected model is downloaded and loaded.

## Подробнее / Details

Фоновый демон. Жмёшь бинд → снизу по центру всплывает «пилюля» с живой звуковой
волной → говоришь → замолчал (Silero VAD ловит тишину > 500 мс) → запись
мгновенно останавливается, аудио уходит в faster-whisper, распознанный текст
**впечатывается в поле, где стоял курсор**, пилюля плавно гаснет. Клик по
шестерёнке — пилюля раскрывается в окно настроек. Блэкаут-тема, русский,
автоопределение или перевод любой поддерживаемой речи на English.

Вне записи пилюли нет вовсе — только фоновый процесс.

## Полная совместимость с Hyprland 0.55 (Lua-конфиг)

Приложение НЕ полагается на хрупкие `windowrulev2` через `hyprctl` (в 0.55 с
Lua-парсером они не работают). Вместо этого оно нативно вписывает управляемый
блок в `~/.config/caelestia/hypr-user.lua` между маркерами:

```lua
-- >>> pill managed integration >>>
hl.on("hyprland.start", function() hl.exec_cmd("… -m pill") end)  -- фоновый демон
hl.bind("GRAVE", hl.dsp.exec_cmd("… -m pill --toggle"), { release = true })
hl.window_rule({
    match = { class = "^pill$" },
    float = true, pin = true,
    no_initial_focus = true,
    no_anim = true, no_dim = true, no_shadow = true,
    border_size = 0, rounding = 0,
    size = "400 960",
    move = "(monitor_w*0.5-window_w*0.5) (monitor_h*0.985-window_h)",  -- низ по центру
})
-- <<< pill managed integration <<<
```

Блок ставится/обновляется автоматически при первом запуске и при смене хоткея в
настройках (с `hyprctl reload`). Клавиатурный фокус сохраняет флаг Qt
`WindowDoesNotAcceptFocus`, а `no_initial_focus` служит страховкой при маппинге.
Мышь при этом работает во всей видимой карточке. Референс — `pill.hypr.lua`.

## Как это устроено

```
bind Hyprland (GRAVE) ─► --toggle ─► показать пилюлю + запись
                                          │ Silero VAD (onnx), волна в UI
                                          ▼
                               тишина > silence_ms  ─► стоп записи
                                          ▼
        faster-whisper (beam 5, biasing словарём): текст, пунктуация,
        фильтр галлюцинаций + защита от повторов
                                          ▼
       wtype / ydotool  ·  wl-copy + адаптивная вставка  ─►  активное поле, пилюля гаснет
```

| Файл | Назначение |
|------|-----------|
| `pill/audio_recorder.py` | захват `sounddevice` + потоковый Silero VAD (onnx, без torch) + `SpeechGate` |
| `pill/stt_engine.py` | faster-whisper, фильтр галлюцинаций, капитализация |
| `pill/vocab.py` | словарные пакеты biasing (мат/IT) → `initial_prompt` + `hotwords` для декодера |
| `pill/text_injector.py` | вставка: `wtype` (Unicode/кириллица, фолбэк `ydotool`) или `wl-copy` + Ctrl+V/Ctrl+Shift+V |
| `pill/hypr.py` | нативная интеграция с Lua-конфигом Hyprland (bind + window_rule) |
| `pill/hotkey.py` | разбор бинда + запасной глобальный перехват через evdev/pynput |
| `pill/ui.py` | `Backend` (QObject) — оркестратор + мост в QML |
| `pill/qml/*.qml` | пилюля, волна, настройки, анимации |
| `pill/__main__.py` | демон в одной копии, команды через Unix-сокет |
| `install.sh` | автоустановка для целевой Arch/Hyprland/caelestia-конфигурации |

## Установка (Arch / CachyOS)

### Автоматически после переустановки

Восстанови или склонируй каталог, затем запусти:

```fish
cd ~/hyprland-voice-input
./install.sh
```

`install.sh` сам поставит пакеты pacman и Python, добавит безопасную группу
`uinput` для ydotool, скачает CUDA-библиотеки при наличии NVIDIA, VAD и
выбранную модель Whisper, установит desktop-ярлык и Lua-интеграцию
Hyprland/caelestia. Существующий `config.json` он не перезаписывает. Просмотр действий
без изменений: `./install.sh --dry-run`.

### Вручную

```fish
sudo pacman -S --needed wtype ydotool wl-clipboard portaudio
systemctl --user enable --now ydotool          # фолбэк-эмулятор ввода (нужна группа uinput)

cd ~/hyprland-voice-input
python3 -m venv .venv                          # проверено на Python 3.14
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pill                        # первый запуск: ставит Lua-интеграцию + качает модели
```

Первый запуск скачает Silero VAD (~2 МБ) в `~/.cache/pill/` и модель Whisper
нужного размера в кэш HuggingFace, и пропишет bind/window_rule в hypr-user.lua.

## Запуск и управление

```fish
.venv/bin/python -m pill            # поднять фоновый демон (пилюля скрыта)
.venv/bin/python -m pill --toggle   # старт/стоп записи (на это висит bind Hyprland)
.venv/bin/python -m pill --settings # открыть настройки
.venv/bin/python -m pill --diag     # проверить ydotool/wl-copy и текущий бинд
```

Демон стартует сам при входе в Hyprland (`hl.on("hyprland.start", …)`), так что
обычно достаточно нажать бинд. Активировать запись можно биндом или `--toggle`.

## Настройки

Пилюля видна лишь во время записи, поэтому надёжный способ открыть настройки —
**лаунчер (пункт `Hyprland Voice Input`) или `python -m pill --settings`** (можно и по шестерёнке
на пилюле во время записи).

- **Горячая клавиша** — кнопка «Записать» временно берёт фокус, ловит
  следующую комбинацию и переписывает нативный bind Hyprland. На Wayland это работает
  через Qt и не требует доступа к `/dev/input` или членства в группе `input`.
- **Язык вывода** — Русский / English / Как в речи. `English` включает нативный
  `Whisper task="translate"`: русская и другая поддерживаемая речь переводится
  в нормальный английский текст. «Как в речи» только определяет и сохраняет язык.
- **Модель STT** — Tiny (быстро) / Small / Medium / **Large** (максимум точности,
  large-v3, ~3 ГБ при первом выборе — лучше всех берёт мат и редкую лексику).
- **Словари** — чипы **Мат** и **IT**: включают словарные пакеты biasing
  (см. ниже). «Мат» снимает самоцензуру Whisper, «IT» усиливает термины и латиницу.
- **Микрофон** — устройство ввода + чувствительность VAD.
- **Метод ввода** — Клавиатура (`wtype`/`ydotool`) или Буфер обмена (`wl-copy`;
  Ctrl+Shift+V выбирается автоматически для терминалов).
- **Положение пилюли** — сверху или снизу экрана; правило обновляется автоматически.

Интерфейс — стеклянная тема (полупрозрачные панели, глянец, глубина), вшитый
шрифт Adwaita Sans/Mono, векторные иконки (Canvas), кастомные easing. Раскрытие
настроек — единая поверхность: пилюля физически вырастает в карточку и ужимается
обратно. Высота карточки равна контенту — **скролла нет**. Для настоящего
frosted-blur включи глобальный blur (`blurEnabled = true` в `hypr-vars.lua`).

Три вкладки: **Настройки**, **Статистика** (символы/буквы/слова и время обработки —
за последнюю диктовку и всего) и **История** (последние 12 диктовок; клик по записи
копирует её в буфер — удобно, если вставка ушла не туда).

Всё пишется в `~/.config/pill/config.json`.

### Точность — распознавание мата и трудных слов

Базовый Whisper обучен на отфильтрованных данных: мат и редкую лексику он глушит —
выдаёт эвфемизм, соседнее слово или мусор. Лечится **на этапе декодирования**, а не
пост-правкой (она портит корректные редкие слова):

- **Пакеты словаря** (`packs`, чипы в настройках) — бандл-лексикон (`pill/vocab.py`).
  `"profanity"` и `"it"` дают `hotwords`, которые beam-search подхватывает охотнее.
  Для английского перевода используются отдельные английские целевые слова, чтобы
  русский словарь не уводил декодер обратно в транскрипцию. Пакеты комбинируются;
  по умолчанию включён `"profanity"`.
- **`beam_size`** — ширина beam-search (по умолчанию **5**; было 1). Заметно точнее
  на редких/матерных словах, на GPU почти бесплатно.
- **`vocabulary`** — свои hotwords через пробел (имена, термины, сленг):
  `"vocabulary": "Каэлестия Hyprland GitHub"`. Добавляются к пакетам.
- **`prompt`** — подсказка словаря/стиля для Whisper: имена, термины, контекст.
  `"prompt": "Пишем про Hyprland, Wayland, Python и GitHub."`
- **`replacements`** — словарь исправлений повторяющихся ослышек (регистронезависимо):
  `"replacements": {"гитхаб": "GitHub", "клауд": "Claude"}`. Применяется после
  распознавания, перед вставкой.

Плюс защита от зацикливания (`repetition_penalty`/`no_repeat_ngram_size`) — Whisper
больше не залипает на «…сука. …сука. …сука.».

## Скорость

- **GPU (NVIDIA):** `device="auto"` сам берёт CUDA/float16, если видит карту и
  установлены `nvidia-cublas-cu12`/`nvidia-cudnn-cu12` (pip). Тогда даже `medium`
  считается за ~0.2 с — точность модели сохраняется, скорость как у tiny на CPU.
  Без CUDA-библиотек тихо откатывается на CPU/int8. Форсировать: `device` в конфиге
  (`auto`/`cuda`/`cpu`).
- **Пауза до вставки** (слайдер в настройках, `silence_ms`) — сколько тишины ждать
  перед распознаванием. Меньше = быстрее реакция, но риск обрезать паузы в речи.
- Модель и VAD прогреваются на старте демона (`prewarm`), первая фраза не ждёт загрузку.

Итог на GPU: конец речи → вставка ≈ `пауза (по умолч. 500 мс)` + ~0.2 с инференса.

## Тесты

```fish
cd ~/hyprland-voice-input
for t in tests/test_*.py; env PYTHONPATH=. .venv/bin/python $t; or exit 1; end
```

Покрыты чистой логикой (без железа/моделей): VAD-гейт, фильтр галлюцинаций,
разбор/конвертация бинда, сборка команд ввода, генерация Lua-блока, конфиг,
статистика, IPC-lock, английский режим перевода и словарный biasing.

Проверено вживую под Hyprland 0.55.4: window_rule (float/pin/no_initial_focus,
низ по центру, фокус не украден), onnx-протокол Silero VAD (тишина 0.04 / речь 0.98),
API faster-whisper, фоновый демон (простой→скрыт, toggle→пилюля, авто-скрытие).

## Известные упрощения (ceiling)

- Whisper умеет переводить речь только **в English**. Выбор «Русский» означает
  качественное распознавание русской речи, а не обратный машинный перевод с English.
- `ydotool type` — аварийный фолбэк и не умеет надёжно печатать кириллицу;
  основной Wayland-бэкенд — `wtype`.
- Волна рисуется от RMS-уровня + рандома с подъёмом к центру, без реального FFT.
- Словарь свободного ввода (`vocabulary`/`prompt`) правится в `config.json`: окно
  без фокуса на Wayland, печатать в него нельзя — поэтому в UI пакеты-чипы, не поле.
- Интеграция целится в `~/.config/caelestia/hypr-user.lua`; для vanilla-Hyprland
  (не-Lua) добавьте эквивалентный `windowrulev2` вручную (см. `pill.hypr.lua`).
- Модель Silero тянется по фикс-URL с фолбэком; путь переопределяется
  `vad_model_path` в конфиге.
