"""
evaluation/metrics.py: latencia, precisión y matriz de confusión del traductor de señas.

Uso típico:
    ms = measure_latency(clasificar, ventanas)          # milisegundos por llamada
    reporte = evaluate(reales, predichos, ms)           # reales/predichos: listas de glosas
    print(summary_text(reporte)); save_report(reporte, "evaluation/reporte.json")

Una predicción None (el sistema no reconoció nada) cuenta como error y aparece
como "(ninguna)" en la matriz, para que no se oculten los fallos de reconocimiento.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Iterable, Sequence

import numpy as np

UNKNOWN = "(ninguna)"


def _pair(y_true: Sequence, y_pred: Sequence) -> tuple[list[str], list[str]]:
    t = [UNKNOWN if v is None else str(v) for v in y_true]
    p = [UNKNOWN if v is None else str(v) for v in y_pred]
    if len(t) != len(p):
        raise ValueError("y_true y y_pred deben tener la misma longitud")
    if not t:
        raise ValueError("No hay datos para evaluar")
    return t, p


# ---------- Precisión ----------
def accuracy(y_true: Sequence, y_pred: Sequence) -> float:
    """Exactitud global: fracción de predicciones correctas (0 a 1)."""
    t, p = _pair(y_true, y_pred)
    return sum(a == b for a, b in zip(t, p)) / len(t)


def confusion_matrix(y_true: Sequence, y_pred: Sequence,
                     labels: Iterable[str] | None = None) -> tuple[np.ndarray, list[str]]:
    """
    Matriz con filas = seña real y columnas = seña predicha. Si pasas `labels` fijan el orden;
    cualquier etiqueta vista que falte se agrega al final para no perder datos.
    """
    t, p = _pair(y_true, y_pred)
    seen = sorted(set(t) | set(p))
    given = [str(label) for label in labels] if labels is not None else []
    labs = given + [x for x in seen if x not in set(given)]
    idx = {label: i for i, label in enumerate(labs)}
    cm = np.zeros((len(labs), len(labs)), dtype=int)
    for a, b in zip(t, p):
        cm[idx[a], idx[b]] += 1
    return cm, labs


def per_class(cm: np.ndarray, labels: Sequence[str]) -> dict[str, dict[str, float]]:
    """Precisión, recall, F1 y soporte de cada seña, a partir de la matriz."""
    out = {}
    for i, label in enumerate(labels):
        tp = int(cm[i, i])
        col, row = int(cm[:, i].sum()), int(cm[i, :].sum())
        prec = tp / col if col else 0.0
        rec = tp / row if row else 0.0
        out[label] = {"precision": prec, "recall": rec,
                      "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0, "soporte": row}
    return out


def top_confusions(cm: np.ndarray, labels: Sequence[str], n: int = 5) -> list[tuple[str, str, int]]:
    """Los n errores más frecuentes como (real, predicha, veces)."""
    errs = [(labels[i], labels[j], int(cm[i, j]))
            for i in range(len(labels)) for j in range(len(labels)) if i != j and cm[i, j]]
    return sorted(errs, key=lambda e: -e[2])[:n]


def format_confusion(cm: np.ndarray, labels: Sequence[str]) -> str:
    """Matriz en texto alineado (filas = real, columnas = predicha)."""
    names = [label[:10] for label in labels]
    w = max([len(n) for n in names] + [len(str(int(cm.max()))) if cm.size else 1]) + 1
    lines = [" " * w + "".join(n.rjust(w) for n in names)]
    lines += [names[i].ljust(w) + "".join(str(int(v)).rjust(w) for v in row) for i, row in enumerate(cm)]
    return "\n".join(lines)


# ---------- Latencia ----------
class Timer:
    """with Timer() as t: ...; t.ms  -> milisegundos transcurridos."""

    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.ms = (time.perf_counter() - self._t0) * 1000
        return False


def measure_latency(fn: Callable, inputs: Iterable, warmup: int = 2) -> list[float]:
    """Milisegundos que tarda fn en cada entrada. Las primeras `warmup` llamadas no cuentan
    (cargar el modelo o abrir la conexión distorsionaría el resultado)."""
    items = list(inputs)
    for x in items[:warmup]:
        fn(x)
    out = []
    for x in items:
        with Timer() as t:
            fn(x)
        out.append(t.ms)
    return out


def latency_stats(ms: Sequence[float]) -> dict[str, float]:
    arr = np.asarray(ms, dtype=float)
    if arr.size == 0:
        raise ValueError("No hay mediciones de latencia")
    return {"n": int(arr.size), "media_ms": float(arr.mean()), "p50_ms": float(np.percentile(arr, 50)),
            "p95_ms": float(np.percentile(arr, 95)), "max_ms": float(arr.max())}


# ---------- Reporte ----------
def evaluate(y_true: Sequence, y_pred: Sequence, latencies_ms: Sequence[float] | None = None,
             labels: Iterable[str] | None = None) -> dict:
    cm, labs = confusion_matrix(y_true, y_pred, labels)
    report = {
        "exactitud": accuracy(y_true, y_pred),
        "muestras": len(y_true),
        "etiquetas": labs,
        "matriz": cm.tolist(),
        "por_sena": per_class(cm, labs),
        "errores_frecuentes": [list(e) for e in top_confusions(cm, labs)],
    }
    if latencies_ms is not None and len(latencies_ms):
        report["latencia"] = latency_stats(latencies_ms)
    return report


def summary_text(report: dict) -> str:
    lines = [f"Exactitud: {report['exactitud']:.1%} en {report['muestras']} muestras"]
    if "latencia" in report:
        lat = report["latencia"]
        lines.append(f"Latencia: media {lat['media_ms']:.0f} ms, p50 {lat['p50_ms']:.0f} ms, "
                     f"p95 {lat['p95_ms']:.0f} ms, máx {lat['max_ms']:.0f} ms")
    for real, pred, n in report["errores_frecuentes"]:
        lines.append(f"Error frecuente: {real} se confundió con {pred} ({n} veces)")
    lines.append(format_confusion(np.array(report["matriz"]), report["etiquetas"]))
    return "\n".join(lines)


def save_report(report: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path