# import sys
# import os
# import time

# # Agrega la carpeta raíz del proyecto (lsm-translator) al path de Python 
# # para que VS Code encuentre la carpeta 'capture' sin importar desde dónde se ejecute.
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# from capture.camera import CameraCapture
# from capture.microphone import MicrophoneCapture

# class ClassroomMode:
#     def __init__(self):
#         self.camera = CameraCapture()        # Instantiates your camera capture module
#         self.microphone = MicrophoneCapture()# Instantiates your microphone capture module
#         self.is_running = False              # Tracks whether classroom mode is active

#     def iniciar_clase(self):
#         """Inicia los flujos de captura para el modo clase."""
#         print("Iniciando Modo Clase...")
#         self.camera.iniciar()                # Powers on the camera background thread
#         self.microphone.iniciar()            # Powers on the microphone audio stream
#         self.is_running = True

#     def procesar_ciclo(self):
#         """Obtiene datos en tiempo real de la cámara y el micrófono."""
#         if not self.is_running:
#             return None, None

#         # Capturar frame actual para el reconocedor de señas del alumno
#         frame = self.camera.obtener_frame()
        
#         # Capturar bloque de audio para los subtítulos en vivo del docente
#         audio_block = self.microphone.obtener_bloque()

#         return frame, audio_block            # Returns both data streams to the application loop

#     def detener_clase(self):
#         """Detiene la captura al salir del modo."""
#         print("Finalizando Modo Clase...")
#         self.is_running = False
#         self.camera.detener()                # Shuts down the camera safely
#         self.microphone.detener()            # Shuts down the microphone safely


#Codigo de prueba del modo clase
import sys
import os
import time
import subprocess
import cv2
import soundfile as sf
import numpy as np

# Agrega la carpeta raíz del proyecto al path para evitar problemas con VS Code
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from capture.camera import CameraCapture
from capture.microphone import MicrophoneCapture

class ClassroomMode:
    def __init__(self):
        self.camera = CameraCapture()        # Instancia el módulo de cámara
        self.microphone = MicrophoneCapture()# Instancia el módulo de micrófono
        self.is_running = False              # Estado activo del modo clase

    def iniciar_clase(self):
        """Inicia los flujos de captura para el modo clase."""
        print("Iniciando Modo Clase...")
        self.camera.iniciar()                # Enciende el hilo de la cámara
        self.microphone.iniciar()            # Enciende el flujo de audio
        self.is_running = True

    def procesar_ciclo(self):
        """Obtiene datos en tiempo real de la cámara y el micrófono."""
        if not self.is_running:
            return None, None

        # Capturar frame actual para el reconocedor de señas
        frame = self.camera.obtener_frame()
        
        # Capturar bloque de audio para los subtítulos en vivo
        audio_block = self.microphone.obtener_bloque()

        return frame, audio_block            # Devuelve ambos flujos sincronizados

    def detener_clase(self):
        """Detiene la captura al salir del modo."""
        print("Finalizando Modo Clase...")
        self.is_running = False
        self.camera.detener()                # Cierra la cámara de forma segura
        self.microphone.detener()            # Cierra el micrófono de forma segura

# Bloque de prueba integral: Genera todas las evidencias y convierte el video automáticamente
if __name__ == "__main__":
    print("=== PROBANDO MODO CLASE (Grabación de 10s + Generación de Todas las Evidencias) ===")
    clase = ClassroomMode()
    
    # Nombres de archivos de salida
    video_temp = 'evidencia_clase_temp.mp4'
    video_final = 'evidencia_clase_final.mp4'
    audio_file = 'evidencia_clase_audio.wav'
    reporte_file = 'reporte_modo_clase.txt'
    
    # Configurar grabador de video temporal y listas de control
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video_out = cv2.VideoWriter(video_temp, fourcc, 30.0, (640, 480))
    audio_chunks = []
    
    try:
        clase.iniciar_clase()
        print("🔴 Dispositivos activos. Ventana en vivo abierta por 10 segundos...")
        
        start_time = time.time()
        duracion_prueba = 10  # Duración de la prueba en segundos
        ciclos = 0
        
        # Abrir archivo de texto para el reporte simultáneo
        with open(reporte_file, "w") as f_rep:
            f_rep.write("--- REPORTE DE PRUEBA: MODO CLASE UNIFICADO (LSM-Translator) ---\n")
            f_rep.write(f"Fecha y hora: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            while time.time() - start_time < duracion_prueba:
                frame, audio_block = clase.procesar_ciclo()
                ciclos += 1
                
                # 1. Procesar video (mostrar y grabar)
                if frame is not None:
                    video_out.write(frame)
                    cv2.imshow("Prueba Modo Clase - Camara en Vivo", frame)
                    f_status = f"Frame OK {frame.shape}"
                else:
                    f_status = "Frame vacío"
                
                # 2. Procesar audio
                if audio_block is not None:
                    audio_chunks.append(audio_block)
                    a_status = f"Audio OK {audio_block.shape}"
                else:
                    a_status = "Audio vacío"
                
                # Escribir línea en el reporte de texto
                log_line = f"Ciclo {ciclos:02d} -> {f_status} | {a_status}\n"
                f_rep.write(log_line)
                
                # Permitir salir antes presionando 'q'
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
            f_rep.write(f"\nPrueba finalizada. Total de ciclos: {ciclos}\n")
            
        print("\n✔️ ¡Captura de datos finalizada!")
        
    except Exception as e:
        print(f"❌ Error durante la ejecución: {e}")
    finally:
        video_out.release()
        cv2.destroyAllWindows()
        clase.detener_clase()

    # --- POST-PROCESAMIENTO Y GUARDADO AUTOMÁTICO DE TODAS LAS EVIDENCIAS ---
    print("\n📦 Generando y consolidando archivos de evidencia para tu reporte...")
    
    # 1. Guardar Audio (.wav)
    if audio_chunks:
        audio_data = np.concatenate(audio_chunks, axis=0)
        sf.write(audio_file, audio_data, clase.microphone.samplerate)
        print(f"  📁 [1/3] Audio guardado con éxito: '{audio_file}'")
    
    # 2. Reporte de Texto (.txt)
    print(f"  📁 [2/3] Reporte de registros guardado con éxito: '{reporte_file}'")

    # 3. Transcodificar Video a MP4 Universal con FFmpeg
    if os.path.exists(video_temp):
        try:
            print(f"  🔄 Transcodificando video a formato universal H.264...")
            subprocess.run([
                'ffmpeg', '-y', '-i', video_temp,
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
                '-pix_fmt', 'yuv420p', video_final
            ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Limpiar archivo temporal
            os.remove(video_temp)
            print(f"  📁 [3/3] Video universal generado: '{video_final}' (¡Listo para abrir y enviar sin errores!)")
        except Exception as e:
            print(f"  ⚠️ No se pudo ejecutar ffmpeg automáticamente: {e}")
            print(f"     (El video temporal sin optimizar sigue disponible en '{video_temp}')")

    print("\n=== TODAS LAS EVIDENCIAS FUERON GUARDADAS CORRECTAMENTE ===")