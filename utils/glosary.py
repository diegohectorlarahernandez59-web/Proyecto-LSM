import os
import unicodedata
from pathlib import Path

class GlossaryManager:
    def __init__(self, signs_dir: str = "assets/signs"):
        """
        Inicializa el gestor del glosario visual escaneando la carpeta de assets.
        """
        self.signs_dir = Path(signs_dir)
        self.glossary_map = {}
        self._load_glossary()

    def _normalize_text(self, text: str) -> str:
        """
        Normaliza el texto: convierte a minúsculas, elimina acentos y espacios extras.
        Ejemplo: "¡Hola, Cómo estás! " -> "hola como estas"
        """
        text = text.lower().strip()
        # Eliminar acentos (normalización Unicode NFD)
        text = ''.join(
            c for c in unicodedata.normalize('NFD', text)
            if unicodedata.category(c) != 'Mn'
        )
        return text

    def _load_glossary(self):
        """
        Escanea el directorio de signos y mapea la palabra normalizada a la ruta del archivo.
        Soporta extensiones comunes de video e imagen (.mp4, .avi, .gif, .png).
        """
        supported_extensions = {'.mp4', '.avi', '.mov', '.gif', '.png', '.jpg'}
        
        if not self.signs_dir.exists():
            print(f"[Advertencia] La ruta del glosario {self.signs_dir} no existe. Creándola...")
            self.signs_dir.mkdir(parents=True, exist_ok=True)
            return

        for file_path in self.signs_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                # El nombre del archivo sin extensión es la palabra clave (ej. "gracias.mp4" -> "gracias")
                clean_name = self._normalize_text(file_path.stem)
                self.glossary_map[clean_name] = str(file_path.resolve())

        print(f"[GlossaryManager] Se cargaron {len(self.glossary_map)} señas desde {self.signs_dir}")

    def get_sign_path(self, word: str) -> str | None:
        """
        Busca una palabra en el glosario.
        Retorna la ruta absoluta del archivo si existe, o None si no se encuentra (para activar deletreo).
        """
        normalized_word = self._normalize_text(word)
        return self.glossary_map.get(normalized_word, None)

    def reload(self):
        """Recarga el glosario por si se agregaron nuevos archivos en tiempo de ejecución."""
        self.glossary_map.clear()
        self._load_glossary()