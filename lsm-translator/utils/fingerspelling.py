"""
utils/fingerspelling.py: deletreo para palabras que no están en el glosario.

Busca los clips del alfabeto dactilológico en assets/signs/:
    alfabeto/a.png ... alfabeto/ñ.mp4 ... alfabeto/0.png     (carpeta alfabeto/)
    letra_b.png                                              (o con prefijo "letra_")
Si hay dos clips para la misma letra se prefiere el video (algunas letras llevan movimiento).
"""
from __future__ import annotations

import logging
from pathlib import Path

from .glossary import (DEFAULT_SIGNS_DIR, EXT_PRIORITY, LETTER_PREFIX, SignItem, is_alphabet_file,
                       iter_clips, normalize_text, register_clip)

log = logging.getLogger(__name__)

ALPHABET = "abcdefghijklmnñopqrstuvwxyz"
DIGITS = "0123456789"


class Fingerspeller:
    def __init__(self, signs_dir: str | Path | None = None):
        self.signs_dir = Path(signs_dir) if signs_dir else DEFAULT_SIGNS_DIR
        self._letters: dict[str, str] = {}
        self.reload()

    def reload(self) -> int:
        """Reescanea el alfabeto y lo intercambia de una vez (seguro entre hilos)."""
        found: dict = {}
        if self.signs_dir.is_dir():
            for path, rel in iter_clips(self.signs_dir):
                if not is_alphabet_file(rel):
                    continue
                key = normalize_text(path.stem)
                if key.startswith(LETTER_PREFIX):
                    key = key[len(LETTER_PREFIX):]
                if len(key) == 1:
                    register_clip(found, key, path)
                else:
                    log.warning("Letra inválida %r en %s (debe ser 1 carácter)", key, path)
        self._letters = {k: v[1] for k, v in found.items()}
        return len(self._letters)

    def get(self, char: str) -> str | None:
        """Ruta del clip de una letra o dígito, o None."""
        char = normalize_text(char)
        return self._letters.get(char) if len(char) == 1 else None

    def spell(self, word: str) -> list[SignItem]:
        """
        Una SignItem por carácter: kind="letter" si hay clip, "missing" si falta.
        Se ignoran espacios y signos ("¡Ana!" -> a, n, a).
        """
        letters = self._letters
        return [
            SignItem(c, "letter", letters[c]) if c in letters else SignItem(c, "missing")
            for c in normalize_text(word).replace(" ", "")
        ]

    def missing(self, include_digits: bool = False) -> list[str]:
        """Letras (y dígitos, si se pide) que aún no tienen clip."""
        wanted = ALPHABET + (DIGITS if include_digits else "")
        return [c for c in wanted if c not in self._letters]

    def clip_path_for(self, char: str, ext: str = ".mp4") -> Path:
        """Ruta donde guardar el clip de una letra: assets/signs/alfabeto/<letra>.mp4"""
        key = normalize_text(char)
        if len(key) != 1:
            raise ValueError("Una letra debe tener 1 carácter")
        ext = ext.lower() if ext.startswith(".") else "." + ext.lower()
        if ext not in EXT_PRIORITY:
            raise ValueError(f"Extensión no soportada: {ext}")
        return self.signs_dir / "alfabeto" / (key + ext)

    def __len__(self) -> int:
        return len(self._letters)

    def __contains__(self, char: str) -> bool:
        return self.get(char) is not None