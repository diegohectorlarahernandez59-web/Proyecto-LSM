import queue
import sounddevice as sd
import numpy as np
import time

class MicrophoneCapture:
    def __init__(self, samplerate: int = 16000, blocksize: int = 8000):
        self.samplerate = samplerate        # Audio sample rate (16 kHz is optimal for speech recognition)
        self.blocksize = blocksize          # Number of audio frames per block
        self.audio_queue = queue.Queue()    # Thread-safe queue to pass audio blocks to downstream modules
        self.stream = None                  # Audio input stream placeholder

    def _audio_callback(self, indata, frames, time_info, status):
        """Función callback ejecutada por sounddevice para cada bloque de audio."""
        if status:
            print(f"Estado de audio: {status}", flush=True) # Prints warnings if audio buffer overflows/underflows
        self.audio_queue.put(indata.copy()) # Puts a copy of the recorded audio chunk into the queue

    def iniciar(self):
        """Inicia el flujo de entrada de audio."""
        self.stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=1,                     # Mono audio recording
            dtype='int16',                  # 16-bit integer audio format
            blocksize=self.blocksize,       
            callback=self._audio_callback   # Links the continuous stream to your callback function
        )
        self.stream.start()                 # Starts streaming audio from the microphone hardware

    def obtener_bloque(self):
        """Extrae un bloque de audio de la cola si está disponible."""
        try:
            return self.audio_queue.get_nowait() # Pulls an item immediately without waiting
        except queue.Empty:
            return None                     # Returns None if no new audio block is ready yet

    def detener(self):
        """Detiene y cierra el flujo de audio."""
        if self.stream:
            self.stream.stop()              # Stops the input audio stream
            self.stream.close()             # Closes the audio stream and frees hardware resources

# Bloque para probar el micrófono directamente desde la terminal
if __name__ == "__main__":
    print("=== PROBANDO MICRÓFONO DIRECTAMENTE ===")
    mic = MicrophoneCapture()
    try:
        mic.iniciar()
        print("Micrófono abierto. Habla durante 3 segundos para probar la captura...")
        
        start_time = time.time()
        blocks_received = 0
        
        while time.time() - start_time < 3:
            block = mic.obtener_bloque()
            if block is not None:
                blocks_received += 1
                print(f"✔️ Bloque de audio recibido - Tamaño: {block.shape}")
            time.sleep(0.2)
            
        print(f"\n¡Prueba exitosa! Se capturaron {blocks_received} bloques de audio en total.")
    except Exception as e:
        print(f"❌ Error al probar el micrófono: {e}")
    finally:
        mic.detener()
        print("=== PRUEBA FINALIZADA ===")