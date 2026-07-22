"""UI: плавающая «Пилюля» на PySide6/QML + оркестрация всего пайплайна.

Backend (QObject) — единственный мост между QML и Python-логикой. Он держит
AudioRecorder, SttEngine, TextInjector и дёргает их по состояниям:

    idle --toggle--> recording --(VAD:тишина>silence_ms | toggle)--> processing
      ^                                                                  |
      +---------------------------- вставка текста ----------------------+

Сигналы из рабочих потоков (аудио/STT) эмитятся напрямую — PySide ставит их в
очередь GUI-потока, так что дополнительной синхронизации не нужно.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
import urllib.request
from typing import Optional

from PySide6.QtCore import Property, QKeyCombination, QObject, QTimer, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication, QKeySequence, QRegion
from PySide6.QtQml import QQmlApplicationEngine

from . import config, desktop_integration, paths, stats
from .audio_recorder import AudioRecorder
from .hotkey import canonical_combo, capture_once
from .stt_engine import SttEngine
from .text_injector import TextInjector

VERSION = "1.1.0"
_WIN = sys.platform.startswith("win")

RELEASES_API = "https://api.github.com/repos/nyavke-nya/voice-input/releases/latest"
RELEASES_PAGE = "https://github.com/nyavke-nya/voice-input/releases/latest"


def _parse_version(tag: str) -> tuple:
    """'v1.0.0' -> (1, 0, 0); нечисловое отбрасывается, чтобы сравнение не падало."""
    return tuple(int(n) for n in re.findall(r"\d+", tag)) or (0,)


def _qt_hotkey_combo(key: int, modifiers: int) -> Optional[str]:
    """Превратить Qt KeyEvent в каноничный bind; один модификатор ещё не bind."""
    modifier_keys = {
        int(Qt.Key.Key_Control), int(Qt.Key.Key_Alt), int(Qt.Key.Key_AltGr),
        int(Qt.Key.Key_Shift), int(Qt.Key.Key_Meta),
    }
    if key in modifier_keys:
        return None
    allowed = (
        Qt.KeyboardModifier.ControlModifier
        | Qt.KeyboardModifier.AltModifier
        | Qt.KeyboardModifier.ShiftModifier
        | Qt.KeyboardModifier.MetaModifier
    )
    mods = Qt.KeyboardModifier(modifiers) & allowed
    sequence = QKeySequence(QKeyCombination(mods, Qt.Key(key))).toString(
        QKeySequence.SequenceFormat.PortableText
    )
    try:
        return canonical_combo(sequence)
    except (TypeError, ValueError):
        return None


class Backend(QObject):
    stateChanged = Signal()
    levelChanged = Signal()
    settingsChanged = Signal()
    expandedChanged = Signal()
    capturingChanged = Signal()
    statsChanged = Signal()
    notify = Signal(str)               # текст всплывашки для QML/notify-send
    updateAvailableChanged = Signal()  # найден более новый GitHub-релиз
    _toggleRequested = Signal()        # маршалинг toggle в GUI-поток
    _settingsRequested = Signal()      # маршалинг «открыть настройки» в GUI-поток
    _quitRequested = Signal()          # IPC-thread -> GUI event loop
    _hotkeyCaptured = Signal(int, str)  # serial отсекает запоздалый timeout
    _hotkeyCaptureFailed = Signal(int, str)

    def __init__(self, cfg: dict):
        super().__init__()
        self._cfg = cfg
        self._state = "idle"
        self._level = 0.0
        self._expanded = False
        self._capturing = False
        self._capture_serial = 0
        self._stats = stats.load()
        self._update_available = False
        self._latest_version = ""
        self._tray = None  # QSystemTrayIcon на Windows; ставит build_app
        self.on_hotkey_changed = lambda combo: None  # ставит __main__ (evdev/pynput)

        self.recorder = AudioRecorder(cfg)
        self.recorder.on_level = self._on_level
        self.recorder.on_utterance = self._on_utterance
        self.recorder.on_error = self._on_error
        self.stt = SttEngine(cfg)
        self.injector = TextInjector(cfg)

        self._device_names, self._device_indices = self._list_devices()
        self._toggleRequested.connect(self._do_toggle)
        self._settingsRequested.connect(self._do_settings)
        self._quitRequested.connect(QGuiApplication.quit)
        self._hotkeyCaptured.connect(self._on_captured)
        self._hotkeyCaptureFailed.connect(self._on_capture_failed)

    # ---- внешние точки входа (сокет), безопасны из любого потока ----
    def request_toggle(self) -> None:
        self._toggleRequested.emit()

    def request_settings(self) -> None:
        self._settingsRequested.emit()

    def request_quit(self) -> None:
        self._quitRequested.emit()

    @Slot()
    def _do_settings(self) -> None:
        self.expanded = True

    # ---- состояние ----
    def _set_state(self, s: str) -> None:
        if s != self._state:
            self._state = s
            self.stateChanged.emit()

    @Slot()
    def _do_toggle(self) -> None:
        if self._state == "processing":
            return
        if self._state == "idle":
            self._set_state("recording")
            self.recorder.start()
        else:  # recording -> форсированный конец фразы
            self.recorder.stop()

    def _on_level(self, v: float) -> None:
        self._level = v
        self.levelChanged.emit()

    def _on_utterance(self, audio) -> None:
        if audio is None:
            self._set_state("idle")
            return
        self._set_state("processing")
        audio_sec = len(audio) / 16000.0
        t0 = time.perf_counter()
        try:
            text = self.stt.transcribe(audio)
        except Exception as e:  # noqa: BLE001
            self._on_error(f"STT: {e}")
            return
        proc_sec = time.perf_counter() - t0
        if text:
            inserted = self.injector.inject(text)
            try:
                stats.record(self._stats, text, proc_sec, audio_sec)
                stats.save(self._stats)
                self.statsChanged.emit()
            except OSError as e:
                self._on_error(f"Статистика: {e}")
                return
            if not inserted:
                detail = f": {self.injector.last_error}" if self.injector.last_error else ""
                self._on_error(f"Не удалось вставить текст{detail}")
                return
        self._set_state("idle")

    def _desktop_notify(self, msg: str) -> None:
        """Всплывашка ОС: трей на Windows, notify-send на Linux."""
        if self._tray is not None:
            self._tray.showMessage("Voice Input", msg)
            return
        if not _WIN:
            try:
                subprocess.run(["notify-send", "Voice Input", msg], check=False)
            except OSError:
                pass

    def _show_error(self, msg: str) -> None:
        print(f"[voice-input] ошибка: {msg}")
        self.notify.emit(msg)
        self._desktop_notify(msg)

    def _on_error(self, msg: str) -> None:
        self._show_error(msg)
        self._set_state("idle")

    # ---- прогрев, чтобы уложиться в 300–600мс на первой фразе ----
    def prewarm(self) -> None:
        threading.Thread(target=self.stt.warmup, daemon=True).start()

        def vad():
            try:
                self.recorder._ensure_vad()
            except Exception as e:  # noqa: BLE001
                self._show_error(str(e))

        threading.Thread(target=vad, daemon=True).start()
        threading.Thread(target=self._check_updates, daemon=True).start()

    def _check_updates(self) -> None:
        """Раз при старте: сравнить VERSION с последним GitHub-релизом. Тихо при офлайне."""
        try:
            req = urllib.request.Request(
                RELEASES_API,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "voice-input"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                tag = json.load(resp).get("tag_name", "")
        except Exception:  # noqa: BLE001 — офлайн/лимит/нет релизов: просто без апдейта
            return
        if tag and _parse_version(tag) > _parse_version(VERSION):
            self._latest_version = tag.lstrip("vV")
            self._update_available = True
            self.updateAvailableChanged.emit()

    def _list_devices(self):
        names, idx = ["По умолчанию"], [None]
        try:
            import sounddevice as sd

            for i, d in enumerate(sd.query_devices()):
                if d["max_input_channels"] > 0:
                    names.append(d["name"])
                    idx.append(i)
        except Exception:  # noqa: BLE001
            pass
        return names, idx

    def _save(self) -> None:
        config.save(self._cfg)

    # ================= свойства для QML =================
    @Property(str, notify=stateChanged)
    def appState(self):
        return self._state

    @Property(float, notify=levelChanged)
    def level(self):
        return self._level

    def _get_expanded(self):
        return self._expanded

    def _set_expanded(self, v: bool):
        if v != self._expanded:
            self._expanded = v
            self.expandedChanged.emit()

    expanded = Property(bool, _get_expanded, _set_expanded, notify=expandedChanged)

    @Property(str, constant=True)
    def version(self):
        return VERSION

    @Property(bool, notify=updateAvailableChanged)
    def updateAvailable(self):
        return self._update_available

    @Property(str, notify=updateAvailableChanged)
    def latestVersion(self):
        return self._latest_version

    @Property(str, constant=True)
    def releasesUrl(self):
        return RELEASES_PAGE

    @Property(bool, constant=True)
    def isWayland(self):
        import os
        return bool(os.environ.get("WAYLAND_DISPLAY"))

    @Property(bool, constant=True)
    def isWindows(self):
        return _WIN

    @Property("QStringList", constant=True)
    def devices(self):
        return self._device_names

    @Property("QVariantMap", notify=statsChanged)
    def stats(self):
        s = self._stats
        n = s["count"] or 1
        return {
            "count": s["count"],
            "chars": s["chars"], "letters": s["letters"], "words": s["words"],
            "audioSec": round(s["audio_sec"], 1),
            "avgProcMs": round(s["proc_sec"] / n * 1000) if s["count"] else 0,
            "lastChars": s["last"]["chars"], "lastLetters": s["last"]["letters"],
            "lastWords": s["last"]["words"], "lastProcMs": s["last"]["proc_ms"],
            "lastAudioMs": s["last"]["audio_ms"],
        }

    @Property("QVariantList", notify=statsChanged)
    def history(self):
        return self._stats.get("history", [])

    @Slot(int)
    def copyHistory(self, i: int):
        h = self._stats.get("history", [])
        if 0 <= i < len(h):
            QGuiApplication.clipboard().setText(h[i]["text"])
            self.notify.emit("Скопировано в буфер")
            self._desktop_notify("Скопировано в буфер")

    @Slot()
    def resetStats(self):
        self._stats = stats.fresh()
        stats.save(self._stats)
        self.statsChanged.emit()

    # -- настройки (двусторонние) --
    def _mk(attr, allowed=None):
        def getter(self):
            return self._cfg[attr]

        def setter(self, v):
            if allowed and v not in allowed:
                return
            if v == self._cfg[attr]:
                return
            self._cfg[attr] = v
            self._save()
            self.settingsChanged.emit()

        return getter, setter

    language = Property(str, *_mk("language", {"ru", "en", "auto"}), notify=settingsChanged)
    model = Property(str, *_mk("model", {"tiny", "small", "medium", "large"}), notify=settingsChanged)
    inputMethod = Property(
        str, *_mk("input_method", {"keyboard", "clipboard"}), notify=settingsChanged
    )
    theme = Property(int, *_mk("theme", set(range(10))), notify=settingsChanged)

    # -- словарные пакеты biasing (Мат / IT): включаются чипами, без ввода текста
    #    (окно без фокуса на Wayland — печатать в него нельзя) --
    @Property("QStringList", notify=settingsChanged)
    def packs(self):
        return list(self._cfg.get("packs", []))

    @Slot(str)
    def togglePack(self, name: str):
        from .vocab import PACKS

        if name not in PACKS:
            return
        cur = list(self._cfg.get("packs", []))
        self._cfg["packs"] = [p for p in cur if p != name] if name in cur else cur + [name]
        self._save()
        self.settingsChanged.emit()

    def _get_vad(self):
        return float(self._cfg["vad_sensitivity"])

    def _set_vad(self, v):
        v = min(1.0, max(0.0, float(v)))
        if v != self._cfg["vad_sensitivity"]:
            self._cfg["vad_sensitivity"] = v
            self._save()
            self.settingsChanged.emit()

    vadSensitivity = Property(float, _get_vad, _set_vad, notify=settingsChanged)

    def _get_silence(self):
        return int(self._cfg["silence_ms"])

    def _set_silence(self, v):
        v = max(100, int(v))
        if v != self._cfg["silence_ms"]:
            self._cfg["silence_ms"] = v
            self._save()
            self.settingsChanged.emit()

    silenceMs = Property(int, _get_silence, _set_silence, notify=settingsChanged)

    def _get_hotkey(self):
        return self._cfg["hotkey"]

    def _set_hotkey(self, v):
        try:
            v = canonical_combo(str(v))
        except ValueError:
            self.notify.emit(f"Некорректный бинд: {v}")
            return
        if v != self._cfg["hotkey"]:
            self._cfg["hotkey"] = v
            self._save()
            desktop_integration.install(v)
            self.on_hotkey_changed(v)  # обновит evdev/pynput-слушатель, если активен
            self.settingsChanged.emit()

    hotkey = Property(str, _get_hotkey, _set_hotkey, notify=settingsChanged)

    # -- перехват новой комбинации (кнопка «Записать») --
    @Property(bool, notify=capturingChanged)
    def capturing(self):
        return self._capturing

    def _set_capturing(self, v: bool):
        if v != self._capturing:
            self._capturing = v
            self.capturingChanged.emit()

    @Slot()
    def captureHotkey(self):
        if self._capturing:
            self._capture_serial += 1
            self._set_capturing(False)
            return
        self._capture_serial += 1
        serial = self._capture_serial
        self._set_capturing(True)
        # Wayland не даёт клиенту глобально слушать клавиату. QML на время
        # захвата снимает WindowDoesNotAcceptFocus и передаёт клавишу сюда.
        if self.isWayland:
            QTimer.singleShot(
                15_000,
                lambda: self._hotkeyCaptureFailed.emit(
                    serial, "Время ожидания комбинации истекло"
                ),
            )
            return
        capture_once(
            lambda combo: self._hotkeyCaptured.emit(serial, combo),
            lambda message: self._hotkeyCaptureFailed.emit(serial, message),
        )

    @Slot(int, int)
    def captureQtHotkey(self, key: int, modifiers: int):
        """Принять одно нажатие из сфокусированного QML-окна на Wayland."""
        if not self._capturing:
            return
        combo = _qt_hotkey_combo(key, modifiers)
        if combo is None:
            return
        self._hotkeyCaptured.emit(self._capture_serial, combo)

    @Slot(int, str)
    def _on_captured(self, serial: int, combo: str):
        if serial != self._capture_serial or not self._capturing:
            return
        self._set_capturing(False)
        self.hotkey = combo  # сеттер валидирует, сохраняет, ставит bind, оповещает UI

    @Slot(int, str)
    def _on_capture_failed(self, serial: int, message: str):
        if serial != self._capture_serial or not self._capturing:
            return
        self._set_capturing(False)
        self._show_error(message)

    def _get_device_index(self):
        cur = self._cfg["input_device"]
        return self._device_indices.index(cur) if cur in self._device_indices else 0

    def _set_device_index(self, i):
        if 0 <= i < len(self._device_indices):
            value = self._device_indices[i]
            if value == self._cfg["input_device"]:
                return
            self._cfg["input_device"] = value
            self._save()
            self.settingsChanged.emit()

    deviceIndex = Property(int, _get_device_index, _set_device_index, notify=settingsChanged)

    # -- действия из QML --
    @Slot()
    def toggle(self):
        self._do_toggle()

    @Slot()
    def showSettings(self):
        self.expanded = True

    @Slot()
    def quitApp(self):
        QGuiApplication.quit()

    def shutdown(self) -> None:
        self.recorder.stop()
        self.recorder.join()


def _install_tray(app, backend) -> None:
    """Иконка в трее (только Windows): клик открывает настройки; меню и tooltip."""
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QMenu, QSystemTrayIcon

    ico = paths.icon_path()
    icon = QIcon(str(ico)) if ico else app.windowIcon()
    app.setWindowIcon(icon)
    tray = QSystemTrayIcon(icon, app)
    menu = QMenu()
    menu.addAction("Начать / остановить запись").triggered.connect(backend.request_toggle)
    menu.addAction("Настройки").triggered.connect(backend.request_settings)
    menu.addSeparator()
    menu.addAction("Выход").triggered.connect(backend.quitApp)
    tray.setContextMenu(menu)

    def _tooltip():
        tray.setToolTip(f"Voice Input · {backend.hotkey}")

    _tooltip()
    backend.settingsChanged.connect(_tooltip)  # обновить при смене хоткея
    tray.activated.connect(
        lambda reason: backend.request_settings()
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick)
        else None
    )
    tray.show()
    backend._tray = tray
    backend._tray_menu = menu  # удержать ссылку от GC


def build_app(cfg: dict):
    """Создать приложение + движок QML. Возвращает (app, backend, engine)."""
    if _WIN:  # трей/меню — виджеты, нужен QApplication
        from PySide6.QtWidgets import QApplication
        app = QApplication(sys.argv)
    else:
        app = QGuiApplication(sys.argv)
    app.setApplicationName("pill")
    app.setApplicationDisplayName("Voice Input")
    app.setDesktopFileName("pill")  # -> app_id/class для оконных правил Hyprland
    app.setQuitOnLastWindowClosed(False)  # демон живёт, когда пилюля скрыта
    backend = Backend(cfg)
    if _WIN:
        _install_tray(app, backend)
    engine = QQmlApplicationEngine()
    engine.setParent(backend)  # QML должен уничтожиться раньше context-property backend
    engine.rootContext().setContextProperty("backend", backend)
    qml = paths.resource_path("qml", "Main.qml")  # source checkout и onedir(_MEIPASS)
    engine.load(QUrl.fromLocalFile(str(qml)))
    if not engine.rootObjects():
        raise RuntimeError("QML не загрузился")
    window = engine.rootObjects()[0]

    def sync_input_region():
        region = window.property("inputRegion")
        if region is not None:
            window.setMask(QRegion(region.toAlignedRect()))

    window.inputRegionChanged.connect(sync_input_region)
    window._sync_input_region = sync_input_region  # удержать Python-callback
    sync_input_region()

    def teardown_qml():
        for root in engine.rootObjects():
            root.deleteLater()
        engine.deleteLater()

    app.aboutToQuit.connect(teardown_qml)
    backend._teardown_qml = teardown_qml
    return app, backend, engine


if __name__ == "__main__":  # self-check: сравнение версий для баннера обновления
    assert _parse_version("v1.0.0") > _parse_version("0.1.2")
    assert _parse_version("v0.1.2") == _parse_version("0.1.2")
    assert not (_parse_version("0.1.2") > _parse_version("0.1.2"))
    assert _parse_version("v1.0.0") > _parse_version("v0.9.9")
    print("ui self-check ok")
