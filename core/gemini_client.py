import os
from google import genai
from config import GEMINI_API_KEY, GEMINI_MODEL

class GeminiClient:
    def __init__(self):
        """Inicializa el cliente de Gemini con la API key y el modelo configurado."""
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY no está configurada en las variables de entorno.")
        
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model = GEMINI_MODEL

    def generate_content(self, contents):
        """Envía contenido multimodal o texto a Gemini y retorna la respuesta en texto."""
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
            )
            return response.text
        except Exception as e:
            print(f"Error al comunicar con Gemini: {e}")
            return ""