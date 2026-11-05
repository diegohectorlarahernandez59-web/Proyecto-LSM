from core.gemini_client import GeminiClient

class GlossToText:
    def __init__(self):
        self.gemini = GeminiClient()

    def translate(self, gloss_sequence):
        """
        Convierte una lista de glosas de LSM a una oración coherente en español usando Gemini.
        """
        if not gloss_sequence:
            return ""

        gloss_str = " ".join(gloss_sequence)
        prompt = (
            "Eres un experto lingüista en Lengua de Señas Mexicana (LSM) y español. "
            "Las señas se estructuran en glosas con reglas gramaticales propias. "
            "Traduce la siguiente secuencia de glosas de LSM a una oración en español natural, correcta y fluida:\n\n"
            f"Glosas: [{gloss_str}]\n\n"
            "Devuelve únicamente la oración traducida en español:"
        )

        return self.gemini.generate_content(prompt)