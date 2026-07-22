# Voice Input for Windows

Голосовой ввод для Windows 10 и 11. Voice Input локально распознаёт речь через
Whisper и печатает текст в любое активное поле. Режим `English` переводит
русскую и другую поддерживаемую речь на английский.

Offline voice typing and speech-to-text for Windows 10/11. Dictate into any
focused text field, transcribe Russian speech or translate speech into English.
Audio stays on your computer.

## Скачать для Windows / Download

### [⬇ Скачать VoiceInputSetup.exe](https://github.com/nyavke/voice-input/releases/latest/download/VoiceInputSetup.exe)

Поддерживаются Windows 10 22H2 и Windows 11, только x64. Python и другие
зависимости уже находятся внутри установщика.

1. Скачайте `VoiceInputSetup.exe`.
2. Запустите установщик.
3. Откройте Voice Input через меню «Пуск» или ярлык на рабочем столе.

Первый релиз пока не подписан сертификатом. Если SmartScreen покажет
«Неизвестный издатель», у файла из этого репозитория можно нажать `Подробнее` →
`Выполнить в любом случае`. SHA-256 указан на странице релиза.

The first release is not code-signed. If SmartScreen warns about an unknown
publisher, check that the file came from this repository, then click `More
info` → `Run anyway`.

## Как пользоваться / How to use

1. Поставьте курсор в поле, куда нужно ввести текст.
2. Нажмите горячую клавишу, указанную в настройках Voice Input.
3. Говорите. После короткой паузы текст появится в поле.
4. Нажмите горячую клавишу ещё раз, чтобы закончить запись раньше.

Настройки языка, модели, микрофона и горячей клавиши открываются через Voice
Input в меню «Пуск» или через значок в трее.

| Режим / Mode | Что получится / Result |
| --- | --- |
| `Русский / Russian` | Распознавание русской речи |
| `English` | Перевод речи на английский |
| `Как в речи / As spoken` | Распознавание без перевода |

Whisper умеет переводить только на английский, поэтому других целевых языков в
меню нет.

## Скорость, GPU и размер

Windows-установщик занимает около 1.6 ГБ, потому что внутри уже есть CUDA,
cuBLAS и cuDNN. Совместимая видеокарта NVIDIA используется автоматически. Если
её нет, Voice Input продолжит работать на процессоре.

Скорость зависит от мощности видеокарты или процессора, выбранной модели
Whisper и длины фразы. Маленькие модели работают быстрее, большие обычно дают
более точный текст.

При первом запуске Voice Input скачает выбранную модель Whisper. После этого
распознавание работает локально, а аудио никуда не отправляется.

## Логи и удаление

Если приложение не запускается, приложите этот файл к GitHub issue:

```text
%LOCALAPPDATA%\Voice Input\logs\voice-input.log
```

Удаление: `Параметры → Приложения → Установленные приложения → Voice Input →
Удалить`. Удалитель отдельно спросит, нужно ли стереть настройки и модели.

## Linux

Linux тоже поддерживается, но основная готовая сборка сейчас предназначена для
Windows. Для Arch/CachyOS, Debian/Ubuntu, Fedora, openSUSE и Void:

```bash
git clone https://github.com/nyavke/voice-input.git
cd voice-input
./install.sh --dry-run
./install.sh
```

Установщик работает с Wayland и X11, включая Hyprland, Sway, GNOME, KDE,
Cinnamon и XFCE. Alpine/musl пока не поддерживается.

## Ошибки / Bugs

Создайте [GitHub issue](https://github.com/nyavke/voice-input/issues/new/choose)
или напишите в Telegram: [@nyavke](https://t.me/nyavke). Укажите версию Windows
и Voice Input, а также приложите лог.
