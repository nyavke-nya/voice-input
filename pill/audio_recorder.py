"""Захват звука с микрофона + потоковый Silero VAD.

Работает так: sounddevice гонит поток 16кГц моно кадрами по 512 сэмплов
(~32мс). Каждый кадр прогоняется через Silero VAD (onnxruntime, без torch).
SpeechGate — чистый конечный автомат: копит тишину и решает, когда фраза
закончилась. Как только тишина превысила silence_ms после реальной речи —
запись останавливается и накопленное аудио отдаётся наружу.

SpeechGate вынесен как numpy/onnx-free класс, чтобы его логику можно было
тестировать без железа и моделей.
"""
from __future__ import annotations

import threading
import urllib.request
import shutil
from collections import deque
from pathlib import Path
from typing import Callable, Optional

SAMPLE_RATE = 16000
FRAME = 512  # сэмплов на кадр (требование Silero v5 для 16кГц)
FRAME_MS = FRAME / SAMPLE_RATE * 1000  # ~32мс

# Пробуем локальный ассет faster-whisper, иначе качаем один файл модели.
_VAD_URLS = [
    "https://github.com/snakers4/silero-vad/raw/v5.1.2/src/silero_vad/data/silero_vad.onnx",
    "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx",
]
_MIN_VAD_BYTES = 100_000


def resolve_vad_model(override: Optional[str] = None) -> str:
    """Вернуть путь к silero_vad.onnx, скачав при необходимости."""
    if override:
        path = Path(override).expanduser()
        if path.is_file():
            return str(path)
        raise RuntimeError(f"vad_model_path не найден: {path}")
    from .config import cache_dir

    cached = cache_dir() / "silero_vad.onnx"
    if cached.is_file() and cached.stat().st_size >= _MIN_VAD_BYTES:
        return str(cached)

    # faster-whisper иногда несёт единый silero_vad.onnx в ассетах — берём даром.
    try:
        from importlib.resources import files

        asset = files("faster_whisper.assets") / "silero_vad.onnx"
        if asset.is_file():
            return str(asset)
    except (ImportError, ModuleNotFoundError, FileNotFoundError):
        pass

    last_err: Optional[Exception] = None
    partial = cached.with_suffix(".onnx.download")
    for url in _VAD_URLS:
        try:
            with urllib.request.urlopen(url, timeout=30) as source, partial.open("wb") as target:
                shutil.copyfileobj(source, target)
            if partial.stat().st_size < _MIN_VAD_BYTES:
                raise RuntimeError("скачанный файл слишком мал и, вероятно, повреждён")
            partial.replace(cached)
            return str(cached)
        except Exception as e:  # сеть/404 — пробуем следующий
            last_err = e
            try:
                partial.unlink()
            except OSError:
                pass
    raise RuntimeError(
        f"Не удалось получить silero_vad.onnx. Скачайте вручную в {cached} "
        f"или задайте vad_model_path в конфиге. Последняя ошибка: {last_err}"
    )


class SileroVAD:
    """Тонкая обёртка над onnxruntime-сессией Silero VAD v5."""

    def __init__(self, model_path: str, sample_rate: int = SAMPLE_RATE):
        import numpy as np
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        self.sess = ort.InferenceSession(
            model_path, sess_options=opts, providers=["CPUExecutionProvider"]
        )
        self._np = np
        self.sr = sample_rate
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        # имена входов на случай мелких расхождений между версиями модели
        names = {i.name for i in self.sess.get_inputs()}
        self._in = "input" if "input" in names else self.sess.get_inputs()[0].name

    def reset(self) -> None:
        self._state[:] = 0

    def __call__(self, frame) -> float:
        np = self._np
        x = np.asarray(frame, dtype=np.float32).reshape(1, -1)
        out, self._state = self.sess.run(
            None,
            {self._in: x, "state": self._state, "sr": np.array(self.sr, dtype=np.int64)},
        )
        return float(out[0][0])


class SpeechGate:
    """Конечный автомат «конца фразы». Чистый Python — тестируется без железа.

    feed(is_speech) на каждый кадр. should_stop=True, когда после достаточного
    объёма речи набралось >= silence_ms непрерывной тишины. timed_out=True,
    если речь так и не началась за preroll_timeout_ms.
    """

    def __init__(
        self,
        silence_ms: int = 500,
        min_speech_ms: int = 200,
        preroll_timeout_ms: int = 8000,
        frame_ms: float = FRAME_MS,
    ):
        self.silence_frames = max(1, round(silence_ms / frame_ms))
        self.min_speech_frames = max(1, round(min_speech_ms / frame_ms))
        self.preroll_timeout_frames = max(1, round(preroll_timeout_ms / frame_ms))
        self.reset()

    def reset(self) -> None:
        self.speech_frames = 0
        self.silence_run = 0
        self.total_frames = 0
        self.started = False

    def feed(self, is_speech: bool) -> None:
        self.total_frames += 1
        if is_speech:
            self.speech_frames += 1
            self.silence_run = 0
            if self.speech_frames >= self.min_speech_frames:
                self.started = True
        else:
            self.silence_run += 1

    @property
    def should_stop(self) -> bool:
        return self.started and self.silence_run >= self.silence_frames

    @property
    def timed_out(self) -> bool:
        return not self.started and self.total_frames >= self.preroll_timeout_frames


class AudioRecorder:
    """Стрим микрофона -> VAD -> SpeechGate. Всё в собственном потоке.

    on_level(float 0..1) — уровень для визуализации волны (частый вызов).
    on_utterance(np.ndarray float32) — накопленное аудио фразы (в конце).
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._vad: Optional[SileroVAD] = None
        self._vad_lock = threading.Lock()
        self.on_level: Callable[[float], None] = lambda _: None
        self.on_utterance: Callable[[object], None] = lambda _: None
        self.on_error: Callable[[str], None] = lambda _: None
        self.max_seconds = 30  # предохранитель от бесконечной записи

    def _ensure_vad(self) -> SileroVAD:
        with self._vad_lock:
            if self._vad is None:
                path = resolve_vad_model(self.cfg.get("vad_model_path"))
                self._vad = SileroVAD(path)
            self._vad.reset()
            return self._vad

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout: float = 1.0) -> None:
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=timeout)

    def _run(self) -> None:
        import queue

        import numpy as np
        import sounddevice as sd

        try:
            vad = self._ensure_vad()
        except Exception as e:
            self.on_error(str(e))
            return

        threshold = float(self.cfg.get("vad_sensitivity", 0.5))
        gate = SpeechGate(silence_ms=int(self.cfg.get("silence_ms", 500)))
        frames_q: "queue.Queue" = queue.Queue()

        def cb(indata, _frames, _time, status):  # PortAudio-поток
            if status:
                print(f"[pill] предупреждение аудиопотока: {status}")
            frames_q.put(indata[:, 0].copy())

        collected: list = []
        preroll = deque(maxlen=max(1, round(320 / FRAME_MS)))
        max_frames = int(self.max_seconds * SAMPLE_RATE / FRAME)
        def _open(dev):
            return sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                                  blocksize=FRAME, device=dev, callback=cb)

        try:
            dev = self.cfg.get("input_device")
            try:
                stream = _open(dev)
            except Exception:  # выбранное устройство не держит 16кГц/недоступно
                if dev is None:
                    raise
                print("[pill] микрофон не подходит, беру устройство по умолчанию")
                stream = _open(None)
            with stream:
                n = 0
                while not self._stop.is_set():
                    try:
                        frame = frames_q.get(timeout=0.5)
                    except queue.Empty:
                        continue
                    if len(frame) < FRAME:
                        frame = np.pad(frame, (0, FRAME - len(frame)))
                    elif len(frame) > FRAME:
                        frame = frame[:FRAME]
                    was_started = gate.started
                    if not was_started:
                        preroll.append(frame)
                    prob = vad(frame)
                    gate.feed(prob >= threshold)
                    if gate.started and not was_started:
                        collected.extend(preroll)
                        preroll.clear()
                    elif was_started:
                        collected.append(frame)
                    # уровень: RMS с лёгким поджатием, чтобы волна была живой
                    rms = float(np.sqrt(np.mean(frame ** 2)))
                    self.on_level(min(1.0, rms * 8.0))
                    n += 1
                    if gate.should_stop or gate.timed_out or n >= max_frames:
                        break
        except Exception as e:
            self.on_error(str(e))
            return

        self.on_level(0.0)
        if gate.started and collected:
            self.on_utterance(np.concatenate(collected))
        else:
            self.on_utterance(None)  # тишина/таймаут — фразы нет


if __name__ == "__main__":
    # self-check: гейт срабатывает ровно после min_speech + silence, и таймаутит тишину
    g = SpeechGate(silence_ms=500, min_speech_ms=200, frame_ms=32)
    for _ in range(10):  # ~320мс речи -> started
        g.feed(True)
    assert g.started and not g.should_stop
    fired = None
    for i in range(100):
        g.feed(False)
        if g.should_stop:
            fired = i + 1
            break
    assert fired == round(500 / 32), fired  # ~16 кадров тишины
    g2 = SpeechGate(preroll_timeout_ms=320, frame_ms=32)
    for _ in range(10):
        g2.feed(False)
    assert g2.timed_out and not g2.should_stop
    print("audio_recorder gate OK")
