from core.gemini_client import GeminiClient

class TextToGloss:
    def __init__(self):
        self.gemini = GeminiClient()

    def translate(self, spanish_text):
        """
        Convierte una oración en español a una secuencia de glosas en LSM usando Gemini.
        """
        if not spanish_text:
            return []

        prompt = (
            "Eres un intérprete experto en Lengua de Señas Mexicana (LSM). "
            "Convierte la siguiente oración en español a la estructura de glosas de LSM correspondiente:\n\n"
            f"Español: \"{spanish_text}\"\n\n"
            "Devuelve únicamente las glosas separadas por espacios (ej. CASA IR YO MAÑANA):"
        )

        response = self.gemini.generate_content(prompt)
        return response.split() if response else []