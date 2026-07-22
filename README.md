# Voice Input for Linux

Локальный голосовой ввод для Linux на базе Whisper. Программа печатает диктовку
в активное поле, а режим `English` переводит русскую и другую поддерживаемую
речь на английский. Аудио обрабатывается на компьютере.

Voice Input for Linux is an offline speech-to-text app built on Whisper. Use it
for voice typing and dictation in focused fields on Wayland or X11. It can also
translate supported speech into English.

## Установка / Install

```bash
git clone https://github.com/nyavke/voice-input.git
cd voice-input
./install.sh --dry-run
./install.sh
```

Запускайте скрипт от обычного пользователя. `--dry-run` покажет план без
изменений. Установщик определит дистрибутив, окружение и Wayland/X11. В конце он
крупно напечатает настроенную горячую клавишу.

Run the script as your normal user. `--dry-run` changes nothing. The installer
detects the distro, desktop and display server, then prints the configured
hotkey at the end.

## Использование / Usage

1. Поставьте курсор в нужное поле.
2. Нажмите горячую клавишу, напечатанную установщиком.
3. Говорите и сделайте короткую паузу. Текст вставится сам.
4. Нажмите клавишу ещё раз, чтобы остановить запись раньше.

Focus a text field, press the printed hotkey, speak and pause. Open `Voice Input`
from the app menu for settings, or run `voice-input --settings`.

Из каталога проекта приложение можно открыть командой `./run.sh`.
From the project directory, run `./run.sh` to open the app.

| Режим / Mode | Результат / Result |
| --- | --- |
| `Русский / Russian` | Русская транскрипция / Russian transcription |
| `English` | Перевод речи на английский / Speech translated into English |
| `Как в речи / As spoken` | Без перевода / No translation |

Whisper переводит только на английский, поэтому других целевых языков в меню
нет. Whisper translates only into English, so other target languages are not
listed.

## Совместимость / Compatibility

- Arch/CachyOS/Manjaro, Debian/Ubuntu/Mint, Fedora, openSUSE и Void
- Wayland и X11
- Hyprland/caelestia, Sway, i3 и GNOME с нативной горячей клавишей
- KDE, Cinnamon, XFCE и другие окружения через `evdev` fallback

Нужен Python 3.9 или новее. Alpine/musl пока не поддерживается, потому что
необходимые Python wheels для musl отсутствуют.

Python 3.9 or newer is required. Alpine/musl is not supported yet because the
required Python wheels are unavailable for musl.

## Диагностика / Diagnostics

```bash
voice-input --diag
voice-input --toggle
voice-input --quit
```

Если `~/.local/bin` ещё не входит в `PATH`, используйте `./voice-input`. Установка
и первый запуск могут занять больше времени из-за загрузки модели.

## Удаление / Uninstall

```bash
./uninstall.sh --dry-run
./uninstall.sh
```

Обычное удаление сохраняет настройки, модели и общие системные пакеты. Команда
`./uninstall.sh --purge` также удаляет настройки и кэш приложения.

The normal uninstall keeps settings, models and shared system packages. Add
`--purge` to remove the app settings and cache too.

## Ошибки / Bugs

Создайте [GitHub issue](https://github.com/nyavke/voice-input/issues/new/choose)
или напишите в Telegram: [@nyavke](https://t.me/nyavke).

Please include your distro, desktop, Wayland/X11 and the output of
`voice-input --diag`.
