"""Точка входа: `python -m pill`.

Фоновый демон в одной копии. Команды работающему демону — через локальный сокет
(Unix на Linux, TCP 127.0.0.1 на Windows):

    python -m pill            # запустить демон (или ничего, если уже запущен)
    python -m pill --toggle   # старт/стоп записи (глобальный bind / ярлык)
    python -m pill --settings # открыть настройки
    python -m pill --diag     # диагностика
    python -m pill --quit     # завершить демон

Триггер записи: нативный bind поддерживаемого desktop/WM, иначе универсальный
глобальный хоткей — evdev на Linux, pynput на Windows.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time

from . import config

_WIN = sys.platform.startswith("win")
_TCP_PORT = 47187  # localhost, для Windows-IPC
_USAGE = """Voice Input

Usage: voice-input [OPTION]

  --toggle     start or stop dictation / начать или остановить диктовку
  --settings   open settings / открыть настройки
  --diag       print diagnostics / показать диагностику
  --quit       stop the daemon / остановить демон
  -h, --help   show this help / показать справку
"""


def _sock_path():
    return config.cache_dir() / "pill.sock"


def _client():
    if _WIN:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(("127.0.0.1", _TCP_PORT))
        return s
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(0.5)
    s.connect(str(_sock_path()))
    return s


def _send(msg: bytes) -> bool:
    """Отправить команду работающему демону. False, если он не запущен."""
    if not _WIN and not _sock_path().exists():
        return False
    try:
        with _client() as s:
            s.sendall(msg)
        return True
    except OSError:
        return False


def _instance_lock():
    """Взять неблокирующий lock демона. На Windows уникальность даёт TCP bind."""
    if _WIN:
        return None
    import fcntl

    path = config.cache_dir() / "pill.lock"
    handle = path.open("a+b")
    os.chmod(path, 0o600)
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return False
    return handle


def _prepare_server():
    if _WIN:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", _TCP_PORT))
    else:
        p = _sock_path()
        if p.exists():
            p.unlink()  # снять устаревший сокет
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(str(p))
        os.chmod(p, 0o600)
    srv.listen()
    return srv


def _serve(backend, srv) -> None:
    while True:
        try:
            conn, _ = srv.accept()
        except OSError:
            break
        with conn:
            data = conn.recv(64)
        command = data.strip()
        if command == b"toggle":
            backend.request_toggle()
        elif command == b"settings":
            backend.request_settings()
        elif command == b"quit":
            backend.request_quit()
            break
        # b"ping" — просто подтверждение, что демон жив


def main() -> int:
    args = sys.argv[1:]

    if args in (["-h"], ["--help"]):
        print(_USAGE, end="")
        return 0
    known = {"--toggle", "--settings", "--diag", "--quit"}
    if len(args) > 1 or (args and args[0] not in known):
        bad = " ".join(args) or "<empty>"
        print(f"Unknown option / Неизвестный параметр: {bad}\n", file=sys.stderr)
        print(_USAGE, end="", file=sys.stderr)
        return 2

    if args == ["--diag"]:
        from .desktop_integration import detect
        from .text_injector import TextInjector

        print("config:", config.config_path())
        print("platform:", sys.platform)
        print("desktop:", detect().label)
        print("injection:", TextInjector.diagnostics())
        print("hotkey:", config.load()["hotkey"])
        return 0

    want = args[0][2:] if args else "start"
    command = {"toggle": b"toggle", "settings": b"settings", "quit": b"quit", "start": b"ping"}[want]
    if _send(command):
        return 0
    if want == "quit":
        return 0

    lock = _instance_lock()
    if lock is False:
        # Другой процесс уже выиграл гонку запуска, но мог ещё не поднять сокет.
        for _ in range(20):
            time.sleep(0.05)
            if _send(command):
                return 0
        print("[voice-input] демон уже запускается, но сокет пока недоступен", file=sys.stderr)
        return 1
    try:
        srv = _prepare_server()
    except OSError as e:
        if _send(command):
            return 0
        print(f"[voice-input] не удалось открыть IPC: {e}", file=sys.stderr)
        if lock:
            lock.close()
        return 1

    cfg = config.load()
    from PySide6.QtCore import QTimer

    from . import desktop_integration
    from .hotkey import make_listener
    from .ui import build_app

    app, backend, engine = build_app(cfg)
    backend.notify.connect(lambda m: print(f"[voice-input] {m}"))

    native_hotkey = desktop_integration.install(
        cfg["hotkey"], cfg.get("pill_position", "bottom")
    )

    def _restart() -> None:
        # Некоторые WM применяют позицию только при новом маппинге окна.
        if not _WIN:
            try:
                _sock_path().unlink()
            except OSError:
                pass
        os.execv(sys.executable, [sys.executable, "-m", "pill"])

    backend.on_restart = _restart

    listener = None
    if not native_hotkey:  # нет нативного бинда -> универсальный слушатель
        listener = make_listener(cfg["hotkey"], backend.request_toggle)
        backend.on_hotkey_changed = listener.set_combo
        try:
            listener.start()
            print("[voice-input] хоткей через", "pynput" if _WIN else "evdev")
        except Exception as e:  # noqa: BLE001
            print(f"[voice-input] не удалось запустить хоткей: {e} (используйте --toggle)")

    threading.Thread(target=_serve, args=(backend, srv), daemon=True).start()
    backend.prewarm()

    if want == "settings":
        backend.showSettings()
    elif want == "toggle":
        QTimer.singleShot(400, backend.request_toggle)

    print(f"[voice-input] демон запущен. бинд: {cfg['hotkey']} | команда: voice-input --toggle")
    try:
        return app.exec()
    finally:
        backend.shutdown()
        if listener is not None:
            listener.stop()
        srv.close()
        if not _WIN:
            try:
                _sock_path().unlink()
            except OSError:
                pass
        if lock:
            lock.close()


if __name__ == "__main__":
    sys.exit(main())
