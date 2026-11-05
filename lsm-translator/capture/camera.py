# Código de captura de cámara y prueba de grabación MP4
import cv2
import threading
import time

class CameraCapture:
    def __init__(self, width: int = 640, height: int = 480, fps: int = 30):
        self.width = width
        self.height = height
        self.target_fps = fps
        self.cap = None
        self.running = False
        self.current_frame = None
        self.lock = threading.Lock()
        self.thread = None

    def iniciar(self):
        """Abre la cámara y arranca el hilo de captura en segundo plano."""
        # Usamos el índice 0 para la cámara web integrada principal
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        
        if not self.cap.isOpened():
            raise RuntimeError("No se pudo abrir la cámara.")

        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def _capture_loop(self):
        """Bucle interno que lee los frames de la cámara constantemente."""
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.resize(frame, (self.width, self.height))
                with self.lock:
                    self.current_frame = frame
            time.sleep(1 / self.target_fps)

    def obtener_frame(self):
        """Devuelve una copia del último frame capturado de forma segura."""
        with self.lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
            return None

    def detener(self):
        """Detiene el hilo de la cámara y libera el recurso físico."""
        self.running = False
        if self.thread:
            self.thread.join()
        if self.cap:
            self.cap.release()

# Bloque de prueba directa y guardado de video de evidencia en formato MP4 (3 segundos)
if __name__ == "__main__":
    print("=== PROBANDO CÁMARA Y GUARDANDO VIDEO MP4 DE 3 SEGUNDOS ===")
    cam = CameraCapture(width=640, height=480, fps=30)
    
    # Configurar el códec a 'mp4v' y la extensión del archivo a .mp4
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter('evidencia_video_camara.mp4', fourcc, 30.0, (640, 480))
    
    try:
        cam.iniciar()
        print("Cámara abierta. Grabando video de prueba por 3 segundos...")
        
        start_time = time.time()
        frames_grabados = 0
        
        while time.time() - start_time < 3:
            frame = cam.obtener_frame()
            if frame is not None:
                out.write(frame)
                frames_grabados += 1
            time.sleep(1 / 30)
            
        print(f"✔️ ¡Video guardado con éxito! Se grabaron {frames_grabados} frames.")
        print("📁 Archivo generado: 'evidencia_video_camara.mp4'")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        out.release()
        cam.detener()
        print("=== PRUEBA DE CÁMARA FINALIZADA ===")