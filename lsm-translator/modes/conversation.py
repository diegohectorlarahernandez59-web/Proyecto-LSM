# import sys
# import os
# import time

# # Agrega la carpeta raíz del proyecto al path para evitar problemas de importación en VS Code
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# from capture.camera import CameraCapture
# from capture.microphone import MicrophoneCapture

# class ConversationMode:
#     def __init__(self):
#         self.camera = CameraCapture()        # Instancia el módulo de cámara para las señas
#         self.microphone = MicrophoneCapture()# Instancia el módulo de micrófono para la voz
#         self.is_running = False              # Estado activo del modo conversación

#     def iniciar_conversacion(self):
#         """Inicia los flujos de captura simultáneos para el modo conversación."""
#         print("Iniciando Modo Conversación...")
#         self.camera.iniciar()                # Enciende el hilo de la cámara
#         self.microphone.iniciar()            # Enciende el flujo de audio
#         self.is_running = True

#     def procesar_ciclo(self):
#         """Obtiene en tiempo real el frame de la seña y el bloque de audio de la voz."""
#         if not self.is_running:
#             return None, None

#         # Capturar frame actual de la cámara (para el modelo de traducción de señas)
#         frame = self.camera.obtener_frame()
        
#         # Capturar bloque de audio del micrófono (para el reconocimiento de voz / transcripción)
#         audio_block = self.microphone.obtener_bloque()

#         return frame, audio_block            # Devuelve ambos flujos sincronizados al bucle principal

#     def detener_conversacion(self):
#         """Finaliza y libera los recursos de hardware de forma segura."""
#         print("Finalizando Modo Conversación...")
#         self.is_running = False
#         self.camera.detener()                # Cierra la cámara de forma segura
#         self.microphone.detener()            # Cierra el micrófono de forma segura


#Prueba del modo conversación
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

class ConversationMode:
    def __init__(self):
        self.camera = CameraCapture()        # Instancia el módulo de cámara para las señas
        self.microphone = MicrophoneCapture()# Instancia el módulo de micrófono para la voz
        self.is_running = False              # Estado activo del modo conversación

    def iniciar_conversacion(self):
        """Inicia los flujos de captura simultáneos para el modo conversación."""
        print("Iniciando Modo Conversación...")
        self.camera.iniciar()                # Enciende el hilo de la cámara
        self.microphone.iniciar()            # Enciende el flujo de audio
        self.is_running = True

    def procesar_ciclo(self):
        """Obtiene en tiempo real el frame de la seña y el bloque de audio de la voz."""
        if not self.is_running:
            return None, None

        # Capturar frame actual de la cámara (para el modelo de traducción de señas)
        frame = self.camera.obtener_frame()
        
        # Capturar bloque de audio del micrófono (para el reconocimiento de voz / transcripción)
        audio_block = self.microphone.obtener_bloque()

        return frame, audio_block            # Devuelve ambos flujos sincronizados al bucle principal

    def detener_conversacion(self):
        """Finaliza y libera los recursos de hardware de forma segura."""
        print("Finalizando Modo Conversación...")
        self.is_running = False
        self.camera.detener()                # Cierra la cámara de forma segura
        self.microphone.detener()            # Cierra el micrófono de forma segura

# Bloque de prueba integral optimizado para asegurar la captura de audio y video
if __name__ == "__main__":
    print("=== PROBANDO MODO CONVERSACIÓN (10s + Forzado de Grabación de Audio y Video) ===")
    conv = ConversationMode()
    
    # Nombres de archivos de salida
    video_temp = 'evidencia_conversacion_temp.mp4'
    video_final = 'evidencia_conversacion_final.mp4'
    audio_file = 'evidencia_conversacion_audio.wav'
    reporte_file = 'reporte_modo_conversacion.txt'
    
    # Configurar grabador de video temporal y listas de control
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video_out = cv2.VideoWriter(video_temp, fourcc, 30.0, (640, 480))
    audio_chunks = []
    
    try:
        conv.iniciar_conversacion()
        print("🔴 Dispositivos activos. Habla y gesticula frente a la cámara durante 10 segundos...")
        
        start_time = time.time()
        duracion_prueba = 10  # Duración de la prueba en segundos
        ciclos = 0
        
        # Abrir archivo de texto para el reporte simultáneo
        with open(reporte_file, "w") as f_rep:
            f_rep.write("--- REPORTE DE PRUEBA: MODO CONVERSACIÓN (LSM-Translator) ---\n")
            f_rep.write(f"Fecha y hora: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            while time.time() - start_time < duracion_prueba:
                frame, audio_block = conv.procesar_ciclo()
                ciclos += 1
                
                # 1. Procesar video (mostrar en ventana y grabar)
                if frame is not None:
                    video_out.write(frame)
                    cv2.imshow("Prueba Modo Conversacion - Camara en Vivo", frame)
                    f_status = f"Frame OK {frame.shape}"
                else:
                    f_status = "Frame vacío"
                
                # 2. Acumular bloques de audio de manera estricta
                if audio_block is not None and len(audio_block) > 0:
                    audio_chunks.append(audio_block)
                    a_status = f"Audio OK {audio_block.shape}"
                else:
                    a_status = "Audio vacío / esperando"
                
                # Escribir línea en el reporte de texto
                log_line = f"Ciclo {ciclos:02d} -> {f_status} | {a_status}\n"
                f_rep.write(log_line)
                
                # Pequeña pausa para sincronizar tasa de muestreo y permitir captura del micro
                time.sleep(0.01)
                
                # Permitir salir antes presionando 'q'
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
            f_rep.write(f"\nPrueba finalizada. Total de ciclos: {ciclos}\n")
            
        print("\n✔️ ¡Captura de datos de conversación finalizada!")
        
    except Exception as e:
        print(f"❌ Error durante la ejecución: {e}")
    finally:
        video_out.release()
        cv2.destroyAllWindows()
        conv.detener_conversacion()

    # --- POST-PROCESAMIENTO Y GUARDADO AUTOMÁTICO DE TODAS LAS EVIDENCIAS ---
    print("\n📦 Consolidando archivos de evidencia para el Modo Conversación...")
    
    # 1. Guardar Audio (.wav) de forma garantizada
    if len(audio_chunks) > 0:
        audio_data = np.concatenate(audio_chunks, axis=0)
        sf.write(audio_file, audio_data, conv.microphone.samplerate)
        print(f"  📁 [1/3] Audio guardado con éxito: '{audio_file}' ({len(audio_data)} samples)")
    else:
        print(f"  ⚠️ Advertencia: No se recolectaron bloques de audio. Revisa los permisos o el dispositivo predeterminado.")
    
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
            print(f"  📁 [3/3] Video universal generado: '{video_final}' (¡Listo para abrir y enviar sin problemas!)")
        except Exception as e:
            print(f"  ⚠️ No se pudo ejecutar ffmpeg automáticamente: {e}")
            print(f"     (El video temporal sigue disponible en '{video_temp}')")

    print("\n=== TODAS LAS EVIDENCIAS DE CONVERSACIÓN FUERON GUARDADAS ===")