import os
from google import genai
from config import GEMINI_API_KEY, GEMINI_MODEL

class GeminiClient:
    def __init__(self):
        """Inicializa el cliente de Gemini para tareas puramente de texto/glosas."""
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY no está configurada en las variables de entorno.")
        
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model = GEMINI_MODEL

    def generate_content(self, prompt_text):
        """Envía un prompt de texto a Gemini y retorna la respuesta limpia."""
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt_text,
            )
            return response.text.strip() if response.text else ""
        except Exception as e:
            print(f"Error al comunicar con Gemini (Core Texto): {e}")
            return ""