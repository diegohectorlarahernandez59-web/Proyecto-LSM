from gtts import gTTS
import os

class TextToSpeech:
    def __init__(self, lang='es'):
        self.lang = lang

    def speak(self, text, output_path="assets/temp_output.mp3"):
        """Convierte texto a archivo de audio MP3."""
        if not text.strip():
            return None
        
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            tts = gTTS(text=text, lang=self.lang, slow=False)
            tts.save(output_path)
            return output_path
        except Exception as e:
            print(f"Error en TextToSpeech: {e}")
            return None