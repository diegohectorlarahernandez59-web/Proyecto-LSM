"""
utils/glossary.py: glosario visual palabra -> clip de seña (LSM).

Estructura esperada de assets/signs/:
    hola.mp4, gracias.gif, buenos_dias.mp4     palabras o frases (guion bajo = espacio)
    alfabeto/a.png ... alfabeto/ñ.mp4          letras para deletrear
    letra_b.png                                otra forma de marcar una letra
    aliases.json (opcional)                    {"gracias": ["muchas gracias"]}

Si hay dos archivos con el mismo nombre se prefiere video sobre imagen.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)

# utils/glossary.py -> raíz del proyecto -> assets/signs (no depende de dónde se ejecute)
DEFAULT_SIGNS_DIR = Path(__file__).resolve().parent.parent / "assets" / "signs"

# Número menor = mayor prioridad cuando dos archivos comparten nombre.
EXT_PRIORITY = {
    ".mp4": 0, ".webm": 0, ".mov": 1, ".avi": 2,
    ".gif": 3, ".png": 4, ".jpg": 5, ".jpeg": 5, ".webp": 5,
}
ALPHABET_DIRS = {"alfabeto", "abecedario", "letras", "dactilologia"}
ALPHABET = "abcdefghijklmnñopqrstuvwxyz"
ALIASES_FILE = "aliases.json"

_ENE = "\ue000"  # protege la ñ mientras se quitan los acentos
_NON_WORD = re.compile(r"[^a-z0-9ñ\s]")


@lru_cache(maxsize=8192)
def normalize_text(text: str) -> str:
    """
    Minúsculas, sin acentos ni signos, espacios colapsados. Conserva la ñ
    (no es lo mismo "año" que "ano").
    "¡Hola, Cómo estás! " -> "hola como estas"
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


@dataclass(frozen=True)
class SignItem:
    text: str                  # palabra, frase o letra solicitada
    kind: str                  # "sign" | "letter" | "missing"
    path: str | None = None    # ruta absoluta del clip, None si kind == "missing"


@dataclass(frozen=True)
class _Snapshot:
    words: dict
    letters: dict
    max_phrase: int


def _register(target: dict, key: str, path: Path):
    prio = EXT_PRIORITY[path.suffix.lower()]
    prev = target.get(key)
    if prev is None or prio < prev[0]:
        if prev:
            log.warning("Duplicado %r: se usa %s en lugar de %s", key, path.name, Path(prev[1]).name)
        target[key] = (prio, str(path.resolve()))
    else:
        log.warning("Duplicado %r: se ignora %s", key, path)


class GlossaryManager:
    def __init__(self, signs_dir: str | Path | None = None, create_if_missing: bool = True):
        self.signs_dir = Path(signs_dir) if signs_dir else DEFAULT_SIGNS_DIR
        self.create_if_missing = create_if_missing
        self._state = _Snapshot({}, {}, 1)
        self.reload()

    # ---------- Carga ----------
    def reload(self) -> int:
        """
        Reescanea la carpeta. Arma un glosario nuevo y lo intercambia de una vez,
        así otros hilos nunca ven un glosario a medias. Devuelve el total de palabras.
        """
        if not self.signs_dir.is_dir():
            log.warning("La ruta del glosario %s no existe.", self.signs_dir)
            if self.create_if_missing:
                self.signs_dir.mkdir(parents=True, exist_ok=True)
            self._state = _Snapshot({}, {}, 1)
            return 0

        words: dict = {}
        letters: dict = {}
        for path in sorted(self.signs_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in EXT_PRIORITY:
                continue
            rel = path.relative_to(self.signs_dir)
            if any(part.startswith(".") for part in rel.parts):
                continue
            key = normalize_text(path.stem.replace("_", " "))
            is_letter = any(normalize_text(p) in ALPHABET_DIRS for p in rel.parts[:-1])
            if key.startswith("letra "):
                key, is_letter = key[6:], True
            if not key:
                log.warning("Nombre de archivo sin texto utilizable: %s", path)
            elif is_letter and len(key) != 1:
                log.warning("Letra inválida %r en %s (debe ser 1 carácter)", key, path)
            else:
                _register(letters if is_letter else words, key, path)

        words = {k: v[1] for k, v in words.items()}
        letters = {k: v[1] for k, v in letters.items()}
        self._load_aliases(words)

        self._state = _Snapshot(words, letters, max((k.count(" ") + 1 for k in words), default=1))
        log.info("Glosario: %d señas, %d letras. Faltan letras: %s",
                 len(words), len(letters), "".join(self.missing_letters()) or "ninguna")
        return len(words)

    def _load_aliases(self, words: dict):
        path = self.signs_dir / ALIASES_FILE
        if not path.is_file():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("debe ser un objeto JSON")
        except (OSError, ValueError) as e:
            log.warning("No se pudo leer %s: %s", path, e)
            return
        for canonical, alts in data.items():
            target = words.get(normalize_text(canonical))
            if target is None:
                log.warning("Alias para %r ignorado: no existe esa seña", canonical)
                continue
            for alt in [alts] if isinstance(alts, str) else alts:
                words.setdefault(normalize_text(alt), target)

    # ---------- Consulta ----------
    @staticmethod
    def _lookup(snap: _Snapshot, phrase: str) -> str | None:
        if phrase:
            for cand in _variants(phrase):
                if cand in snap.words:
                    return snap.words[cand]
        return None

    @staticmethod
    def _spell(snap: _Snapshot, word: str) -> list[SignItem]:
        return [
            SignItem(c, "letter", snap.letters[c]) if c in snap.letters else SignItem(c, "missing")
            for c in word
        ]

    def get_sign_path(self, word: str) -> str | None:
        """Ruta absoluta del clip de la palabra o frase, o None si no existe (activar deletreo)."""
        return self._lookup(self._state, normalize_text(word))

    def get_letter_path(self, char: str) -> str | None:
        char = normalize_text(char)
        return self._state.letters.get(char) if len(char) == 1 else None

    def spell(self, word: str) -> list[SignItem]:
        """Deletrea la palabra letra por letra con el alfabeto del glosario."""
        return self._spell(self._state, normalize_text(word).replace(" ", ""))

    def resolve(self, text: str | Iterable[str], spell_missing: bool = True) -> list[SignItem]:
        """
        Convierte un texto (o la glosa que devuelve Gemini) en la lista ordenada de clips.
        Busca primero la frase más larga que exista ("buenos dias" antes que "buenos" + "dias").
        Lo que no está en el glosario se deletrea; las letras sin clip salen como "missing".
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
                path = self._lookup(snap, phrase)
                if path:
                    items.append(SignItem(phrase, "sign", path))
                    i += n
                    break
            else:
                items.extend(self._spell(snap, tokens[i]) if spell_missing
                             else [SignItem(tokens[i], "missing")])
                i += 1
        return items

    # ---------- Utilidades de mantenimiento ----------
    def missing_words(self, vocabulary: Iterable[str]) -> list[str]:
        """Del vocabulario inicial que quieres cubrir, cuáles aún no tienen clip."""
        return [w for w in vocabulary if self.get_sign_path(w) is None]

    def missing_letters(self) -> list[str]:
        return [c for c in ALPHABET if c not in self._state.letters]

    def words(self) -> list[str]:
        return sorted(self._state.words)

    def summary(self) -> dict:
        s = self._state
        return {"palabras": len(s.words), "letras": len(s.letters),
                "letras_faltantes": self.missing_letters()}

    @property
    def glossary_map(self) -> dict:
        """Copia del mapa palabra -> ruta (compatibilidad con la versión anterior)."""
        return dict(self._state.words)

    def __len__(self) -> int:
        return len(self._state.words)

    def __contains__(self, word: str) -> bool:
        return self.get_sign_path(word) is not None


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    g = GlossaryManager()
    print(g.summary())
    for it in g.resolve(" ".join(sys.argv[1:]) or "hola"):
        print(f"{it.kind:8} {it.text:16} {it.path or ''}")