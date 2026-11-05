"""
utils/glossary.py: mapeo glosa -> clip de seña, con categoría y estado de validación.

Fuentes (se combinan):
  assets/glossaries/*.json  catálogo de glosas: archivo, categoría, estado, alias.
  assets/signs/             los clips. Cualquier video/imagen cuyo nombre sea una glosa
                            (hola.mp4, buenos_dias.mp4) cuenta aunque no esté en un JSON.
El alfabeto (alfabeto/a.png, letra_b.png) lo maneja utils/fingerspelling.py.

Formato de un JSON:
  {"nombre": "escolar",
   "senas": [{"glosa": "HOLA", "archivo": "hola.mp4", "categoria": "saludos",
              "estado": "pendiente", "alias": ["opcional"]}]}

estado: "validada" (la revisó una persona sorda o un intérprete), "pendiente" o "rechazada".
Las glosas de carpeta sin JSON quedan como "sin_registro".
"""
from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Iterator

if TYPE_CHECKING:
    from .fingerspelling import Fingerspeller

log = logging.getLogger(__name__)

# utils/glossary.py -> raíz del proyecto -> assets/ (no depende de dónde se ejecute)
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
DEFAULT_SIGNS_DIR = ASSETS_DIR / "signs"
DEFAULT_GLOSSARIES_DIR = ASSETS_DIR / "glossaries"

# Número menor = mayor prioridad cuando dos archivos comparten nombre.
EXT_PRIORITY = {
    ".mp4": 0, ".webm": 0, ".mov": 1, ".avi": 2,
    ".gif": 3, ".png": 4, ".jpg": 5, ".jpeg": 5, ".webp": 5,
}
ALPHABET_DIRS = {"alfabeto", "abecedario", "letras", "dactilologia"}
LETTER_PREFIX = "letra "

VALIDADA, PENDIENTE, RECHAZADA, SIN_REGISTRO = "validada", "pendiente", "rechazada", "sin_registro"
ESTADOS = (VALIDADA, PENDIENTE, RECHAZADA)

_ENE = "\ue000"  # protege la ñ mientras se quitan los acentos
_NON_WORD = re.compile(r"[^a-z0-9ñ\s]")


@lru_cache(maxsize=8192)
def normalize_text(text: str) -> str:
    """
    Minúsculas, sin acentos ni signos, espacios colapsados. Conserva la ñ
    (no es lo mismo "año" que "ano").  "¡Hola, Cómo estás! " -> "hola como estas"
    """
    text = unicodedata.normalize("NFC", text).lower().replace("ñ", _ENE)
    text = "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )
    text = _NON_WORD.sub(" ", text.replace(_ENE, "ñ"))
    return " ".join(text.split())


def _variants(phrase: str):
    """La frase tal cual y luego su último término en singular (plural español simple)."""
    yield phrase
    head, _, last = phrase.rpartition(" ")
    head = head + " " if head else ""
    if len(last) > 3:  # evita falsos positivos como "mes" -> "me"
        if last.endswith("ces"):
            yield head + last[:-3] + "z"      # luces -> luz
        if last.endswith("es"):
            yield head + last[:-2]            # papeles -> papel
        if last.endswith("s"):
            yield head + last[:-1]            # dias -> dia


# ---------- Piezas compartidas con fingerspelling.py ----------
def iter_clips(signs_dir: Path) -> Iterator[tuple[Path, Path]]:
    """(ruta, ruta relativa) de cada clip válido, en orden estable; ignora ocultos."""
    for path in sorted(signs_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in EXT_PRIORITY:
            continue
        rel = path.relative_to(signs_dir)
        if not any(part.startswith(".") for part in rel.parts):
            yield path, rel


def is_alphabet_file(rel: Path) -> bool:
    """True si el clip es del alfabeto: está en alfabeto/ (o similar) o se llama letra_x."""
    in_dir = any(normalize_text(p) in ALPHABET_DIRS for p in rel.parts[:-1])
    return in_dir or normalize_text(rel.stem).startswith(LETTER_PREFIX)


def register_clip(target: dict, key: str, path: Path) -> None:
    """Guarda (prioridad, ruta) en target[key]; ante duplicados gana el de mejor extensión."""
    prio = EXT_PRIORITY[path.suffix.lower()]
    prev = target.get(key)
    if prev is None or prio < prev[0]:
        if prev:
            log.warning("Duplicado %r: se usa %s en lugar de %s", key, path.name, Path(prev[1]).name)
        target[key] = (prio, str(path.resolve()))
    else:
        log.warning("Duplicado %r: se ignora %s", key, path)


@dataclass(frozen=True)
class SignEntry:
    glosa: str
    path: str | None                       # None = declarada pero aún sin clip
    categoria: str | None = None
    estado: str = SIN_REGISTRO
    fuente: str = "carpeta"                # ruta del JSON de origen, o "carpeta"
    validado_por: str | None = None


@dataclass(frozen=True)
class SignItem:
    text: str                              # palabra, frase o letra solicitada
    kind: str                              # "sign" | "letter" | "missing"
    path: str | None = None                # ruta absoluta del clip, None si kind == "missing"
    categoria: str | None = None
    estado: str | None = None              # estado de validación (solo para kind == "sign")


@dataclass(frozen=True)
class _Snapshot:
    entries: dict
    max_phrase: int


class GlossaryManager:
    def __init__(self, signs_dir: str | Path | None = None, glossaries_dir: str | Path | None = None,
                 *, require_validated: bool = False, create_if_missing: bool = True,
                 fingerspeller: "Fingerspeller | None" = None):
        """
        require_validated=True: solo se usan señas con estado "validada"; las demás se
        deletrean. Conviene activarlo cuando ya haya clips revisados por una persona sorda.
        """
        self.signs_dir = Path(signs_dir) if signs_dir else DEFAULT_SIGNS_DIR
        self.glossaries_dir = Path(glossaries_dir) if glossaries_dir else DEFAULT_GLOSSARIES_DIR
        self.require_validated = require_validated
        self.create_if_missing = create_if_missing
        if fingerspeller is None:
            # Import tardío: fingerspelling.py importa este módulo.
            from .fingerspelling import Fingerspeller
            fingerspeller = Fingerspeller(self.signs_dir)
        self.fingerspeller = fingerspeller
        self._state = _Snapshot({}, 1)
        self.reload()

    # ---------- Carga ----------
    def reload(self) -> int:
        """
        Reescanea clips y catálogos. Arma un glosario nuevo y lo intercambia de una vez,
        así otros hilos nunca ven uno a medias. Devuelve cuántas glosas tienen clip.
        """
        files: dict = {}
        if self.signs_dir.is_dir():
            for path, rel in iter_clips(self.signs_dir):
                if is_alphabet_file(rel):
                    continue
                key = normalize_text(path.stem)
                if key:
                    register_clip(files, key, path)
                else:
                    log.warning("Nombre de archivo sin texto utilizable: %s", path)
        else:
            log.warning("La ruta de señas %s no existe.", self.signs_dir)
            if self.create_if_missing:
                self.signs_dir.mkdir(parents=True, exist_ok=True)
        files = {k: v[1] for k, v in files.items()}

        entries: dict[str, SignEntry] = {}
        aliases: list[tuple[str, str]] = []
        json_files = sorted(self.glossaries_dir.glob("*.json")) if self.glossaries_dir.is_dir() else []
        for jf in json_files:
            for item in self._read_catalog(jf):
                key = normalize_text(str(item.get("glosa", "")))
                if not key:
                    log.warning("Entrada sin glosa en %s", jf.name)
                    continue
                if key in entries:
                    log.warning("Glosa duplicada %r en %s: se ignora", key, jf.name)
                    continue
                estado = item.get("estado", PENDIENTE)
                if estado not in ESTADOS:
                    log.warning("Estado inválido %r para %r: queda como pendiente", estado, key)
                    estado = PENDIENTE
                path = None
                if item.get("archivo"):
                    declared = self.signs_dir / str(item["archivo"])
                    path = str(declared.resolve()) if declared.is_file() else None
                entries[key] = SignEntry(
                    glosa=str(item["glosa"]).strip(), path=path or files.get(key),
                    categoria=item.get("categoria"), estado=estado,
                    fuente=str(jf), validado_por=item.get("validado_por"))
                alias = item.get("alias", [])
                aliases += [(normalize_text(a), key) for a in ([alias] if isinstance(alias, str) else alias)]

        for key, path in files.items():          # clips sin catálogo
            entries.setdefault(key, SignEntry(glosa=key, path=path))
        for alt, key in aliases:
            if alt and alt not in entries:
                entries[alt] = entries[key]
            elif alt:
                log.warning("Alias %r ignorado: ya existe como glosa", alt)

        self._state = _Snapshot(entries, max((k.count(" ") + 1 for k in entries), default=1))
        self.fingerspeller.reload()
        con_clip = sum(1 for k, e in entries.items() if e.path and k == normalize_text(e.glosa))
        log.info("Glosario: %d glosas con clip, %d sin clip. Letras: %d",
                 con_clip, len(self.missing_clips()), len(self.fingerspeller))
        return con_clip

    @staticmethod
    def _read_catalog(path: Path) -> list[dict]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log.warning("No se pudo leer %s: %s", path, e)
            return []
        items = data if isinstance(data, list) else data.get("senas", []) if isinstance(data, dict) else []
        return [i for i in items if isinstance(i, dict)]

    # ---------- Consulta ----------
    def _usable(self, entry: SignEntry | None) -> bool:
        return bool(entry and entry.path and (not self.require_validated or entry.estado == VALIDADA))

    def _lookup(self, snap: _Snapshot, phrase: str) -> SignEntry | None:
        """Primera entrada utilizable para la frase o su singular."""
        if phrase:
            for cand in _variants(phrase):
                entry = snap.entries.get(cand)
                if self._usable(entry):
                    return entry
        return None

    def get_entry(self, word: str) -> SignEntry | None:
        """La entrada tal como está en el catálogo, tenga clip o no, esté validada o no."""
        phrase = normalize_text(word)
        for cand in _variants(phrase) if phrase else ():
            entry = self._state.entries.get(cand)
            if entry:
                return entry
        return None

    def get_sign_path(self, word: str) -> str | None:
        """Ruta absoluta del clip, o None si no hay clip utilizable (activar deletreo)."""
        entry = self._lookup(self._state, normalize_text(word))
        return entry.path if entry else None

    def resolve(self, text: str | Iterable[str], spell_missing: bool = True) -> list[SignItem]:
        """
        Convierte un texto (o la glosa que devuelve Gemini) en la lista ordenada de clips.
        Busca primero la frase más larga que exista ("buenos dias" antes que "buenos" + "dias").
        Lo que no tiene clip utilizable se deletrea con fingerspelling.py.
        """
        snap = self._state
        if not isinstance(text, str):
            text = " ".join(text)
        tokens = normalize_text(text).split()
        items: list[SignItem] = []
        i = 0
        while i < len(tokens):
            for n in range(min(snap.max_phrase, len(tokens) - i), 0, -1):
                phrase = " ".join(tokens[i:i + n])
                entry = self._lookup(snap, phrase)
                if entry:
                    items.append(SignItem(phrase, "sign", entry.path, entry.categoria, entry.estado))
                    i += n
                    break
            else:
                items.extend(self.fingerspeller.spell(tokens[i]) if spell_missing
                             else [SignItem(tokens[i], "missing")])
                i += 1
        return items

    # ---------- Catálogo y validación ----------
    def _unique(self) -> list[SignEntry]:
        return list({normalize_text(e.glosa): e for e in self._state.entries.values()}.values())

    def missing_clips(self) -> list[SignEntry]:
        """Glosas del catálogo que aún no tienen clip: la lista de pendientes por grabar."""
        return [e for e in self._unique() if e.path is None]

    def categories(self) -> list[str]:
        return sorted({e.categoria for e in self._unique() if e.categoria})

    def by_category(self, categoria: str) -> list[SignEntry]:
        return [e for e in self._unique() if e.categoria == categoria]

    def validation_report(self) -> dict[str, int]:
        """Cuántas glosas hay por estado: {"validada": 3, "pendiente": 50, ...}."""
        report: dict[str, int] = {}
        for e in self._unique():
            report[e.estado] = report.get(e.estado, 0) + 1
        return report

    def set_validation(self, glosa: str, estado: str, por: str | None = None) -> None:
        """
        Cambia el estado de una glosa en su JSON y recarga. Para "validada" hay que
        indicar quién la revisó (queda registrado con la fecha).
        """
        if estado not in ESTADOS:
            raise ValueError(f"Estado inválido: {estado!r}. Usa uno de {ESTADOS}")
        if estado == VALIDADA and not (por and por.strip()):
            raise ValueError("Para marcar una seña como validada indica quién la revisó (por=...)")
        entry = self.get_entry(glosa)
        if entry is None or entry.fuente == "carpeta":
            raise KeyError(f"{glosa!r} no está registrada en ningún JSON de {self.glossaries_dir}")
        jf = Path(entry.fuente)
        data = json.loads(jf.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("senas", [])
        key = normalize_text(entry.glosa)
        for item in items:
            if isinstance(item, dict) and normalize_text(str(item.get("glosa", ""))) == key:
                item["estado"] = estado
                if estado == VALIDADA:
                    item["validado_por"], item["fecha_validacion"] = por.strip(), date.today().isoformat()
                else:
                    item.pop("validado_por", None)
                    item.pop("fecha_validacion", None)
                break
        else:
            raise KeyError(f"{glosa!r} no se encontró en {jf.name}")
        tmp = jf.with_name(jf.name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, jf)
        self.reload()

    def clip_path_for(self, word: str, ext: str = ".mp4") -> Path:
        """
        Ruta donde guardar un clip nuevo para que reload() lo asocie a la glosa
        ("Buenos días" -> buenos_dias.mp4). Las letras usan Fingerspeller.clip_path_for.
        """
        key = normalize_text(word)
        if not key:
            raise ValueError("La palabra no tiene texto utilizable")
        ext = ext.lower() if ext.startswith(".") else "." + ext.lower()
        if ext not in EXT_PRIORITY:
            raise ValueError(f"Extensión no soportada: {ext}")
        return self.signs_dir / (key.replace(" ", "_") + ext)

    def words(self) -> list[str]:
        return sorted(k for k, e in self._state.entries.items() if self._usable(e))

    def summary(self) -> dict:
        return {"estados": self.validation_report(), "sin_clip": len(self.missing_clips()),
                "letras": len(self.fingerspeller), "letras_faltantes": self.fingerspeller.missing()}

    def __len__(self) -> int:
        return len(self.words())

    def __contains__(self, word: str) -> bool:
        return self.get_sign_path(word) is not None