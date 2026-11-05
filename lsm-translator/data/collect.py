"""
data/collect.py: graba muestras etiquetadas de cada seña para entrenar el clasificador.

Uso (desde la raíz del proyecto):
    python -m data.collect HOLA --muestras 30        graba hasta tener 30 muestras de HOLA
    python -m data.collect --resumen                 cuenta las muestras de cada seña

Teclas: ESPACIO graba una muestra, Z borra la última, Q termina.

Cada muestra es data/raw/HOLA/0.npy, HOLA/1.npy... con forma (frames, 126): por cada
fotograma, 2 manos x 21 puntos x (x, y, z) de MediaPipe. Mano izquierda primero; ceros si
no se ve. Todas las muestras se remuestrean a la misma cantidad de fotogramas (30 por defecto,
el tamaño mínimo de ventana de utils/frame_buffer.py) para poder entrenar con ellas.
La carpeta usa el mismo nombre normalizado que utils/glossary.py (BUENOS_DIAS, ESPAÑOL).
"""
from __future__ import annotations

import argparse
import time
import unicodedata
from pathlib import Path

import numpy as np

from utils.glossary import normalize_text

RAW_DIR = Path(__file__).resolve().parent / "raw"
POINTS, HANDS = 21, 2
HAND_FEATURES = POINTS * 3
FEATURES = HANDS * HAND_FEATURES   # 126
WINDOW = 30                        # fotogramas por muestra


# ---------- Lógica pura (no necesita cámara) ----------
def folder_name(glosa: str) -> str:
    """"Buenos días" -> "BUENOS_DIAS": misma normalización que el glosario."""
    key = normalize_text(glosa)
    if not key:
        raise ValueError("La glosa no tiene texto utilizable")
    return key.upper().replace(" ", "_")


def hands_vector(results) -> np.ndarray:
    """Vector de 126 valores a partir de un resultado de mp.solutions.hands (ceros si no hay manos)."""
    vec = np.zeros(FEATURES, dtype=np.float32)
    if results.multi_hand_landmarks:
        for lm, hd in zip(results.multi_hand_landmarks, results.multi_handedness):
            slot = 0 if hd.classification[0].label == "Left" else 1
            pts = np.array([[p.x, p.y, p.z] for p in lm.landmark], dtype=np.float32).ravel()
            vec[slot * HAND_FEATURES:(slot + 1) * HAND_FEATURES] = pts
    return vec


def resample(seq, n: int = WINDOW) -> np.ndarray:
    """Lleva una secuencia (T, D) a exactamente n fotogramas tomando los más cercanos en el tiempo."""
    seq = np.asarray(seq, dtype=np.float32)
    if len(seq) == 0:
        raise ValueError("La secuencia está vacía")
    return seq[np.round(np.linspace(0, len(seq) - 1, n)).astype(int)]


def hand_ratio(seq) -> float:
    """Fracción de fotogramas en los que se vio al menos una mano."""
    return float(np.mean(np.any(np.asarray(seq) != 0, axis=1)))


def next_index(folder: Path) -> int:
    nums = [int(p.stem) for p in folder.glob("*.npy") if p.stem.isdigit()]
    return max(nums) + 1 if nums else 0


def save_sample(glosa: str, seq, root: Path = RAW_DIR) -> Path:
    folder = Path(root) / folder_name(glosa)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{next_index(folder)}.npy"
    np.save(path, np.asarray(seq, dtype=np.float32))
    return path


def delete_last(glosa: str, root: Path = RAW_DIR) -> Path | None:
    folder = Path(root) / folder_name(glosa)
    nums = sorted(int(p.stem) for p in folder.glob("*.npy") if p.stem.isdigit())
    if not nums:
        return None
    path = folder / f"{nums[-1]}.npy"
    path.unlink()
    return path


def count_samples(root: Path = RAW_DIR) -> dict[str, int]:
    root = Path(root)
    if not root.is_dir():
        return {}
    return {d.name: len(list(d.glob("*.npy"))) for d in sorted(root.iterdir()) if d.is_dir()}


# ---------- Captura con cámara ----------
def run_capture(glosa: str, muestras: int, frames: int, segundos: float, camara: int, min_manos: float):
    import cv2
    import mediapipe as mp

    folder = RAW_DIR / folder_name(glosa)
    total = len(list(folder.glob("*.npy")))
    etiqueta = unicodedata.normalize("NFKD", glosa).encode("ascii", "ignore").decode().upper()  # cv2 solo dibuja ASCII
    hands = mp.solutions.hands.Hands(max_num_hands=2, min_detection_confidence=0.6,
                                     min_tracking_confidence=0.5)
    cap = cv2.VideoCapture(camara)
    if not cap.isOpened():
        raise SystemExit("No se pudo abrir la cámara")
    grabando, t0, buf, msg = False, 0.0, [], "ESPACIO = grabar"
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)  # vista espejo: así MediaPipe etiqueta bien izquierda/derecha
            res = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            for lm in res.multi_hand_landmarks or []:
                mp.solutions.drawing_utils.draw_landmarks(frame, lm, mp.solutions.hands.HAND_CONNECTIONS)
            if grabando:
                buf.append(hands_vector(res))
                if time.monotonic() - t0 >= segundos:
                    grabando = False
                    if len(buf) < 2 or hand_ratio(buf) < min_manos:
                        msg = "Descartada: casi no se vieron las manos"
                    else:
                        save_sample(glosa, resample(buf, frames))
                        total += 1
                        msg = f"Guardada ({total})"
                    buf = []
            color = (0, 0, 255) if grabando else (0, 200, 0)
            cv2.putText(frame, f"{etiqueta}  muestras: {total}" + (f"/{muestras}" if muestras else ""),
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            cv2.putText(frame, "GRABANDO..." if grabando else msg, (10, 65),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.imshow("collect", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or (muestras and total >= muestras):
                break
            if key == 32 and not grabando:
                grabando, buf, t0, msg = True, [], time.monotonic(), ""
            elif key == ord("z") and not grabando and delete_last(glosa):
                total -= 1
                msg = f"Borrada la última ({total})"
    finally:
        cap.release()
        hands.close()
        cv2.destroyAllWindows()
    print(f"{folder_name(glosa)}: {total} muestras en {folder}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Graba muestras etiquetadas de una seña.")
    ap.add_argument("glosa", nargs="?", help='glosa a grabar, por ejemplo HOLA o "BUENOS DIAS"')
    ap.add_argument("--muestras", type=int, default=30, help="total deseado en la carpeta (0 = sin límite)")
    ap.add_argument("--frames", type=int, default=WINDOW, help="fotogramas por muestra (30 a 60)")
    ap.add_argument("--segundos", type=float, default=2.0, help="duración de cada grabación")
    ap.add_argument("--camara", type=int, default=0)
    ap.add_argument("--min-manos", type=float, default=0.6,
                    help="fracción mínima de fotogramas con manos para aceptar la muestra")
    ap.add_argument("--resumen", action="store_true", help="solo contar las muestras existentes")
    args = ap.parse_args(argv)
    if args.resumen:
        conteo = count_samples()
        for nombre, n in conteo.items():
            print(f"{nombre:20} {n}")
        print(f"{len(conteo)} señas, {sum(conteo.values())} muestras")
    elif args.glosa:
        run_capture(args.glosa, args.muestras, args.frames, args.segundos, args.camara, args.min_manos)
    else:
        ap.error("indica una glosa o usa --resumen")


if __name__ == "__main__":
    main()