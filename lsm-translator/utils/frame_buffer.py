"""
utils/frame_buffer.py: memoria circular de los últimos fotogramas de la cámara.

Quién lo usa:
  camera.py        -> push(frame) sin parar (hilo de captura)
  sign_to_text.py  -> next_window(30..60) para clasificar, o window(...) + encode_jpeg(...) para Gemini
  glosario visual  -> save_to_glossary(...) guarda esa ventana como clip nuevo en assets/signs/

Una seña dura de 1 a 2 s: a 30 fps son entre 30 y 60 fotogramas, el tamaño de ventana por defecto.

Los fotogramas pueden ser cualquier objeto; solo encode_jpeg y save_clip
necesitan arreglos de NumPy/OpenCV (BGR, como los entrega cv2.VideoCapture).
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

if TYPE_CHECKING:
    from .glossary import GlossaryManager


@dataclass(frozen=True)
class TimedFrame:
    frame: Any
    t: float  # segundos, reloj monotónico


WINDOW_MIN = 30   # ventana mínima (≈1 s a 30 fps)
WINDOW_MAX = 60   # ventana máxima y capacidad por defecto (≈2 s a 30 fps)


class FrameBuffer:
    """Cola circular segura entre hilos: al llenarse descarta los fotogramas más viejos."""

    def __init__(self, max_seconds: float = 2.0, fps: int = 30, *, capacity: int | None = None):
        """La capacidad sale de max_seconds * fps (60 por defecto) o se fija con capacity."""
        if max_seconds <= 0 or fps <= 0 or (capacity is not None and capacity < 1):
            raise ValueError("max_seconds, fps y capacity deben ser positivos")
        self.max_seconds = max_seconds
        self.capacity = capacity or max(1, int(max_seconds * fps))
        self._frames: deque[TimedFrame] = deque(maxlen=self.capacity)
        self._lock = threading.Lock()
        self._pushed = 0    # total de fotogramas recibidos
        self._emitted = 0   # valor de _pushed en la última ventana entregada

    # ---------- Escritura (hilo de captura) ----------
    def push(self, frame: Any, t: float | None = None) -> None:
        item = TimedFrame(frame, time.monotonic() if t is None else t)
        with self._lock:
            self._frames.append(item)
            self._pushed += 1

    def clear(self) -> None:
        with self._lock:
            self._frames.clear()
            self._pushed = self._emitted = 0

    # ---------- Lectura (hilo de procesamiento) ----------
    def window_timed(self, seconds: float | None = 1.5, every: int = 1,
                     max_frames: int | None = None) -> list[TimedFrame]:
        """
        Fotogramas de los últimos `seconds` (medidos desde el más reciente).
        every=3 entrega uno de cada tres, siempre incluyendo el más reciente.
        max_frames limita la cantidad repartiendo los fotogramas de forma pareja
        (útil para controlar cuántas imágenes se envían a Gemini).
        """
        if every < 1 or (max_frames is not None and max_frames < 1):
            raise ValueError("every y max_frames deben ser al menos 1")
        with self._lock:
            items = list(self._frames)
        if items and seconds is not None:
            cutoff = items[-1].t - seconds
            items = [f for f in items if f.t >= cutoff]
        if every > 1:
            items = items[::-1][::every][::-1]
        n = len(items)
        if max_frames is not None and n > max_frames:
            idx = [n - 1] if max_frames == 1 else [
                round(i * (n - 1) / (max_frames - 1)) for i in range(max_frames)
            ]
            items = [items[i] for i in idx]
        return items

    def window(self, seconds: float | None = 1.5, every: int = 1,
               max_frames: int | None = None) -> list[Any]:
        return [f.frame for f in self.window_timed(seconds, every, max_frames)]

    def last(self, n: int = WINDOW_MIN) -> list[Any]:
        """Los últimos n fotogramas, o [] si todavía no hay tantos."""
        if n < 1:
            raise ValueError("n debe ser al menos 1")
        with self._lock:
            return [f.frame for f in list(self._frames)[-n:]] if len(self._frames) >= n else []

    def next_window(self, size: int = WINDOW_MIN, hop: int = 10) -> list[Any] | None:
        """
        Ventana deslizante para clasificar en continuo: entrega los últimos `size`
        fotogramas solo cuando llegaron `hop` nuevos desde la última entrega; si no, None.
        Con size=30 y hop=10 se clasifica unas 3 veces por segundo a 30 fps.
        """
        if not 1 <= size <= self.capacity:
            raise ValueError(f"size debe estar entre 1 y la capacidad ({self.capacity})")
        if hop < 1:
            raise ValueError("hop debe ser al menos 1")
        with self._lock:
            if len(self._frames) < size or self._pushed - self._emitted < hop:
                return None
            self._emitted = self._pushed
            return [f.frame for f in list(self._frames)[-size:]]

    def duration(self) -> float:
        """Segundos de video que hay guardados ahora."""
        with self._lock:
            return self._frames[-1].t - self._frames[0].t if len(self._frames) > 1 else 0.0

    def ready(self, min_seconds: float = 1.0) -> bool:
        return self.duration() >= min_seconds

    def age(self) -> float:
        """Segundos desde el último push (con reloj por defecto). Sirve para detectar cámara detenida."""
        with self._lock:
            return time.monotonic() - self._frames[-1].t if self._frames else float("inf")

    def __len__(self) -> int:
        with self._lock:
            return len(self._frames)

    # ---------- Puente con assets/signs ----------
    def save_to_glossary(self, glossary: "GlossaryManager", word: str, seconds: float = 2.0,
                         *, letter: bool = False, overwrite: bool = False) -> Path:
        """
        Guarda los últimos `seconds` como clip de la seña `word` y recarga el glosario,
        así glossary.get_sign_path(word) ya lo encuentra. Con letter=True va a alfabeto/.
        """
        items = self.window_timed(seconds)
        if len(items) < 2:
            raise ValueError("Muy pocos fotogramas: espera a que la cámara llene el buffer")
        path = (glossary.fingerspeller.clip_path_for(word) if letter
                else glossary.clip_path_for(word))
        if path.exists() and not overwrite:
            raise FileExistsError(f"Ya existe {path.name}; usa overwrite=True para reemplazarlo")
        span = items[-1].t - items[0].t
        fps = min(60.0, max(1.0, (len(items) - 1) / span)) if span > 0 else 15.0
        save_clip([i.frame for i in items], path, fps)
        glossary.reload()
        return path


def encode_jpeg(frames: Sequence[Any], quality: int = 80, max_width: int | None = 640) -> list[bytes]:
    """Codifica fotogramas como JPEG (más ligeros para enviar a Gemini)."""
    import cv2

    out = []
    for fr in frames:
        h, w = fr.shape[:2]
        if max_width and w > max_width:
            fr = cv2.resize(fr, (max_width, round(h * max_width / w)))
        ok, buf = cv2.imencode(".jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise ValueError("No se pudo codificar un fotograma")
        out.append(buf.tobytes())
    return out


def save_clip(frames: Sequence[Any], path: str | Path, fps: float) -> Path:
    """Escribe los fotogramas como .mp4. Usa un archivo temporal con nombre ASCII
    para que nombres como "ñ.mp4" no fallen en el escritor de OpenCV (sobre todo en Windows)."""
    import cv2

    if not frames:
        raise ValueError("No hay fotogramas para guardar")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / ".tmp_clip.mp4"  # los archivos que empiezan con "." los ignora el glosario
    h, w = frames[0].shape[:2]
    writer = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not writer.isOpened():
        raise RuntimeError("OpenCV no pudo abrir el escritor de video (¿falta el códec mp4v?)")
    try:
        for fr in frames:
            if fr.shape[:2] != (h, w):
                fr = cv2.resize(fr, (w, h))
            writer.write(fr)
    finally:
        writer.release()
    os.replace(tmp, path)
    return path