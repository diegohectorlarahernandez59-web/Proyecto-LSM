import threading
import time
import importlib
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Sequence, List
from pathlib import Path

try:
    cv2 = importlib.import_module("cv2")
except ImportError:
    cv2 = None


if TYPE_CHECKING:
    # Importa solo para evitar ciclos de dependencia si no se usa en tiempo de ejecución
    from .glossary import GlossaryManager


@dataclass(frozen=True)
class TimedFrame:
    """Datos para almacenar un fotograma con su marca de tiempo."""
    frame: Any  # El fotograma (ej. un array NumPy BGR)
    t: float  # Tiempo en segundos, reloj monotónico

class FrameBuffer:
    """Cola circular segura entre hilos para almacenar fotogramas de video."""

    def __init__(self, max_seconds: float = 2.0, fps: int = 30):
        """
        Inicializa el búfer.
        max_seconds: Tiempo que se quiere almacenar en la cola.
        fps: Tasa de fotogramas esperada (para cálculos de duración).
        """
        if max_seconds <= 0 or fps <= 0:
            raise ValueError("max_seconds y fps deben ser positivos")

        # El tamaño máximo de la cola es basado en el tiempo y FPS
        max_capacity = max(1, int(max_seconds * fps))
        self._frames: deque[TimedFrame] = deque(maxlen=max_capacity)
        self._lock = threading.Lock()
        self.max_seconds = max_seconds
        self.fps = fps

    # ---------- Escritura (hilo de captura) ----------
    def push(self, frame: Any, t: float | None = None) -> None:
        """Agrega un nuevo fotograma al buffer."""
        if t is None:
            t = time.monotonic()

        item = TimedFrame(frame, t)
        with self._lock:
            self._frames.append(item)


    def clear(self) -> None:
        """Vacía completamente el buffer."""
        with self._lock:
            self._frames.clear()


    # ---------- Lectura (hilo de procesamiento) ----------
    def window_timed(self, seconds: float | None = 1.5, every: int = 1,
                      max_frames: int | None = None) -> List[TimedFrame]:
        """
        Obtiene los fotogramas dentro de un rango de tiempo.
        """
        if every < 1 or (max_frames is not None and max_frames < 1):
            raise ValueError("every y max_frames deben ser al menos 1")

        with self._lock:
            items = list(self._frames)
            if not items:
                return []

            if seconds is not None:
                cutoff = items[-1].t - seconds
                items = [f for f in items if f.t >= cutoff]

            if every > 1:
                # Recorte y retorno en orden cronológico inverso, luego se revierte
                items = items[::-1][::every][::-1]

            if max_frames is not None and len(items) > max_frames:
                # Lógica para repartir los fotogramas de forma pareja
                if max_frames == 1:
                    indices = [len(items) - 1]
                else:
                    # Distribución de índices para seleccionar max_frames puntos
                    indices = [
                        round(i * (len(items) - 1) / (max_frames - 1))
                        for i in range(max_frames)
                    ]
                items = [items[i] for i in indices]

            return items


    def window(self, seconds: float | None = 1.5, every: int = 1,
               max_frames: int | None = None) -> List[Any]:
        """Método conveniente para obtener solo los fotogramas (sin la marca de tiempo)."""
        return [f.frame for f in self.window_timed(seconds, every, max_frames)]


    def duration(self) -> float:
        """Calcula la duración de los fotogramas almacenados."""
        with self._lock:
            if len(self._frames) > 1:
                return self._frames[-1].t - self._frames[0].t
            return 0.0

    def age(self) -> float:
        """Tiempo transcurrido desde el último push."""
        with self._lock:
            if not self._frames:
                return float("inf")
            return time.monotonic() - self._frames[-1].t


    def __len__(self) -> int:
        """Retorna la cantidad actual de fotogramas en el buffer."""
        with self._lock:
            return len(self._frames)


    # ---------- Puentes de Guardado (Integración clave) ----------

    def save_to_glossary(self, glossary: "GlossaryManager", word: str, seconds: float = 2.0,
                          *, letter: bool = False, overwrite: bool = False) -> Path:
        """Guarda los últimos segundos como clip en el disco."""
        items = self.window_timed(seconds)

        if len(items) < 2:
            raise ValueError("Muy pocos fotogramas: espera a que la cámara llene el buffer")

        path = glossary.clip_path_for(word, letter=letter)
        if path.exists() and not overwrite:
            raise FileExistsError(f"Ya existe {path.name}; usa overwrite=True para reemplazarlo")

        # Cálculo de FPS basado en la cantidad de frames y el tiempo transcurrido
        span = items[-1].t - items[0].t
        if span <= 0:
             # Si el tiempo es cero, usar un FPS estándar para evitar división por cero.
            fps = 15.0
        else:
            # Asegura que el FPS esté dentro de un rango razonable (1.0 a 60.0)
            fps = min(60.0, max(1.0, (len(items) - 1) / span))


        # Escribir el clip de video
        self.save_clip([i.frame for i in items], path, fps)

        # Forzar la recarga del glosario para que detecte el nuevo archivo
        glossary.reload()
        return path


    # ---------- Funciones de Codificación/Guardado OpenCV ----------

    def encode_jpeg(self, frames: Sequence[Any], quality: int = 80, max_width: int | None = 640) -> List[bytes]:
        """Codifica fotogramas como JPEG."""
        if cv2 is None:
            raise RuntimeError("La codificación de imágenes requiere OpenCV; instala opencv-python")
        out = []
        for fr in frames:
            h, w = fr.shape[:2]
            if max_width and w > max_width:
                # Redimensionar si es necesario para reducir carga de envío a Gemini
                fr = cv2.resize(fr, (max_width, round(h * max_width / w)))

            ok, buf = cv2.imencode(".jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, quality])
            if not ok:
                raise ValueError("No se pudo codificar un fotograma")
            out.append(buf.tobytes())
        return out


    def save_clip(self, frames: Sequence[Any], path: str | Path, fps: float) -> Path:
        """Escribe los fotogramas como .mp4."""
        if cv2 is None:
            raise RuntimeError("La escritura de video requiere OpenCV; instala opencv-python")
        if not frames:
            raise ValueError("No hay fotogramas para guardar")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Usamos un nombre temporal ASCII para compatibilidad con OpenCV/Windows
        tmp = path.parent / ".tmp_clip.mp4"

        try:
            writer = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), fps, (frames[0].shape[1], frames[0].shape[0]))
            if not writer.isOpened():
                raise RuntimeError("OpenCV no pudo abrir el escritor de video (¿falta el códec mp4v?)")

            for fr in frames:
                # Asegurarse de que todos los frames tengan las mismas dimensiones para el escritor MP4
                if fr.shape[:2] != (frames[0].shape[0], frames[0].shape[1]):
                    fr = cv2.resize(fr, (frames[0].shape[1], frames[0].shape[0]))
                writer.write(fr)

            writer.release()
            
            # Reemplazar el archivo temporal por el destino final
            import os
            os.replace(tmp, path)
            return path

        except Exception as e:
            print(f"Error al escribir el clip en {path}: {e}")
            raise RuntimeError(f"Fallo en la escritura de video: {e}")

