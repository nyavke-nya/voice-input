# Voice Input for Windows and Linux

Локальный голосовой ввод на базе Whisper. Программа распознаёт речь прямо на
компьютере и печатает текст в активное поле. Режим `English` переводит русскую
и другую поддерживаемую речь на английский.

Voice Input is a local Whisper-based dictation app for Windows and Linux. It
types recognized speech into the focused field and can translate supported
speech into English. Audio stays on your computer.

## Windows

[Скачать VoiceInputSetup.exe / Download for Windows](https://github.com/nyavke/voice-input/releases/latest/download/VoiceInputSetup.exe)

Поддерживаются 64-битные Windows 10 22H2 и Windows 11.

1. Скачайте `VoiceInputSetup.exe` со страницы Releases.
2. Запустите установщик.
3. Откройте Voice Input через меню «Пуск» или ярлык на рабочем столе.

При первом запуске программа скачает выбранную модель Whisper. Windows-сборка
включает библиотеки NVIDIA, поэтому занимает около 1.6 ГБ. Совместимая
видеокарта используется автоматически; без неё приложение работает на CPU.
Скорость зависит от мощности видеокарты или процессора, выбранной модели и
длины фразы.

The first launch downloads the selected Whisper model. The Windows build is
about 1.6 GB because it includes the NVIDIA runtime. A compatible GPU is used
automatically, with a CPU fallback. Recognition speed depends on GPU or CPU
performance, the selected model and the length of the recording.

Установщик пока не подписан сертификатом, поэтому SmartScreen может показать
предупреждение «Неизвестный издатель». Скачивайте EXE только из Releases этого
репозитория; контрольная сумма указана на странице релиза.

## Linux

```bash
git clone https://github.com/nyavke/voice-input.git
cd voice-input
./install.sh --dry-run
./install.sh
```

Запускайте скрипт от обычного пользователя. `--dry-run` покажет план без
изменений. Установщик определит дистрибутив, окружение и Wayland/X11, а в конце
крупно напечатает настроенную горячую клавишу.

Run the script as your normal user. `--dry-run` changes nothing. The installer
detects the distro, desktop and display server, then prints the configured
hotkey at the end.

## Использование / Usage

1. Поставьте курсор в нужное поле.
2. Нажмите горячую клавишу из настроек.
3. Говорите и сделайте короткую паузу. Текст вставится сам.
4. Нажмите клавишу ещё раз, чтобы остановить запись раньше.

Focus a text field, press the configured hotkey, speak and pause. Open Voice
Input from the Start/app menu to change the language, model, microphone or
hotkey.

В Linux приложение также можно открыть командой `voice-input --settings` или
`./run.sh` из каталога проекта.

| Режим / Mode | Результат / Result |
| --- | --- |
| `Русский / Russian` | Русская транскрипция / Russian transcription |
| `English` | Перевод речи на английский / Speech translated into English |
| `Как в речи / As spoken` | Без перевода / No translation |

Whisper переводит только на английский, поэтому других целевых языков в меню
нет. Whisper translates only into English, so other target languages are not
listed.

## Совместимость / Compatibility

- Windows 10 22H2 и Windows 11, x64
- Arch/CachyOS/Manjaro, Debian/Ubuntu/Mint, Fedora, openSUSE и Void
- Wayland и X11
- Hyprland/caelestia, Sway, i3 и GNOME с нативной горячей клавишей
- KDE, Cinnamon, XFCE и другие Linux-окружения через `evdev` fallback

Для Linux нужен Python 3.9 или новее. Alpine/musl пока не поддерживается из-за
отсутствия необходимых wheels. Windows-установщик уже содержит Python и все
зависимости.

## Диагностика / Diagnostics

Windows пишет лог сюда:

```text
%LOCALAPPDATA%\Voice Input\logs\voice-input.log
```

Linux-команды:

```bash
voice-input --diag
voice-input --toggle
voice-input --quit
```

## Удаление / Uninstall

В Windows откройте «Параметры → Приложения → Установленные приложения → Voice
Input → Удалить». Удаление предложит отдельно стереть настройки и модели.

В Linux:

```bash
./uninstall.sh --dry-run
./uninstall.sh
```

Обычное удаление сохраняет настройки, модели и общие системные пакеты. Команда
`./uninstall.sh --purge` также удаляет настройки и кэш приложения.

## Ошибки / Bugs

Создайте [GitHub issue](https://github.com/nyavke/voice-input/issues/new/choose)
или напишите в Telegram: [@nyavke](https://t.me/nyavke).

Укажите Windows/Linux, версию системы и приложите Windows-лог или вывод
`voice-input --diag` в Linux.
