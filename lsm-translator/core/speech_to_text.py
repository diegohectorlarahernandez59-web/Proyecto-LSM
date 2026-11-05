from google.genai import types
from core.gemini_client import GeminiClient

class SpeechToText:
    def __init__(self):
        self.gemini_client = GeminiClient()

    def transcribe_audio(self, audio_data_bytes):
        """
        Toma bytes de audio en crudo y los transcribe a texto en tiempo real usando Gemini.
        """
        if not audio_data_bytes:
            return ""

        prompt = [
            types.Part.from_bytes(
                data=audio_data_bytes,
                mime_type="audio/wav",
            ),
            (
                "Transcribe de manera fiel, clara y en tiempo real el siguiente fragmento de audio en español. "
                "Devuelve solo el texto correspondiente."
            )
        ]

        try:
            response = self.gemini_client.client.models.generate_content(
                model=self.gemini_client.model,
                contents=prompt,
            )
            return response.text.strip() if response.text else ""
        except Exception as e:
            print(f"Error en SpeechToText: {e}")
            return ""