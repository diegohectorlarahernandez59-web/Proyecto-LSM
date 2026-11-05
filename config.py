import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-2.5-flash"

"""Parametros de hardware"""

CAMERA_FPS = 30
AUDIO_SAMPLE_RATE = 16000

"""parametros de clasificador"""

FRAME_WINDOW_SIZE = 30
CONFIDENCE_THRESHOLD = 0.8
CONSECUTIVE_PREDICTIONS = 3
MODEL_PATH = "lsm-translator/data/models/"

# --- Bloque de prueba ---
if __name__ == "__main__":
    print("\n=== Prueba de Configuración ===")
    print(f"¿API Key detectada en .env?: {bool(GEMINI_API_KEY)}")
    print(f"Modelo de Gemini: {MODEL_NAME}")
    print(f"Ruta del modelo local: {MODEL_PATH}")
    print("¡Si ves este mensaje sin errores, tus requerimientos y configuración funcionan al 100%!\n")