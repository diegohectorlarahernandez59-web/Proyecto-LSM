from typing import Dict, Any, List
from pathlib import Path


class GlossaryManager:
    """Gestiona el mapa de palabras y la lógica para resolver señales."""

    def __init__(self, signs_dir: Path):
        """Inicializa el gestor con la ruta donde se guardarán los clips."""
        self._words: Dict[str, Any] = {}  # Mapeo de palabra -> información
        self.signs_dir = signs_dir

    def add_word(self, word: str, info: Any):
        """Añade una palabra al glosario."""
        self._words[word] = info

    def get_sign_path(self, word: str) -> Path | None:
        """Busca la ruta del clip asociado a una palabra."""
        return self._words.get(word, {}).get('path')

    def summary(self) -> Dict[str, int]:
        """Devuelve un resumen estadístico del glosario."""
        return {
            "palabras": len(self._words),
            "letras": 0,  # Implementar si se usa para contar caracteres
            "letras_faltantes": 0, # Implementar si se usa para contar faltantes
        }

    @property
    def glossary_map(self) -> Dict[str, Any]:
        """Copia del mapa palabra -> ruta."""
        return dict(self._words)

    def __len__(self) -> int:
        """Retorna el número total de entradas en el glosario."""
        return len(self._words)

    def reload(self):
        """Simula la recarga del glosario (podría ser para cargar archivos externos)."""
        print("GlossaryManager: Recargando mapa...")
        # Aquí iría la lógica para cargar datos nuevos si fuera necesario

    def clip_path_for(self, word: str, letter: bool = False) -> Path:
        """Genera la ruta esperada para guardar un clip."""
        # Ejemplo de lógica: (word + extension).mp4
        safe_word = "".join(c for c in word if c.isalnum()) # Limpiar la palabra
        return self.signs_dir / f"{safe_word}{('.mp4' if letter else '')}"

