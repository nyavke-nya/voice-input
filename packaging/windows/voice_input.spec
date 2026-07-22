# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: onedir + windowed VoiceInput.exe.

Onedir (не onefile): ML-зависимости крупные, onefile медленнее стартует и чаще
ловит ложные срабатывания антивирусов. Собирается ТОЛЬКО на Windows.
"""
import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

HERE = os.path.abspath(SPECPATH)                           # packaging/windows
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))     # корень репозитория

datas, binaries, hiddenimports = [], [], []

# QML-приложение: надёжнее всего собрать Qt целиком (плагины платформы + QML-
# модули QtQuick/Controls/Effects). ponytail: crude но работает с первого билда;
# после зелёной сборки можно сузить до конкретных модулей ради размера.
for pkg in ("PySide6", "faster_whisper", "ctranslate2", "onnxruntime", "sounddevice"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

hiddenimports += collect_submodules("pynput")
hiddenimports += collect_submodules("pill")

# CUDA намеренно не собирается внутрь Setup. На машине с NVIDIA установщик
# скачивает официальный runtime с PyPI в отдельный каталог gpu-runtime.

# Наши ресурсы: QML + встроенные шрифты + иконка (нужны и в source, и во frozen).
datas += [(os.path.join(ROOT, "pill", "qml"), os.path.join("pill", "qml"))]
datas += [(os.path.join(HERE, "voice-input.ico"), "pill")]

# Урезаем бандл: collect_all тянет ВЕСЬ Qt (WebEngine ~150 МБ, 3D, Charts, …).
# Это QML-приложение их не использует — выкидываем. Что реально нужно (QtQuick,
# QtQuick.Controls, QtQuick.Effects) проверяет усиленный `--self-test`, грузящий
# Main.qml offscreen: срезали лишнее -> self-test падает -> CI краснеет до релиза.
_QT_DROP = (
    "webengine", "webview", "webchannel", "quick3d", "qt63d", "charts",
    "datavisualization", "qt6graphs", "multimedia", "spatialaudio", "qt6pdf",
    "pdfquick", "virtualkeyboard", "designer", "qt6test", "qmltest", "quicktest",
    "sensors", "positioning", "qt6location", "serialport", "serialbus",
    "bluetooth", "qt6nfc", "remoteobjects", "scxml", "texttospeech",
    "qt6sql", "sqldrivers", "qt6quicktimeline",
)


def _keep(entry):
    hay = (entry[1] + "|" + entry[0]).lower().replace("\\", "/")
    if "pyside6" not in hay and "qt6" not in hay:
        return True  # не Qt — не трогаем (numpy, ctranslate2, onnxruntime, …)
    return not any(tok in hay for tok in _QT_DROP)


binaries = [b for b in binaries if _keep(b)]
datas = [d for d in datas if _keep(d)]

a = Analysis(
    [os.path.join(HERE, "voice_input.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[HERE],                 # локальные хуки, если понадобятся
    excludes=["evdev", "tkinter"],    # evdev — только Linux
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VoiceInput",
    console=False,                    # GUI без консольного окна
    icon=os.path.join(HERE, "voice-input.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="VoiceInput",
)
