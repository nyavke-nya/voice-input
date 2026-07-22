# Voice Input — сборка под Windows

Установщик `VoiceInputSetup.exe` ставится **per-user без прав администратора**,
кладёт `VoiceInput.exe` (onedir, PyInstaller) в `%LOCALAPPDATA%\Programs\Voice Input`,
добавляет ярлыки в меню «Пуск» / на рабочий стол и (опционально) в автозапуск.
Python, `.py`, консоль и ручная установка зависимостей пользователю не видны.

## Файлы

| Файл | Назначение |
|------|-----------|
| `voice_input.spec` | PyInstaller: onedir + windowed `VoiceInput.exe` |
| `voice_input.py` | frozen-entry (пакет `pill` как приложение) |
| `voice-input.iss` | Inno Setup 6.3+: per-user installer/uninstaller |
| `voice-input.ico` / `.svg` | иконка (EXE, tray, ярлыки, installer) |
| `build.ps1` | одна команда: venv → PyInstaller → smoke-test → Inno |
| `requirements-windows.txt` | зависимости (CPU-база) |
| `install-gpu-runtime.ps1` | загрузка проверенных CUDA DLL с PyPI во время установки |

## Сборка одной командой (bootstrap)

`bootstrap.ps1` сам ставит Python 3.12 и Inno Setup (winget, per-user, без админа),
качает проект (git не нужен) и собирает. Ничего заранее ставить не надо — только
Windows 10 22H2+/11 и интернет. В PowerShell:

```powershell
irm https://raw.githubusercontent.com/nyavke/voice-input/main/packaging/windows/bootstrap.ps1 | iex
```

Результат: `dist\VoiceInputSetup.exe` (или `dist\VoiceInput\VoiceInput.exe`, если Inno не встал).
Текущий CPU-артефакт CI весит около 230 МБ; точный размер немного зависит от
версий зависимостей.

## Ручная сборка

Если Python 3.12 x64 и Inno Setup 6.3+ уже в `PATH`:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1 -SkipInstaller  # без Inno
```

## GPU

Setup всегда собирается компактным, без CUDA. Если найден драйвер NVIDIA, мастер
показывает включённый по умолчанию пункт ускорения и во время установки скачивает
с официального PyPI cuBLAS, cuDNN, CUDA Runtime и NVRTC (около 1,3 ГБ). SHA-256
каждого wheel проверяется по метаданным PyPI; DLL попадают в `{app}\gpu-runtime`.
Без NVIDIA этого пункта нет и приложение работает на CPU. Отдельный CUDA Toolkit
не нужен. Проверка: после диктовки в `%LOCALAPPDATA%\Voice Input\logs\voice-input.log`
должно быть `STT: … на cuda`.

## Подпись (опционально)

Если задать `$env:PILL_PFX` (путь к `.pfx`) и `$env:PILL_PFX_PASSWORD`, `build.ps1`
подпишет EXE и installer через `signtool`. Без сертификата сборка проходит, но
артефакт **unsigned**. В CI — секреты `SIGN_PFX_BASE64` и `SIGN_PFX_PASSWORD`.
Сертификаты и пароли в репозиторий не коммитятся.

## CI

`.github/workflows/windows.yml`: проверка исходников и PowerShell, сборка EXE и
installer, `--self-test`, загрузка компактного `VoiceInputSetup.exe` как artifact.

## Ручная проверка на чистой Windows (Sandbox / VM без Python)

1. Silent install без UAC и ошибок.
2. В «Пуск» и на рабочем столе — правильные имя и иконка.
3. После входа приложение появляется в трее один раз.
4. Ярлык открывает настройки; второй экземпляр не создаётся.
5. Hotkey начинает/останавливает запись.
6. Русский текст в Notepad; English mode переводит; clipboard mode вставляет Unicode.
7. Микрофон и список устройств; понятное сообщение при отказе в доступе.
8. UI на 1366×768 и масштабах 100/125/150%.
9. Перезагрузка сохраняет config, hotkey, статистику, model cache.
10. Upgrade сохраняет данные; uninstall удаляет программу и ярлыки, но по умолчанию
    не трогает модели/настройки.
11. На машине без Python приложение работает.
